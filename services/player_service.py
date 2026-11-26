from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from database.matchups import PLAYER_STAT_COLUMNS, POSITION_METRICS, rank_weekly_opportunities
from database.player_stats import depth_charts, game_dates, schedule_sides, snap_counts, weekly_stats
from database.rosters import roster_for
from services.projection_service import estimate_ratio, estimate_z

EASTERN = ZoneInfo("America/New_York")

DEFAULT_LIMITS = {"qb": 1, "rb": 2, "wr": 3, "te": 2}
LIMITED_GAMES = 3
ELIGIBLE_STATUSES = {"", "ACT", "ACTIVE"}
BASELINES = {"season": None, "last3": 3, "last5": 5}


def _status_kind(status):
    if status is None or (isinstance(status, float) and pd.isna(status)) or str(status).strip() == "":
        return "unknown"
    if str(status).strip().upper() in ELIGIBLE_STATUSES - {""}:
        return "active"
    return "other"


def is_eligible(status):
    return _status_kind(status) == "active"


def _blank(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    return value


def _number(value):
    value = _blank(value)
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _games_for(stats, snaps, before_week):
    logs = {}
    snap_rows = {}
    if snaps is not None and not snaps.empty:
        for record in snaps.to_dict(orient="records"):
            player_id = record.get("player_id")
            if not player_id or int(record["week"]) >= int(before_week):
                continue
            snap_rows[(player_id, int(record["week"]))] = record
    stat_rows = {}
    if stats is not None and not stats.empty:
        for record in stats.to_dict(orient="records"):
            player_id = record.get("player_id")
            if not player_id or int(record["week"]) >= int(before_week):
                continue
            stat_rows[(player_id, int(record["week"]))] = record
    for player_id, week in set(snap_rows) | set(stat_rows):
        snap = snap_rows.get((player_id, week))
        stat = stat_rows.get((player_id, week))
        snaps_played = None if snap is None else _number(snap.get("offense_snaps"))
        produced = False
        if stat is not None:
            produced = any((_number(stat.get(column)) or 0) != 0 for column in PLAYER_STAT_COLUMNS.values())
        played = False
        via = None
        if snaps_played is not None and snaps_played > 0:
            played = True
            via = "snaps"
        elif snap is None and stat is not None:
            played = True
            via = "box"
        elif produced:
            played = True
            via = "box"
        values = {}
        for column in (*PLAYER_STAT_COLUMNS.values(), "attempts", "carries", "targets"):
            values[column] = None if stat is None else _number(stat.get(column))
        team = None
        if stat is not None and stat.get("team"):
            team = stat.get("team")
        elif snap is not None:
            team = snap.get("team")
        logs.setdefault(player_id, []).append({
            "week": week,
            "team": team,
            "played": played,
            "via": via,
            "offense_snaps": snaps_played or 0,
            "values": values,
        })
    for games in logs.values():
        games.sort(key=lambda game: game["week"])
    return logs


def _primary(position, game):
    values = game["values"]
    if position == "qb":
        return values.get("attempts") or 0
    if position == "rb":
        return (values.get("carries") or 0) + (values.get("targets") or 0)
    return values.get("targets") or 0


def _usage(position, games, team_weeks=None):
    played = [game for game in games if game["played"]]
    if team_weeks is None:
        recent = played[-3:]
        recent_known = bool(played)
        recent_missing = 0
    else:
        by_week = {int(game["week"]): game for game in games}
        recent = []
        known = 0
        recent_missing = 0
        for week in team_weeks:
            game = by_week.get(int(week))
            if game is None:
                recent_missing += 1
                continue
            known += 1
            if game["played"]:
                recent.append(game)
        recent_known = known > 0
    return {
        "recent_primary": sum(_primary(position, game) for game in recent),
        "recent_snaps": sum(game["offense_snaps"] or 0 for game in recent),
        "recent_known": recent_known,
        "recent_missing": recent_missing,
        "season_primary": sum(_primary(position, game) for game in played),
        "season_snaps": sum(game["offense_snaps"] or 0 for game in played),
        "played": played,
    }


def _recent_team_weeks(weeks, game_week):
    prior = sorted(week for week in weeks if int(week) < int(game_week))
    return prior[-3:]


def _chart_ranks(chart):
    ranks = {}
    if chart is None or chart.empty:
        return ranks
    for record in chart.to_dict(orient="records"):
        player_id = record.get("player_id")
        rank = _number(record.get("pos_rank"))
        if not player_id or rank is None:
            continue
        current = ranks.get(player_id)
        ranks[player_id] = rank if current is None else min(current, rank)
    return ranks


def _kickoff(gameday, gametime):
    if not gameday:
        return None
    day = str(gameday)[:10]
    clock = "" if gametime is None or (isinstance(gametime, float) and pd.isna(gametime)) else str(gametime).strip()
    if not clock or clock.lower() in {"nan", "none", "nat"}:
        return None
    hour, minute = (clock.split(":") + ["0"])[:2]
    try:
        local = datetime.fromisoformat(f"{day}T{int(hour):02d}:{int(float(minute)):02d}")
    except ValueError:
        return None
    return local.replace(tzinfo=EASTERN)


def _observed_at(value):
    text = str(value or "")
    if "T" not in text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=ZoneInfo("UTC"))
    return parsed


def _before_kickoff(observed, gameday, gametime):
    text = str(observed or "")
    kickoff = _kickoff(gameday, gametime)
    parsed = _observed_at(text)
    if parsed is not None and kickoff is not None:
        return parsed < kickoff
    if gameday and len(text) >= 10 and text[4] == "-":
        return text[:10] < str(gameday)[:10]
    return False


def _chart_is_fresh(chart, gameday, game_week):
    """A chart is fresh when it is within 10 days or one week of the game.

    Older charts stay visible, but recent usage can resolve them.
    """
    if chart is None or chart.empty or not gameday:
        return True
    observed = str(chart["observed_at"].iloc[0])
    if len(observed) >= 10 and observed[4] == "-":
        try:
            age = datetime.fromisoformat(str(gameday)[:10]) - datetime.fromisoformat(observed[:10])
            return age.days <= 10
        except ValueError:
            pass
    if "week" in chart.columns and game_week is not None:
        week = pd.to_numeric(chart["week"], errors="coerce").dropna()
        if not week.empty:
            return int(game_week) - int(week.max()) <= 1
    return True


def _latest_chart(charts, team, position, gameday, game_week, gametime=None):
    if charts is None or charts.empty:
        return charts.iloc[0:0] if charts is not None else pd.DataFrame()
    rows = charts.loc[(charts["team"] == team) & (charts["position"] == position)].copy()
    if rows.empty:
        return rows
    observed = rows["observed_at"].fillna("").astype(str)
    dated = observed.str.match(r"^\d{4}-\d{2}-\d{2}")
    if gameday and dated.any():
        eligible = [
            _before_kickoff(value, gameday, gametime)
            for value in observed
        ]
        chosen = rows.loc[dated.to_numpy() & pd.Series(eligible, index=rows.index).to_numpy()]
        if not chosen.empty:
            latest = chosen["observed_at"].max()
            return chosen.loc[chosen["observed_at"] == latest]
    weeks = pd.to_numeric(rows["week"], errors="coerce") if "week" in rows.columns else pd.Series(dtype="float64")
    if game_week is not None and weeks.notna().any():
        chosen = rows.loc[weeks.notna() & (weeks < int(game_week))]
        if not chosen.empty:
            latest_week = chosen["week"].max()
            return chosen.loc[chosen["week"] == latest_week]
    return rows.iloc[0:0]


def _has_role_evidence(player):
    if player["pos_rank"] is not None:
        return True
    if player.get("recent_known") and (player["recent_primary"] or player["recent_snaps"]):
        return True
    return bool(player["season_primary"] or player["season_snaps"])


def _evidence_key(player, prefer_usage):
    chart = (
        0 if player["pos_rank"] == 1 else 1,
        player["pos_rank"] if player["pos_rank"] is not None else 10_000,
    )
    usage = (
        0 if player.get("recent_known") else 1,
        -(player["recent_primary"] or 0),
        -(player["recent_snaps"] or 0),
        -(player["season_primary"] or 0),
        -(player["season_snaps"] or 0),
    )
    if prefer_usage:
        return usage + chart
    return chart + usage


def _order_players(members, chart, logs, position, team_weeks=None, chart_fresh=True):
    ranks = _chart_ranks(chart)
    ranked = []
    for player in members:
        usage = _usage(position, logs.get(player["player_id"], []), team_weeks)
        rank = ranks.get(player["player_id"])
        ranked.append({
            **player,
            "eligible": is_eligible(player.get("roster_status")),
            "pos_rank": None if rank is None else int(rank),
            **usage,
        })
    eligible = [player for player in ranked if player["eligible"]]
    starters = [player for player in eligible if player["pos_rank"] == 1]
    starters.sort(key=lambda player: (-player["recent_primary"], -player["recent_snaps"], player.get("player_name") or "", player["player_id"]))
    usage_candidates = [player for player in eligible if player.get("recent_known")]
    usage_leader = max(
        usage_candidates,
        key=lambda player: (player["recent_primary"], player["recent_snaps"], player["season_primary"], player["player_id"]),
        default=None,
    )
    chart_leader = starters[0] if starters else None
    uncertain = (
        chart_fresh
        and chart_leader is not None
        and usage_leader is not None
        and usage_leader["player_id"] != chart_leader["player_id"]
        and usage_leader["recent_primary"] > chart_leader["recent_primary"]
    )
    prefer_usage = (
        not chart_fresh
        and chart_leader is not None
        and usage_leader is not None
        and usage_leader["player_id"] != chart_leader["player_id"]
        and usage_leader["recent_primary"] > chart_leader["recent_primary"]
    )
    eligible.sort(key=lambda player: (
        0 if _has_role_evidence(player) else 1,
        *_evidence_key(player, prefer_usage),
        player.get("player_name") or "",
        player["player_id"],
    ))
    evidenced = [player for player in eligible if _has_role_evidence(player)]
    keys = [_evidence_key(player, prefer_usage) for player in evidenced]
    counts = {}
    for key in keys:
        counts[key] = counts.get(key, 0) + 1
    number = 0
    previous = None
    for player, key in zip(evidenced, keys):
        if key != previous:
            number += 1
            previous = key
        player["role"] = f"{position.upper()}{number}"
        if prefer_usage and player.get("recent_known") and (player["recent_primary"] or player["recent_snaps"]):
            player["role_source"] = "Recent usage"
        elif len(starters) > 1 and player["pos_rank"] == 1:
            player["role_source"] = "Depth chart + recent usage"
        elif player["pos_rank"] is not None:
            player["role_source"] = "Depth chart"
        elif player["recent_primary"] or player["recent_snaps"]:
            player["role_source"] = "Recent usage"
        else:
            player["role_source"] = "Season usage"
        player["role_note"] = None
        if counts[key] > 1:
            player["role_note"] = "Tied on available evidence."
        if prefer_usage and usage_leader is not None and player["player_id"] == usage_leader["player_id"]:
            player["role_note"] = "Depth chart is older than the recent games."
        if uncertain and chart_leader is not None and player["player_id"] == chart_leader["player_id"]:
            player["role_note"] = "Role uncertain"
            if len(starters) <= 1:
                player["role_source"] = "Role uncertain"
    for player in eligible:
        if _has_role_evidence(player):
            continue
        player["role"] = "Unranked"
        player["role_source"] = "Role unknown"
        player["role_note"] = "No pregame depth chart or recent usage."
    ineligible = [player for player in ranked if not player["eligible"]]
    ineligible.sort(key=lambda player: (player.get("player_name") or "", player["player_id"]))
    for player in ineligible:
        player["role"] = None
        player["role_source"] = "Roster status"
        if _status_kind(player.get("roster_status")) == "unknown":
            player["role_note"] = "Roster status unknown."
        else:
            player["role_note"] = player.get("roster_status")
    return eligible + ineligible


def _limit(players, position, scope):
    eligible = [player for player in players if player["eligible"]]
    ineligible = [player for player in players if not player["eligible"]]
    if scope == "all":
        return eligible + ineligible
    if scope == "eligible":
        return eligible
    evidenced = [player for player in eligible if player.get("role") not in {None, "Unranked"}]
    return evidenced[: DEFAULT_LIMITS.get(position, 3)]


def _window(played, baseline):
    count = BASELINES.get(baseline, None)
    if count is None:
        return played
    return played[-count:]


def _average(player, metric, baseline, roster_team, dates):
    column = PLAYER_STAT_COLUMNS.get(metric)
    sample = _window(player["played"], baseline)
    notes = []
    if any(game.get("team") and game["team"] != roster_team for game in player["played"]):
        notes.append("Season average includes games with a previous team.")
    if not sample or column is None:
        return {
            "player_avg": None,
            "games": 0,
            "limited": True,
            "last_week": None,
            "last_date": None,
            "participation_note": None,
            "metric_unavailable": column is None and bool(sample),
            "notes": notes,
        }
    values = []
    incomplete = False
    for game in sample:
        value = game["values"].get(column)
        if value is None and game["via"] == "snaps":
            value = 0.0
        elif value is None:
            incomplete = True
            continue
        values.append(value)
    if incomplete:
        notes.append("Participation data is incomplete. Box scores fill weeks without snap counts.")
    if not values:
        return {
            "player_avg": None,
            "games": 0,
            "limited": True,
            "last_week": sample[-1]["week"],
            "last_date": dates.get((sample[-1]["week"], roster_team)),
            "participation_note": notes[-1] if notes else None,
            "metric_unavailable": True,
            "notes": notes,
        }
    last = sample[-1]
    return {
        "player_avg": sum(values) / len(values),
        "games": len(values),
        "limited": len(values) < LIMITED_GAMES,
        "last_week": last["week"],
        "last_date": dates.get((last["week"], last.get("team") or roster_team)),
        "participation_note": "Participation data is incomplete. Box scores fill weeks without snap counts." if incomplete else None,
        "metric_unavailable": False,
        "notes": notes,
    }


def _warning(player, average, estimate):
    parts = []
    if player.get("role_note"):
        parts.append(player["role_note"])
    if average.get("limited") and average.get("player_avg") is not None:
        parts.append("Limited sample.")
    for note in average.get("notes") or []:
        if note not in parts:
            parts.append(note)
    if estimate.get("reason"):
        parts.append(estimate["reason"])
    return " ".join(parts) or None


def _usage_summary(position, player):
    if position == "qb":
        label = "pass attempts"
    elif position == "rb":
        label = "carries and targets"
    else:
        label = "targets"
    games = min(3, len(player["played"]))
    if games:
        return f"{player['recent_primary']:.0f} recent {label} across {games} games"
    if player["season_primary"]:
        return f"{player['season_primary']:.0f} season {label}"
    return "No recent offensive usage"


def weekly_player_opportunities(season, week, baseline="season", scope="relevant"):
    if season is None or week is None:
        return []
    season = str(season)
    week = int(week)
    if baseline not in BASELINES:
        baseline = "season"
    if scope not in {"relevant", "eligible", "all"}:
        scope = "relevant"
    roster = roster_for(season, week)
    opportunities = rank_weekly_opportunities(season, week)
    if not opportunities:
        return []
    stats = weekly_stats(season, week)
    snaps = snap_counts(season, week)
    stats_available = stats is not None and not stats.empty
    snaps_available = snaps is not None and not snaps.empty
    logs = _games_for(stats, snaps, week)
    charts = depth_charts(season)
    dates = game_dates(season)
    team_weeks = {}
    for record in schedule_sides(season).to_dict(orient="records"):
        team_weeks.setdefault(record["team"], []).append(int(record["week"]))
    grouped = {}
    for player in roster["players"]:
        grouped.setdefault((player["team"], player["position"]), []).append(player)
    gameday = {}
    gametime = {}
    for record in opportunities:
        gameday[record["offense"]] = record.get("gameday")
        gametime[record["offense"]] = record.get("gametime")
    rows = []
    for (team, position), members in grouped.items():
        if position not in POSITION_METRICS:
            continue
        chart = _latest_chart(charts, team, position, gameday.get(team), week, gametime.get(team))
        ordered = _order_players(
            members,
            chart,
            logs,
            position,
            team_weeks=_recent_team_weeks(team_weeks.get(team, []), week),
            chart_fresh=_chart_is_fresh(chart, gameday.get(team), week),
        )
        visible = _limit(ordered, position, scope)
        spots = [
            record for record in opportunities
            if record["offense"] == team and record["position"] == position
        ]
        for player in visible:
            for spot in spots:
                average = _average(player, spot["metric"], baseline, team, dates)
                if average["player_avg"] is None or spot.get("snapshot_week") is None:
                    estimate = estimate_ratio(average["player_avg"], None, None)
                    comparison = estimate_z(average["player_avg"], None)
                else:
                    estimate = estimate_ratio(average["player_avg"], spot["metric_value"], spot["league_mean"])
                    comparison = estimate_z(average["player_avg"], spot["z_score"])
                if average["player_avg"] is None:
                    if average.get("metric_unavailable"):
                        estimate["reason"] = "Metric unavailable."
                    elif not player.get("player_id"):
                        estimate["reason"] = "No matching player ID."
                    elif not stats_available and not snaps_available:
                        estimate["reason"] = "Player stats not ingested."
                    else:
                        estimate["reason"] = "No prior games."
                elif spot.get("snapshot_week") is None:
                    estimate["reason"] = "Defense snapshot unavailable."
                warning = _warning(player, average, estimate)
                rows.append({
                    "game_id": spot.get("game_id"),
                    "season": season,
                    "week": week,
                    "gameday": spot.get("gameday"),
                    "offense": team,
                    "defense": spot["defense"],
                    "player_id": player["player_id"],
                    "player_name": player.get("player_name"),
                    "position": position,
                    "roster_status": player.get("roster_status"),
                    "headshot_url": player.get("headshot_url"),
                    "role": player.get("role"),
                    "role_source": player.get("role_source"),
                    "role_note": player.get("role_note"),
                    "usage_summary": _usage_summary(position, player),
                    "metric": spot["metric"],
                    "label": spot["label"],
                    "z_score": spot["z_score"],
                    "defensive_metric_rank": spot["defensive_metric_rank"],
                    "defense_avg": spot["metric_value"],
                    "league_avg": spot["league_mean"],
                    "snapshot_week": spot.get("snapshot_week"),
                    "snapshot_note": spot.get("note"),
                    "window": baseline,
                    "player_avg": average["player_avg"],
                    "games": average["games"],
                    "limited": average["limited"],
                    "last_week": average["last_week"],
                    "last_date": average["last_date"],
                    "adjusted": estimate["adjusted"],
                    "adjustment_pct": estimate["adjustment_pct"],
                    "multiplier": estimate["multiplier"],
                    "method": estimate["method"],
                    "capped": estimate["capped"],
                    "baseline_only": estimate["baseline_only"],
                    "reason": estimate["reason"],
                    "z_adjusted": comparison["adjusted"],
                    "z_adjustment_pct": comparison["adjustment_pct"],
                    "z_multiplier": comparison["multiplier"],
                    "z_capped": comparison["capped"],
                    "warning": warning,
                    "roster_week": roster["roster_week"],
                    "roster_note": roster["roster_note"],
                })
    _flag_conflicts(rows)
    return rows


def _flag_conflicts(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault((row["player_id"], row["offense"]), {})[row["metric"]] = row
    for metrics in grouped.values():
        receptions = metrics.get("Receiving_Recpt")
        targets = metrics.get("Receiving_Targt")
        if not receptions or not targets:
            continue
        if receptions["adjusted"] is None or targets["adjusted"] is None:
            continue
        if receptions["adjusted"] > targets["adjusted"]:
            note = "Adjusted receptions exceed adjusted targets."
            for row in (receptions, targets):
                row["warning"] = f"{row['warning']} {note}".strip() if row.get("warning") else note


def filter_player_rows(rows, search=None, offense=None, defense=None, position=None, metric=None, flags=None, minimum_games=None):
    selected_flags = {str(flag).upper() for flag in flags} if flags else None
    query = str(search).strip().lower() if search else ""
    filtered = []
    for row in rows:
        if offense and row.get("offense") != offense:
            continue
        if defense and row.get("defense") != defense:
            continue
        if position and row.get("position") != str(position).lower():
            continue
        if metric and row.get("metric") != metric:
            continue
        if selected_flags and row.get("label") not in selected_flags:
            continue
        if minimum_games is not None and int(row.get("games") or 0) < int(minimum_games):
            continue
        if query:
            haystack = " ".join(
                str(row.get(key) or "")
                for key in ("player_name", "offense", "defense", "role", "metric")
            ).lower()
            if query not in haystack:
                continue
        filtered.append(row)
    return filtered


def sort_player_rows(rows, key="z_score", best=True):
    selected = key if key in {"z_score", "adjusted", "adjustment_pct"} else "z_score"
    if selected != "z_score" and len({row.get("metric") for row in rows}) != 1:
        selected = "z_score"

    def value(row):
        number = row.get(selected)
        if number is None or (isinstance(number, float) and pd.isna(number)):
            return None
        return float(number)

    present = [row for row in rows if value(row) is not None]
    missing = [row for row in rows if value(row) is None]
    present.sort(key=value, reverse=best)
    return present + missing
