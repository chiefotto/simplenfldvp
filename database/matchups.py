import sqlite3

import pandas as pd

from database.abbreviations import canonical_abbr
from database.analysis import analyze_snapshot
from database.queries import (
    DB_PATH,
    current_schedule,
    defense_snapshot_for,
    league_table,
    matchup_context,
    season_status,
    team_on_bye,
    week_games,
)

POSITION_METRICS = {
    "qb": ["Passing_Yd", "Passing_TD", "Rushing_Yd", "Rushing_TD"],
    "rb": [
        "Rushing_Att", "Rushing_Yd", "Rushing_TD",
        "Receiving_Targt", "Receiving_Recpt", "Receiving_Yd", "Receiving_TD",
    ],
    "wr": ["Receiving_Targt", "Receiving_Recpt", "Receiving_Yd", "Receiving_TD"],
    "te": ["Receiving_Targt", "Receiving_Recpt", "Receiving_Yd", "Receiving_TD"],
}

TOUCHDOWN_METRICS = {
    "qb": ["Passing_TD", "Rushing_TD"],
    "rb": ["Rushing_TD", "Receiving_TD"],
    "wr": ["Receiving_TD"],
    "te": ["Receiving_TD"],
}

METRIC_ALIASES = {
    "receptions": "Receiving_Recpt",
    "receiving_yards": "Receiving_Yd",
    "receiving_td": "Receiving_TD",
    "rushing_yards": "Rushing_Yd",
    "rushing_td": "Rushing_TD",
    "passing_yards": "Passing_Yd",
    "passing_td": "Passing_TD",
    "targets": "Receiving_Targt",
    "rushing_attempts": "Rushing_Att",
}


def resolve_metric_alias(position, alias):
    position = position.lower()
    if position not in POSITION_METRICS:
        raise ValueError(f"unknown position {position}")
    key = alias.lower()
    metric = METRIC_ALIASES.get(key, key)
    allowed = {name.lower(): name for name in POSITION_METRICS[position]}
    if metric.lower() not in allowed and key not in METRIC_ALIASES:
        raise ValueError(f"unknown metric {alias}")
    canonical = METRIC_ALIASES.get(key) or allowed.get(metric.lower())
    if canonical not in POSITION_METRICS[position]:
        raise ValueError(f"{alias} is not a {position} metric")
    return canonical


def matchup_score(metrics):
    scores = [metric["z_score"] for metric in metrics if pd.notna(metric["z_score"])]
    if not scores:
        return None
    return sum(scores) / len(scores)


def _metric_row(row):
    return {
        "metric": row["metric"],
        "metric_value": float(row["metric_value"]),
        "league_mean": float(row["league_mean"]),
        "z_score": float(row["z_score"]),
        "rank": int(row["rank"]),
        "label": row["label"],
    }


def _sort_metrics(rows):
    return sorted(rows, key=lambda metric: metric["z_score"], reverse=True)


def _plain(value):
    if value is None or pd.isna(value):
        return None
    return value


def _snapshot(position, season=None, week=None):
    if season is None and week is None:
        season, defense_week, note = matchup_context()
        slate_week = season_status()["current_week"]
    else:
        season, defense_week, note = defense_snapshot_for(season, week)
        slate_week = None if week is None else int(week)
    if defense_week is None:
        return season, None, slate_week, note, analyze_snapshot(pd.DataFrame(), position)
    scored = analyze_snapshot(league_table(season, defense_week), position)
    return season, defense_week, slate_week, note, scored


def _weekly_sides(season=None, week=None):
    columns = ["offense", "defense", "game_id", "gameday", "gametime", "away_score", "home_score"]
    if season is None or week is None:
        status = season_status()
        if status["current_week"] is None:
            return pd.DataFrame(columns=columns)
        with sqlite3.connect(DB_PATH) as conn:
            season = conn.execute("SELECT MAX(season) FROM schedule").fetchone()[0]
        week = status["current_week"]
    games = week_games(season, week)
    if games.empty:
        return pd.DataFrame(columns=columns)
    return pd.concat(
        [
            games.rename(columns={"away_team": "offense", "home_team": "defense"}),
            games.rename(columns={"home_team": "offense", "away_team": "defense"}),
        ],
        ignore_index=True,
    )


def _defense_metrics(scored, defense, names):
    rows = scored.loc[(scored["team_abbr"] == defense) & (scored["metric"].isin(names))]
    return _sort_metrics([_metric_row(row) for _, row in rows.iterrows()])


def _assign_ranks(records, key, rank_name="matchup_rank"):
    ranked = [record for record in records if record[key] is not None and pd.notna(record[key])]
    ranked.sort(key=lambda record: record[key], reverse=True)
    previous = None
    rank = 0
    for index, record in enumerate(ranked, start=1):
        if previous is None or record[key] < previous:
            rank = index
        record[rank_name] = rank
        previous = record[key]
    return ranked


def _configured_scores(scored):
    if scored.empty:
        return scored
    mask = pd.Series(False, index=scored.index)
    for position, metrics in POSITION_METRICS.items():
        mask |= (scored["position"] == position) & (scored["metric"].isin(metrics))
    return scored.loc[mask]


def rank_weekly_opportunities(season=None, week=None):
    if season is None and week is None:
        season, defense_week, note = matchup_context()
        slate_week = season_status()["current_week"]
        sides = _weekly_sides()
    else:
        season, defense_week, note = defense_snapshot_for(season, week)
        slate_week = None if week is None else int(week)
        sides = _weekly_sides(season, week)
    if defense_week is None:
        scored = analyze_snapshot(pd.DataFrame())
    else:
        scored = analyze_snapshot(league_table(season, defense_week))
    scored = _configured_scores(scored)
    lookup = {
        (row["team_abbr"], row["position"], row["metric"]): row
        for _, row in scored.iterrows()
    }
    records = []
    for pair in sides.itertuples(index=False):
        for position, metrics in POSITION_METRICS.items():
            for metric_name in metrics:
                row = lookup.get((pair.defense, position, metric_name))
                if row is None:
                    continue
                z_score = float(row["z_score"])
                records.append({
                    "game_id": _plain(pair.game_id),
                    "gameday": _plain(pair.gameday),
                    "gametime": _plain(pair.gametime),
                    "away_score": _plain(pair.away_score),
                    "home_score": _plain(pair.home_score),
                    "offense": pair.offense,
                    "defense": pair.defense,
                    "position": position,
                    "metric": metric_name,
                    "metric_value": float(row["metric_value"]),
                    "league_mean": float(row["league_mean"]),
                    "z_score": z_score,
                    "opportunity_score": z_score,
                    "defensive_metric_rank": int(row["rank"]),
                    "label": row["label"],
                    "season": season,
                    "snapshot_week": defense_week,
                    "week": slate_week,
                    "note": note,
                })
    return _assign_ranks(records, "opportunity_score", "weekly_rank")


def touchdown_opportunities(position=None):
    allowed = {
        (pos, metric)
        for pos, metrics in TOUCHDOWN_METRICS.items()
        for metric in metrics
        if position is None or pos == position
    }
    records = []
    for record in rank_weekly_opportunities():
        if (record["position"], record["metric"]) not in allowed:
            continue
        copied = dict(record)
        copied["td_type"] = copied["metric"]
        copied["touchdown_opportunity_score"] = copied["z_score"]
        records.append(copied)
    return _assign_ranks(records, "touchdown_opportunity_score", "weekly_rank")


def canonical_metric(alias):
    key = str(alias).lower()
    if key in METRIC_ALIASES:
        return METRIC_ALIASES[key]
    columns = {
        name.lower(): name
        for names in POSITION_METRICS.values()
        for name in names
    }
    if key in columns:
        return columns[key]
    raise ValueError(f"unknown metric {alias}")


def positions_for_metric(metric):
    return [position for position, names in POSITION_METRICS.items() if metric in names]


def metric_opportunities(alias):
    metric_name = canonical_metric(alias)
    records = []
    for record in rank_weekly_opportunities():
        if record["metric"] != metric_name:
            continue
        records.append(dict(record))
    return _assign_ranks(records, "opportunity_score", "weekly_rank")


def rank_weekly_matchups(position, season=None, week=None):
    position = position.lower()
    requested = season is not None and week is not None
    season, defense_week, slate_week, note, scored = _snapshot(position, season, week)
    names = POSITION_METRICS[position]
    records = []
    sides = _weekly_sides(season, slate_week) if requested else _weekly_sides()
    for pair in sides.itertuples(index=False):
        metrics = [metric for metric in _defense_metrics(scored, pair.defense, names)]
        records.append({
            "game_id": _plain(getattr(pair, "game_id", None)),
            "offense": pair.offense,
            "defense": pair.defense,
            "position": position,
            "season": season,
            "snapshot_week": defense_week,
            "week": slate_week,
            "note": note,
            "matchup_score": matchup_score(metrics),
            "metrics": metrics,
        })
    return _assign_ranks(records, "matchup_score")


def rank_weekly_metric(position, alias):
    position = position.lower()
    metric_name = resolve_metric_alias(position, alias)
    season, defense_week, slate_week, note, scored = _snapshot(position)
    records = []
    for pair in _weekly_sides().itertuples(index=False):
        metrics = _defense_metrics(scored, pair.defense, [metric_name])
        if not metrics:
            continue
        metric = metrics[0]
        records.append({
            "offense": pair.offense,
            "defense": pair.defense,
            "position": position,
            "season": season,
            "snapshot_week": defense_week,
            "week": slate_week,
            "note": note,
            "metric": metric["metric"],
            "metric_value": metric["metric_value"],
            "z_score": metric["z_score"],
            "league_rank": metric["rank"],
            "label": metric["label"],
        })
    return _assign_ranks(records, "z_score")


def get_defense_profile(team, position):
    position = position.lower()
    team = canonical_abbr(team)
    season, defense_week, _slate_week, note, scored = _snapshot(position)
    names = [*POSITION_METRICS[position], "FPTS"]
    rows = scored.loc[(scored["team_abbr"] == team) & (scored["metric"].isin(names))]
    if rows.empty:
        raise ValueError(f"{team} has no {position} profile")
    order = {name: index for index, name in enumerate(names)}
    metrics = [_metric_row(row) for _, row in rows.iterrows()]
    metrics.sort(key=lambda metric: order[metric["metric"]])
    return {
        "team": team,
        "position": position,
        "season": season,
        "week": defense_week,
        "note": note,
        "metrics": metrics,
    }


def get_offense_matchup(team, position):
    team = canonical_abbr(team)
    position = position.lower()
    if team_on_bye(team):
        return {"bye": True, "offense": team, "position": position}
    found = [record for record in rank_weekly_matchups(position) if record["offense"] == team]
    if not found:
        return {"bye": True, "offense": team, "position": position}
    return found[0]


def _target_spots(records, offense):
    spots = [
        dict(record)
        for record in records
        if record["offense"] == offense and record["label"] in {"HOT", "WARM"}
    ]
    spots.sort(key=lambda record: record["z_score"], reverse=True)
    return spots


def _game_sides(records, offense, defense):
    return [
        {"offense": offense, "defense": defense, "spots": _target_spots(records, offense)},
        {"offense": defense, "defense": offense, "spots": _target_spots(records, defense)},
    ]


def game_hot_spots(team):
    team = canonical_abbr(team)
    if team_on_bye(team):
        return {"bye": True, "offense": team}
    pair = next((row for row in _weekly_sides().itertuples(index=False) if row.offense == team), None)
    if pair is None:
        return {"bye": True, "offense": team}
    return {
        "offense": team,
        "defense": pair.defense,
        "sides": _game_sides(rank_weekly_opportunities(), team, pair.defense),
    }


def slate_hot_spots():
    records = rank_weekly_opportunities()
    games = []
    for row in current_schedule().itertuples(index=False):
        away = row.away_team
        home = row.home_team
        games.append({
            "offense": away,
            "defense": home,
            "sides": _game_sides(records, away, home),
        })
    return {"games": games}


def offense_stat_rankings(team):
    team = canonical_abbr(team)
    if team_on_bye(team):
        return {"bye": True, "offense": team}
    pair = next((row for row in _weekly_sides().itertuples(index=False) if row.offense == team), None)
    if pair is None:
        return {"bye": True, "offense": team}
    spots = [dict(record) for record in rank_weekly_opportunities() if record["offense"] == team]
    return {
        "offense": team,
        "defense": pair.defense,
        "spots": _assign_ranks(spots, "z_score", "offense_rank"),
    }
