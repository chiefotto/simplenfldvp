import pandas as pd

from database.analysis import analyze_snapshot
from database.fantasy import rank_weekly_fantasy_matchups
from database.matchups import (
    POSITION_METRICS,
    rank_weekly_matchups,
    rank_weekly_opportunities,
)
from database.queries import defense_snapshot_for, league_table, list_seasons_weeks, season_status, week_games
from database.rosters import roster_for, team_directory
from services.catalog import normalize_metric_alias, normalize_position, normalize_team
from services.errors import AppError, respond, success
from services.links import game_url, rankings_url, weekly_url

FLAGS = ("HOT", "WARM", "NEUTRAL", "COOL", "COLD")
FAVORABLE = {"HOT", "WARM"}
UNFAVORABLE = {"COOL", "COLD"}
POSITIONS = ("qb", "rb", "wr", "te")
LEADERBOARD_METRICS = (
    "Passing_Yd",
    "Passing_TD",
    "Rushing_Att",
    "Rushing_Yd",
    "Rushing_TD",
    "Receiving_Targt",
    "Receiving_Recpt",
    "Receiving_Yd",
    "Receiving_TD",
)
POSITION_GROUPS = {
    "qb": "quarterbacks",
    "rb": "running backs",
    "wr": "wide receivers",
    "te": "tight ends",
}
METRIC_LABELS = {
    "Receiving_Recpt": "receptions",
    "Receiving_Targt": "targets",
    "Receiving_Yd": "receiving yards",
    "Receiving_TD": "receiving touchdowns",
    "Rushing_Att": "rushing attempts",
    "Rushing_Yd": "rushing yards",
    "Rushing_TD": "rushing touchdowns",
    "Passing_Yd": "passing yards",
    "Passing_TD": "passing touchdowns",
    "Passing_Att": "pass attempts",
    "Passing_Cmp": "completions",
    "Passing_Int": "interceptions",
    "Passing_Rate": "passer rating",
    "Rushing_Avg": "yards per carry",
    "Receiving_Avg": "yards per reception",
    "FL": "fumbles lost",
    "FPTS": "fantasy points",
}
AMOUNT = {
    "HOT": "many more",
    "WARM": "more",
    "NEUTRAL": "about an average number of",
    "COOL": "fewer",
    "COLD": "many fewer",
}
MISSING_URL = "The web app address is not configured. Set WEB_APP_BASE_URL and restart the bot."
ACTIVE_STATUSES = {"", "ACT", "ACTIVE"}


def metric_label(metric):
    return METRIC_LABELS.get(metric, str(metric).replace("_", " ").lower())


def describe_spot(record):
    amount = AMOUNT.get(record["label"], "a different number of")
    stat = metric_label(record["metric"])
    group = POSITION_GROUPS.get(record["position"], record["position"].upper())
    sentence = f"{record['defense']} allows {amount} {stat} to {group}"
    if record["label"] == "NEUTRAL":
        return sentence + "."
    return sentence + " than the league average."


def flag_counts(spots):
    counts = {flag.lower(): 0 for flag in FLAGS}
    for spot in spots:
        label = spot.get("label")
        if label in FLAGS:
            counts[label.lower()] += 1
    return counts


def player_is_active(player):
    status = str(player.get("roster_status") or "").strip().upper()
    return status in ACTIVE_STATUSES


def resolve_slate(season=None, week=None):
    status = season_status()
    seasons = list_seasons_weeks()
    if season is None:
        season = status.get("dvp_season") or (next(iter(seasons), None))
    season = None if season is None else str(season)
    weeks = seasons.get(season, [])
    warning = None
    if week is None:
        current = status.get("current_week")
        week = current if current in weeks else (weeks[-1] if weeks else None)
    else:
        try:
            week = int(week)
        except (TypeError, ValueError) as error:
            raise AppError("INVALID_WEEK", f"Week '{week}' is not valid.") from error
        if weeks and week not in weeks:
            warning = f"Week {week} is not on the {season} schedule."
    if season is not None and seasons and season not in seasons:
        warning = f"Season {season} is not in the stored schedule."
    return season, week, warning


def slate_meta(season, week, warning=None):
    snap_season, snapshot_week, note = defense_snapshot_for(season, week)
    roster = roster_for(season, week)
    meta = {
        "season": snap_season or season,
        "week": week,
        "snapshot_week": snapshot_week,
        "note": note,
        "roster_week": roster["roster_week"],
        "roster_note": roster["roster_note"],
    }
    if warning:
        meta["warning"] = warning
    return meta


def _display_rank(records, key, best=True):
    ranked = [dict(record) for record in records if record.get(key) is not None and pd.notna(record.get(key))]
    ranked.sort(key=lambda record: record[key], reverse=best)
    previous = None
    rank = 0
    for index, record in enumerate(ranked, start=1):
        score = record[key]
        if previous is None or (score < previous if best else score > previous):
            rank = index
        record["display_rank"] = rank
        previous = score
    return ranked


def _players_for(players, team, position):
    found = [
        player for player in players
        if player["team"] == team and player["position"] == position
    ]
    found.sort(key=lambda player: (player["player_name"], player["player_id"]))
    return found


def get_weekly_outlook(season=None, week=None, context=None):
    def action():
        slate_season, slate_week, warning = resolve_slate(season, week)
        meta = slate_meta(slate_season, slate_week, warning)
        if slate_season is None or slate_week is None:
            return success([], meta)
        return success(rank_weekly_opportunities(slate_season, slate_week), meta)

    return respond(action)


def get_leaderboards(
    season=None,
    week=None,
    top=5,
    position=None,
    metric=None,
    flags=None,
    best=True,
    context=None,
):
    def action():
        slate_season, slate_week, warning = resolve_slate(season, week)
        meta = slate_meta(slate_season, slate_week, warning)
        pos = normalize_position(position) if position else None
        selected_metric = normalize_metric_alias(metric) if metric else None
        allowed_flags = {str(flag).upper() for flag in flags} if flags else None
        records = [] if slate_season is None or slate_week is None else rank_weekly_opportunities(slate_season, slate_week)
        categories = []
        for name in LEADERBOARD_METRICS:
            if selected_metric and name != selected_metric:
                continue
            rows = [record for record in records if record["metric"] == name]
            if pos:
                rows = [record for record in rows if record["position"] == pos]
            if allowed_flags:
                rows = [record for record in rows if record["label"] in allowed_flags]
            ranked = _display_rank(rows, "z_score", best=best)
            limit = len(ranked) if top is None else max(int(top), 0)
            categories.append({
                "metric": name,
                "label": metric_label(name),
                "positions": [item for item, names in POSITION_METRICS.items() if name in names],
                "rows": ranked[:limit],
            })
        positional = _positional_summary(records, slate_season, slate_week, pos)
        return success({"categories": categories, "positional": positional}, meta)

    return respond(action)


def _positional_summary(records, season, week, position=None):
    positions = (position,) if position else POSITIONS
    summary = []
    if season is None or week is None:
        return summary
    for pos in positions:
        ranked = rank_weekly_matchups(pos, season, week)
        for record in ranked:
            spots = [
                spot for spot in records
                if spot["offense"] == record["offense"] and spot["position"] == pos
            ]
            summary.append({
                "game_id": record.get("game_id"),
                "offense": record["offense"],
                "defense": record["defense"],
                "position": pos,
                "matchup_score": record["matchup_score"],
                "matchup_rank": record.get("matchup_rank"),
                "flag_counts": flag_counts(spots),
                "snapshot_week": record.get("snapshot_week"),
                "note": record.get("note"),
            })
    return summary


def get_positional_outlook(season=None, week=None, position=None, context=None):
    def action():
        slate_season, slate_week, warning = resolve_slate(season, week)
        meta = slate_meta(slate_season, slate_week, warning)
        pos = normalize_position(position) if position else None
        records = [] if slate_season is None or slate_week is None else rank_weekly_opportunities(slate_season, slate_week)
        return success(_positional_summary(records, slate_season, slate_week, pos), meta)

    return respond(action)


def _game_row(frame, game_id):
    matched = frame.loc[frame["game_id"] == str(game_id)]
    if matched.empty:
        return None
    row = matched.iloc[0]
    values = {}
    for key, value in row.items():
        values[key] = None if pd.isna(value) else value
    return values


def _side(offense, defense, records, matchups, players):
    spots = [dict(record) for record in records if record["offense"] == offense]
    spots.sort(key=lambda record: record["z_score"], reverse=True)
    for spot in spots:
        spot["description"] = describe_spot(spot)
    groups = []
    for pos in POSITIONS:
        pos_spots = [spot for spot in spots if spot["position"] == pos]
        matchup = next((record for record in matchups.get(pos, []) if record["offense"] == offense), None)
        groups.append({
            "position": pos,
            "matchup_score": None if matchup is None else matchup["matchup_score"],
            "matchup_rank": None if matchup is None else matchup.get("matchup_rank"),
            "flag_counts": flag_counts(pos_spots),
            "players": _players_for(players, offense, pos),
            "spots": pos_spots,
        })
    return {
        "offense": offense,
        "defense": defense,
        "positions": groups,
        "spots": spots,
        "favorable": [spot for spot in spots if spot["label"] in FAVORABLE],
        "unfavorable": [spot for spot in spots if spot["label"] in UNFAVORABLE],
    }


def get_game_outlook(game_id, season=None, week=None, context=None):
    def action():
        if not game_id:
            raise AppError("GAME_NOT_FOUND", "Choose a game to open its outlook.")
        slate_season, slate_week, warning = resolve_slate(season, week)
        meta = slate_meta(slate_season, slate_week, warning)
        games = week_games(slate_season, slate_week) if slate_season is not None and slate_week is not None else week_games(None, None)
        game = _game_row(games, game_id)
        if game is None:
            located = _find_game(game_id)
            if located is None:
                raise AppError("GAME_NOT_FOUND", f"Game '{game_id}' was not found.")
            slate_season, slate_week = located["season"], located["week"]
            warning = None
            meta = slate_meta(slate_season, slate_week, warning)
            game = located
        records = rank_weekly_opportunities(slate_season, slate_week)
        matchups = {pos: rank_weekly_matchups(pos, slate_season, slate_week) for pos in POSITIONS}
        players = roster_for(slate_season, slate_week)["players"]
        away = game["away_team"]
        home = game["home_team"]
        data = {
            **game,
            "season": slate_season,
            "week": slate_week,
            "snapshot_week": meta["snapshot_week"],
            "note": meta["note"],
            "roster_week": meta["roster_week"],
            "roster_note": meta["roster_note"],
            "teams": team_directory(),
            "sides": [
                _side(away, home, records, matchups, players),
                _side(home, away, records, matchups, players),
            ],
        }
        return success(data, meta)

    return respond(action)


def _find_game(game_id):
    seasons = list_seasons_weeks()
    for season, weeks in seasons.items():
        for week in weeks:
            game = _game_row(week_games(season, week), game_id)
            if game is not None:
                game["season"] = season
                game["week"] = int(week)
                return game
    return None


def get_schedule_outlook(season=None, week=None, context=None):
    def action():
        slate_season, slate_week, warning = resolve_slate(season, week)
        meta = slate_meta(slate_season, slate_week, warning)
        games = week_games(slate_season, slate_week) if slate_season is not None and slate_week is not None else week_games(None, None)
        records = [] if games.empty else rank_weekly_opportunities(slate_season, slate_week)
        teams = team_directory()
        rows = []
        for game in games.to_dict(orient="records"):
            spots = [record for record in records if record.get("game_id") == game["game_id"]]
            counts = flag_counts(spots)
            rows.append({
                **{key: None if pd.isna(value) else value for key, value in game.items()},
                "hot": counts["hot"],
                "warm": counts["warm"],
                "away_name": teams.get(game["away_team"], {}).get("team_name") or game["away_team"],
                "home_name": teams.get(game["home_team"], {}).get("team_name") or game["home_team"],
                "away_logo": teams.get(game["away_team"], {}).get("team_logo_url"),
                "home_logo": teams.get(game["home_team"], {}).get("team_logo_url"),
            })
        return success(rows, meta)

    return respond(action)


def _defense_rankings(season, week):
    snap_season, snapshot_week, note = defense_snapshot_for(season, week)
    if snapshot_week is None:
        return []
    scored = analyze_snapshot(league_table(snap_season, snapshot_week))
    rows = []
    for record in scored.to_dict(orient="records"):
        rows.append({
            "team": record["team_abbr"],
            "position": record["position"],
            "metric": record["metric"],
            "metric_value": float(record["metric_value"]),
            "league_mean": float(record["league_mean"]),
            "z_score": float(record["z_score"]),
            "defensive_metric_rank": int(record["rank"]),
            "label": record["label"],
            "snapshot_week": snapshot_week,
            "note": note,
            "season": snap_season,
            "week": week,
        })
    return rows


def get_rankings(mode="offense", season=None, week=None, context=None):
    def action():
        slate_season, slate_week, warning = resolve_slate(season, week)
        meta = slate_meta(slate_season, slate_week, warning)
        selected = str(mode or "offense").lower()
        if selected not in {"offense", "defense", "positional", "fantasy"}:
            raise AppError("INVALID_MODE", f"Ranking mode '{mode}' is not valid.")
        meta["mode"] = selected
        if slate_season is None or slate_week is None:
            return success([], meta)
        if selected == "defense":
            return success(_defense_rankings(slate_season, slate_week), meta)
        if selected == "positional":
            records = rank_weekly_opportunities(slate_season, slate_week)
            return success(_positional_summary(records, slate_season, slate_week), meta)
        if selected == "fantasy":
            return success(rank_weekly_fantasy_matchups(True, slate_season, slate_week), meta)
        return success(rank_weekly_opportunities(slate_season, slate_week), meta)

    return respond(action)


def filter_ranking_rows(
    rows,
    search=None,
    offense=None,
    defense=None,
    position=None,
    metric=None,
    flags=None,
):
    selected_flags = {str(flag).upper() for flag in flags} if flags else None
    metric_name = normalize_metric_alias(metric) if metric else None
    pos = normalize_position(position) if position else None
    offense_name = normalize_team(offense) if offense else None
    defense_name = normalize_team(defense) if defense else None
    query = str(search).strip().lower() if search else ""
    filtered = []
    for record in rows:
        if offense_name and record.get("offense") != offense_name and record.get("team") != offense_name:
            continue
        if defense_name and record.get("defense") != defense_name:
            continue
        if pos and record.get("position") != pos:
            continue
        if metric_name and record.get("metric") != metric_name:
            continue
        if selected_flags and record.get("label") not in selected_flags:
            continue
        if query:
            haystack = " ".join(
                str(record.get(key) or "")
                for key in ("offense", "defense", "team", "position", "metric", "label")
            ).lower()
            if query not in haystack and query not in metric_label(record.get("metric", "")).lower():
                continue
        filtered.append(record)
    return filtered


def get_weekly_link(base_url, season=None, week=None, context=None):
    def action():
        slate_season, slate_week, warning = resolve_slate(season, week)
        url = weekly_url(base_url, slate_season, slate_week)
        return success(_link_payload(
            f"NFL Weekly Outlook — Week {slate_week}",
            "Explore this week's best statistical opportunities, positional matchups, and relevant NFL players.",
            url,
            "View Weekly Outlook",
            warning,
        ), slate_meta(slate_season, slate_week, warning))

    return respond(action)


def get_game_link(base_url, team, season=None, week=None, context=None):
    def action():
        abbr = normalize_team(team)
        slate_season, slate_week, warning = resolve_slate(season, week)
        games = week_games(slate_season, slate_week)
        matched = games[(games["away_team"] == abbr) | (games["home_team"] == abbr)]
        if matched.empty:
            when = f" in Week {slate_week}" if slate_week is not None else ""
            raise AppError("TEAM_NOT_PLAYING", f"{abbr} does not have a scheduled game{when}.")
        game = matched.iloc[0]
        opponent = game["home_team"] if game["away_team"] == abbr else game["away_team"]
        url = game_url(base_url, slate_season, slate_week, game["game_id"])
        return success(_link_payload(
            f"{abbr} vs {opponent} — Week {slate_week}",
            "Open the game outlook for both offenses, including the relevant rostered players.",
            url,
            "View Game Outlook",
            warning,
        ), slate_meta(slate_season, slate_week, warning))

    return respond(action)


def get_rankings_link(base_url, position=None, metric=None, season=None, week=None, context=None):
    def action():
        pos = normalize_position(position) if position else None
        selected = None
        if metric:
            selected = normalize_metric_alias(metric)
            if pos and selected not in POSITION_METRICS[pos]:
                raise AppError(
                    "INVALID_METRIC_FOR_POSITION",
                    f"Metric '{metric}' is not supported for {pos.upper()}.",
                )
        slate_season, slate_week, warning = resolve_slate(season, week)
        url = rankings_url(base_url, slate_season, slate_week, None if pos is None else pos.upper(), selected)
        label = "View Rankings"
        title = f"Matchup Rankings — Week {slate_week}"
        if pos:
            title = f"{pos.upper()} Rankings — Week {slate_week}"
        return success(_link_payload(
            title,
            "Open the rankings table for this week.",
            url,
            label,
            warning,
        ), slate_meta(slate_season, slate_week, warning))

    return respond(action)


def _link_payload(title, description, url, button, warning):
    if url is None:
        description = MISSING_URL
    if warning:
        description = f"{description}\n{warning}"
    return {"title": title, "description": description, "url": url, "button": button}
