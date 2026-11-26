import pandas as pd

from database.abbreviations import canonical_abbr
from database.analysis import analyze_snapshot
from database.matchups import _weekly_sides
from database.queries import defense_snapshot_for, league_table, matchup_context, season_status, team_on_bye

POSITIONS = ("qb", "rb", "wr", "te")


def _rank(records, descending):
    ranked = [record for record in records if pd.notna(record["fantasy_score"])]
    ranked.sort(key=lambda record: record["fantasy_score"], reverse=descending)
    previous = None
    rank = 0
    for index, record in enumerate(ranked, start=1):
        score = record["fantasy_score"]
        if previous is None or (score < previous if descending else score > previous):
            rank = index
        record["weekly_rank"] = rank
        previous = score
    return ranked


def _fpts_rows(season=None, week=None):
    requested = season is not None and week is not None
    if requested:
        season, defense_week, note = defense_snapshot_for(season, week)
        slate_week = int(week)
    else:
        season, defense_week, note = matchup_context()
        slate_week = season_status()["current_week"]
    if defense_week is None:
        scored = analyze_snapshot(pd.DataFrame())
    else:
        scored = analyze_snapshot(league_table(season, defense_week))
    if not scored.empty:
        scored = scored.loc[scored["metric"] == "FPTS"]
    return season, defense_week, slate_week, note, scored, requested


def _records(scored, season, defense_week, slate_week, note, position=None, requested=False):
    lookup = {
        (row["team_abbr"], row["position"]): row
        for _, row in scored.iterrows()
    }
    positions = (position,) if position else POSITIONS
    sides = _weekly_sides(season, slate_week) if requested else _weekly_sides()
    records = []
    for pair in sides.itertuples(index=False):
        for pos in positions:
            row = lookup.get((pair.defense, pos))
            if row is None:
                continue
            z_score = float(row["z_score"])
            records.append({
                "offense": pair.offense,
                "defense": pair.defense,
                "position": pos,
                "fpts_allowed": float(row["metric_value"]),
                "league_mean": float(row["league_mean"]),
                "fpts_z_score": z_score,
                "fantasy_score": z_score,
                "defensive_fpts_rank": int(row["rank"]),
                "label": row["label"],
                "season": season,
                "snapshot_week": defense_week,
                "week": slate_week,
                "note": note,
            })
    return records


def rank_weekly_fantasy_matchups(descending=True, season=None, week=None):
    season, defense_week, slate_week, note, scored, requested = _fpts_rows(season, week)
    return _rank(
        _records(scored, season, defense_week, slate_week, note, requested=requested),
        descending,
    )


def rank_weekly_fantasy_position(position, season=None, week=None):
    position = position.lower()
    if position not in POSITIONS:
        raise ValueError(f"unknown position {position}")
    season, defense_week, slate_week, note, scored, requested = _fpts_rows(season, week)
    return _rank(
        _records(scored, season, defense_week, slate_week, note, position, requested),
        descending=True,
    )


def get_fantasy_offense_matchup(team, position):
    team = canonical_abbr(team)
    position = position.lower()
    if position not in POSITIONS:
        raise ValueError(f"unknown position {position}")
    if team_on_bye(team):
        return {"bye": True, "offense": team, "position": position}
    found = [
        record for record in rank_weekly_fantasy_position(position)
        if record["offense"] == team
    ]
    if not found:
        return {"bye": True, "offense": team, "position": position}
    return found[0]
