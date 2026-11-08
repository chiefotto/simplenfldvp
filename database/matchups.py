import sqlite3

import pandas as pd

from database.analysis import analyze_snapshot
from database.queries import DB_PATH, league_table, matchup_context, season_status, team_on_bye

POSITION_METRICS = {
    "qb": ["Passing_Yd", "Passing_TD", "Rushing_Yd", "Rushing_TD"],
    "rb": [
        "Rushing_Att", "Rushing_Yd", "Rushing_TD",
        "Receiving_Targt", "Receiving_Recpt", "Receiving_Yd", "Receiving_TD",
    ],
    "wr": ["Receiving_Targt", "Receiving_Recpt", "Receiving_Yd", "Receiving_TD"],
    "te": ["Receiving_Targt", "Receiving_Recpt", "Receiving_Yd", "Receiving_TD"],
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


def _snapshot(position):
    season, defense_week, note = matchup_context()
    status = season_status()
    if defense_week is None:
        return season, None, status["current_week"], note, analyze_snapshot(pd.DataFrame(), position)
    scored = analyze_snapshot(league_table(season, defense_week), position)
    return season, defense_week, status["current_week"], note, scored


def _weekly_sides():
    status = season_status()
    if status["current_week"] is None:
        return pd.DataFrame(columns=["offense", "defense"])
    with sqlite3.connect(DB_PATH) as conn:
        schedule_season = conn.execute("SELECT MAX(season) FROM schedule").fetchone()[0]
        games = pd.read_sql(
            """
            SELECT away_team, home_team
            FROM schedule
            WHERE season = ? AND week = ?
            """,
            conn,
            params=(schedule_season, status["current_week"]),
        )
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


def rank_weekly_opportunities():
    season, defense_week, note = matchup_context()
    slate_week = season_status()["current_week"]
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
    for pair in _weekly_sides().itertuples(index=False):
        for position, metrics in POSITION_METRICS.items():
            for metric_name in metrics:
                row = lookup.get((pair.defense, position, metric_name))
                if row is None:
                    continue
                z_score = float(row["z_score"])
                records.append({
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


def rank_weekly_matchups(position):
    position = position.lower()
    season, defense_week, slate_week, note, scored = _snapshot(position)
    names = POSITION_METRICS[position]
    records = []
    for pair in _weekly_sides().itertuples(index=False):
        metrics = [metric for metric in _defense_metrics(scored, pair.defense, names)]
        records.append({
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
    team = team.upper()
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
    team = team.upper()
    position = position.lower()
    if team_on_bye(team):
        return {"bye": True, "offense": team, "position": position}
    found = [record for record in rank_weekly_matchups(position) if record["offense"] == team]
    if not found:
        return {"bye": True, "offense": team, "position": position}
    return found[0]
