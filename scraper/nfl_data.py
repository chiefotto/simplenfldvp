import logging

import pandas as pd

from database.abbreviations import canonical_abbr, log_unknown_abbreviations
from database.storage import save_players, save_rosters, save_teams

logger = logging.getLogger("scraper.nfl_data")

SKILL_POSITIONS = {"QB", "RB", "WR", "TE"}


def _as_pandas(raw):
    if raw is None:
        return pd.DataFrame()
    if isinstance(raw, pd.DataFrame):
        return raw.copy()
    if hasattr(raw, "to_pandas"):
        return raw.to_pandas()
    raise TypeError(f"unsupported frame type {type(raw).__name__}")


def _text(value):
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "<na>"}:
        return None
    if text.endswith(".0") and text[:-2].lstrip("-").isdigit():
        text = text[:-2]
    return text


def _first(row, names):
    for name in names:
        if name in row and _text(row[name]) is not None:
            return row[name]
    return None


def prepare_rosters(raw):
    frame = _as_pandas(raw)
    required = {"season", "week", "gsis_id", "team", "position"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"roster frame missing {', '.join(sorted(missing))}")
    if frame.empty:
        return frame
    rows = []
    for record in frame.to_dict(orient="records"):
        position = _text(record.get("position"))
        if position is None or position.upper() not in SKILL_POSITIONS:
            continue
        player_id = _text(record.get("gsis_id"))
        team = canonical_abbr(_text(record.get("team")))
        name = _text(_first(record, ("full_name", "player_name", "display_name", "football_name")))
        week = _text(record.get("week"))
        season = _text(record.get("season"))
        if not player_id or not team or not name or week is None or season is None:
            continue
        rows.append({
            "season": season,
            "week": int(week),
            "player_id": player_id,
            "player_name": name,
            "team": team,
            "position": position.lower(),
            "roster_status": _text(_first(record, ("status", "roster_status"))),
            "jersey_number": _text(record.get("jersey_number")),
            "headshot_url": _text(_first(record, ("headshot_url", "headshot"))),
        })
    prepared = pd.DataFrame(rows)
    if prepared.empty:
        return prepared
    duplicate_count = int(prepared.duplicated(["season", "week", "player_id"]).sum())
    if duplicate_count:
        logger.warning("dropped %s duplicate roster rows", duplicate_count)
    prepared = prepared.drop_duplicates(["season", "week", "player_id"], keep="last")
    log_unknown_abbreviations(prepared["team"])
    return prepared.reset_index(drop=True)


def prepare_players(raw):
    frame = _as_pandas(raw)
    if frame.empty or "gsis_id" not in frame.columns:
        return pd.DataFrame(columns=["player_id", "player_name", "position", "headshot_url"])
    rows = []
    for record in frame.to_dict(orient="records"):
        player_id = _text(record.get("gsis_id"))
        name = _text(_first(record, ("display_name", "full_name", "player_name", "football_name")))
        if not player_id or not name:
            continue
        position = _text(record.get("position"))
        rows.append({
            "player_id": player_id,
            "player_name": name,
            "position": None if position is None else position.lower(),
            "headshot_url": _text(_first(record, ("headshot_url", "headshot"))),
        })
    prepared = pd.DataFrame(rows)
    if prepared.empty:
        return prepared
    return prepared.drop_duplicates("player_id", keep="last").reset_index(drop=True)


def prepare_teams(raw):
    frame = _as_pandas(raw)
    if frame.empty or "team_abbr" not in frame.columns:
        return pd.DataFrame(columns=["team_abbr", "team_name", "team_logo_url", "color_primary", "color_secondary"])
    rows = []
    for record in frame.to_dict(orient="records"):
        source = _text(record.get("team_abbr"))
        abbr = canonical_abbr(source)
        name = _text(_first(record, ("team_name", "team_nick")))
        if not abbr or not name:
            continue
        if source != abbr and abbr in {row["team_abbr"] for row in rows}:
            continue
        rows.append({
            "team_abbr": abbr,
            "team_name": name,
            "team_logo_url": _text(_first(record, ("team_logo_espn", "team_logo_wikipedia", "team_logo_url"))),
            "color_primary": _text(_first(record, ("team_color", "color_primary"))),
            "color_secondary": _text(_first(record, ("team_color2", "color_secondary"))),
            "_source": source,
        })
    prepared = pd.DataFrame(rows)
    if prepared.empty:
        return prepared.drop(columns=["_source"], errors="ignore")
    prepared["_preferred"] = prepared["_source"] == prepared["team_abbr"]
    prepared = prepared.sort_values("_preferred").drop_duplicates("team_abbr", keep="last")
    log_unknown_abbreviations(prepared["team_abbr"])
    return prepared.drop(columns=["_source", "_preferred"]).reset_index(drop=True)


def players_from_rosters(rosters):
    if rosters is None or rosters.empty:
        return pd.DataFrame(columns=["player_id", "player_name", "position", "headshot_url"])
    players = rosters[["player_id", "player_name", "position", "headshot_url"]].copy()
    return players.drop_duplicates("player_id", keep="last").reset_index(drop=True)


def ingest_reference_data(season, loaders=None):
    import nflreadpy as nfl

    loaders = loaders or {}
    load_rosters = loaders.get("rosters", nfl.load_rosters_weekly)
    load_players = loaders.get("players", nfl.load_players)
    load_teams = loaders.get("teams", nfl.load_teams)
    result = {
        "rosters_written": 0,
        "players_written": 0,
        "teams_written": 0,
        "roster_warning": None,
    }
    try:
        teams = prepare_teams(load_teams())
        result["teams_written"] = save_teams(teams)
    except Exception as error:
        logger.error("team ingestion failed: %s", error)
        result["roster_warning"] = str(error)
    try:
        players = prepare_players(load_players())
        result["players_written"] = save_players(players)
    except Exception as error:
        logger.error("player ingestion failed: %s", error)
        result["roster_warning"] = str(error)
    try:
        rosters = prepare_rosters(load_rosters([int(season)]))
        if rosters.empty:
            logger.warning("roster download for %s was empty; stored rosters were left unchanged", season)
            result["roster_warning"] = result["roster_warning"] or f"no roster rows for {season}"
        else:
            result["rosters_written"] = save_rosters(rosters)
            result["players_written"] += save_players(players_from_rosters(rosters))
    except Exception as error:
        logger.error("roster ingestion failed: %s", error)
        result["roster_warning"] = str(error)
    logger.info(
        "reference data season=%s teams=%s players=%s rosters=%s",
        season,
        result["teams_written"],
        result["players_written"],
        result["rosters_written"],
    )
    return result
