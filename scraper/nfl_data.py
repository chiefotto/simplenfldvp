import logging

import pandas as pd

from database.abbreviations import canonical_abbr, log_unknown_abbreviations
from database.storage import save_players, save_rosters, save_teams

logger = logging.getLogger("scraper.nfl_data")

SKILL_POSITIONS = {"QB", "RB", "WR", "TE"}
CHART_POSITIONS = {"QB", "RB", "WR", "TE", "FB"}
STAT_FIELDS = (
    "attempts", "passing_yards", "passing_tds", "carries", "rushing_yards", "rushing_tds",
    "targets", "receptions", "receiving_yards", "receiving_tds",
)


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


def _number(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _integer(value):
    number = _number(value)
    if number is None:
        return None
    return int(number)


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
            "pfr_id": _text(record.get("pfr_id")),
            "espn_id": _text(record.get("espn_id")),
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
    columns = ["player_id", "player_name", "position", "headshot_url", "pfr_id", "espn_id"]
    if rosters is None or rosters.empty:
        return pd.DataFrame(columns=columns)
    players = rosters.reindex(columns=columns).copy()
    return players.drop_duplicates("player_id", keep="last").reset_index(drop=True)


def _empty_charts():
    return pd.DataFrame(columns=[
        "season", "observed_at", "week", "team", "player_id", "player_name",
        "position", "pos_abb", "pos_slot", "pos_rank",
    ])


def _empty_stats():
    return pd.DataFrame(columns=[
        "season", "week", "player_id", "player_name", "team", "position", "game_id", *STAT_FIELDS,
    ])


def _empty_snaps():
    return pd.DataFrame(columns=[
        "season", "week", "team", "pfr_player_id", "player_id", "game_id",
        "position", "offense_snaps", "offense_pct",
    ])


def _roster_position(abbreviation):
    text = _text(abbreviation)
    if text is None:
        return None
    upper = text.upper()
    if upper == "FB":
        return "rb"
    if upper not in SKILL_POSITIONS:
        return None
    return upper.lower()


def prepare_depth_charts(raw, espn_to_gsis=None, season=None):
    frame = _as_pandas(raw)
    if frame.empty or "team" not in frame.columns or "pos_abb" not in frame.columns:
        return _empty_charts()
    if "dt" not in frame.columns and "week" not in frame.columns:
        raise ValueError("depth chart frame needs dt or week")
    espn_to_gsis = espn_to_gsis or {}
    rows = []
    missing_ids = 0
    for record in frame.to_dict(orient="records"):
        abbreviation = _text(record.get("pos_abb"))
        if abbreviation is None or abbreviation.upper() not in CHART_POSITIONS:
            continue
        position = _roster_position(abbreviation)
        observed = _text(record.get("dt"))
        week = _integer(record.get("week")) if "week" in record else None
        if observed is None and week is not None:
            season_text = _text(record.get("season")) or ""
            observed = f"{season_text}-W{week:02d}"
        player_id = _text(record.get("gsis_id")) or _text(record.get("player_id"))
        if player_id is None:
            player_id = espn_to_gsis.get(_text(record.get("espn_id")))
        team = canonical_abbr(_text(record.get("team")))
        rank = _integer(record.get("pos_rank"))
        slot = _integer(record.get("pos_slot"))
        row_season = _text(record.get("season")) if "season" in record else None
        if row_season is None and season is not None:
            row_season = str(season)
        if row_season is None and observed and observed[:4].isdigit():
            row_season = observed[:4]
        if not player_id or not team or not observed or rank is None or row_season is None or position is None:
            if not player_id and abbreviation and abbreviation.upper() in CHART_POSITIONS:
                missing_ids += 1
            continue
        rows.append({
            "season": row_season,
            "observed_at": observed,
            "week": week,
            "team": team,
            "player_id": player_id,
            "player_name": _text(record.get("player_name")),
            "position": position,
            "pos_abb": abbreviation.upper(),
            "pos_slot": 0 if slot is None else slot,
            "pos_rank": rank,
        })
    if missing_ids:
        logger.warning("dropped %s depth chart rows without a player id", missing_ids)
    prepared = pd.DataFrame(rows)
    if prepared.empty:
        return _empty_charts()
    prepared = prepared.drop_duplicates(
        ["season", "observed_at", "team", "player_id", "pos_abb", "pos_slot"],
        keep="last",
    )
    log_unknown_abbreviations(prepared["team"])
    return prepared.reset_index(drop=True)


def prepare_player_stats(raw):
    frame = _as_pandas(raw)
    required = {"player_id", "season", "week", "team"}
    if frame.empty or not required <= set(frame.columns):
        return _empty_stats()
    work = frame.copy()
    if "season_type" in work.columns:
        work = work.loc[work["season_type"].map(lambda value: (_text(value) or "").upper()) == "REG"]
    work["position"] = work["position"].map(_roster_position) if "position" in work.columns else None
    work = work.loc[work["position"].notna()]
    if work.empty:
        return _empty_stats()
    for column in STAT_FIELDS:
        if column not in work.columns:
            work[column] = None
        work[column] = pd.to_numeric(work[column], errors="coerce")
    work["season"] = work["season"].map(_text)
    work["week"] = work["week"].map(_integer)
    work["player_id"] = work["player_id"].map(_text)
    work["team"] = work["team"].map(lambda value: canonical_abbr(_text(value)))
    name_column = "player_display_name" if "player_display_name" in work.columns else "player_name"
    work["player_name"] = work[name_column].map(_text) if name_column in work.columns else None
    work["game_id"] = work["game_id"].map(_text) if "game_id" in work.columns else None
    work = work.dropna(subset=["season", "week", "player_id", "team"])
    if work.empty:
        return _empty_stats()
    grouped = work.groupby(["season", "week", "player_id"], as_index=False)
    totals = grouped[list(STAT_FIELDS)].sum(min_count=1)
    details = grouped.agg(
        player_name=("player_name", "last"),
        team=("team", "last"),
        position=("position", "last"),
        game_id=("game_id", "last"),
    )
    prepared = totals.merge(details, on=["season", "week", "player_id"], how="left")
    log_unknown_abbreviations(prepared["team"])
    return prepared.reset_index(drop=True)


def prepare_snap_counts(raw, pfr_to_gsis=None):
    frame = _as_pandas(raw)
    if frame.empty or "team" not in frame.columns:
        return _empty_snaps()
    pfr_column = "pfr_player_id" if "pfr_player_id" in frame.columns else "pfr_id" if "pfr_id" in frame.columns else None
    if pfr_column is None or "week" not in frame.columns:
        return _empty_snaps()
    pfr_to_gsis = pfr_to_gsis or {}
    work = frame.copy()
    if "game_type" in work.columns:
        work = work.loc[work["game_type"].map(lambda value: (_text(value) or "").upper()) == "REG"]
    rows = []
    for record in work.to_dict(orient="records"):
        pfr_id = _text(record.get(pfr_column))
        team = canonical_abbr(_text(record.get("team")))
        season = _text(record.get("season"))
        week = _integer(record.get("week"))
        if not pfr_id or not team or season is None or week is None:
            continue
        position = _roster_position(record.get("position"))
        rows.append({
            "season": season,
            "week": week,
            "team": team,
            "pfr_player_id": pfr_id,
            "player_id": pfr_to_gsis.get(pfr_id),
            "game_id": _text(record.get("game_id")),
            "position": position,
            "offense_snaps": _number(record.get("offense_snaps")),
            "offense_pct": _number(record.get("offense_pct")),
        })
    prepared = pd.DataFrame(rows)
    if prepared.empty:
        return _empty_snaps()
    prepared = prepared.drop_duplicates(["season", "week", "team", "pfr_player_id"], keep="last")
    log_unknown_abbreviations(prepared["team"])
    return prepared.reset_index(drop=True)


def _id_maps(players):
    pfr_to_gsis = {}
    espn_to_gsis = {}
    if players is None or players.empty:
        return pfr_to_gsis, espn_to_gsis
    for record in players.to_dict(orient="records"):
        gsis = _text(record.get("player_id") or record.get("gsis_id"))
        if not gsis:
            continue
        pfr_id = _text(record.get("pfr_id"))
        espn_id = _text(record.get("espn_id"))
        if pfr_id:
            pfr_to_gsis[pfr_id] = gsis
        if espn_id:
            espn_to_gsis[espn_id] = gsis
    return pfr_to_gsis, espn_to_gsis


def _stored_id_maps():
    import sqlite3

    from database.storage import DB_PATH, initialize_database

    initialize_database()
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT player_id, pfr_id, espn_id FROM players").fetchall()
    pfr_to_gsis = {}
    espn_to_gsis = {}
    for player_id, pfr_id, espn_id in rows:
        if pfr_id:
            pfr_to_gsis[str(pfr_id)] = player_id
        if espn_id:
            espn_to_gsis[str(espn_id)] = player_id
    return pfr_to_gsis, espn_to_gsis


def ingest_reference_data(season, loaders=None):
    import nflreadpy as nfl

    from database.storage import save_depth_charts, save_player_stats, save_snap_counts

    loaders = loaders or {}
    load_rosters = loaders.get("rosters", nfl.load_rosters_weekly)
    load_players = loaders.get("players", nfl.load_players)
    load_teams = loaders.get("teams", nfl.load_teams)
    load_depth = loaders.get("depth", lambda seasons: nfl.load_depth_charts(seasons))
    load_stats = loaders.get("stats", lambda seasons: nfl.load_player_stats(seasons, summary_level="week"))
    load_snaps = loaders.get("snaps", lambda seasons: nfl.load_snap_counts(seasons))
    result = {
        "rosters_written": 0,
        "players_written": 0,
        "teams_written": 0,
        "depth_written": 0,
        "stats_written": 0,
        "snaps_written": 0,
        "snaps_unmatched": 0,
        "roster_warning": None,
        "player_warning": None,
    }
    prepared_players = pd.DataFrame()
    try:
        teams = prepare_teams(load_teams())
        result["teams_written"] = save_teams(teams)
    except Exception as error:
        logger.error("team ingestion failed: %s", error)
        result["roster_warning"] = str(error)
    try:
        prepared_players = prepare_players(load_players())
        result["players_written"] = save_players(prepared_players)
    except Exception as error:
        logger.error("player ingestion failed: %s", error)
        result["roster_warning"] = str(error)
        prepared_players = pd.DataFrame()
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
    pfr_to_gsis, espn_to_gsis = _id_maps(prepared_players)
    try:
        stored_pfr, stored_espn = _stored_id_maps()
        pfr_to_gsis = {**stored_pfr, **pfr_to_gsis}
        espn_to_gsis = {**stored_espn, **espn_to_gsis}
    except Exception as error:
        logger.error("player id crosswalk failed: %s", error)
    warnings = []
    try:
        charts = prepare_depth_charts(load_depth([int(season)]), espn_to_gsis, season)
        if charts.empty:
            logger.warning("depth chart download for %s was empty; stored charts were left unchanged", season)
            warnings.append(f"no depth chart rows for {season}")
        else:
            result["depth_written"] = save_depth_charts(charts)
    except Exception as error:
        logger.error("depth chart ingestion failed: %s", error)
        warnings.append(str(error))
    try:
        stats = prepare_player_stats(load_stats([int(season)]))
        if stats.empty:
            logger.warning("player stat download for %s was empty; stored stats were left unchanged", season)
            warnings.append(f"no player stat rows for {season}")
        else:
            result["stats_written"] = save_player_stats(stats)
    except Exception as error:
        logger.error("player stat ingestion failed: %s", error)
        warnings.append(str(error))
    try:
        snaps = prepare_snap_counts(load_snaps([int(season)]), pfr_to_gsis)
        if snaps.empty:
            logger.warning("snap count download for %s was empty; stored snaps were left unchanged", season)
            warnings.append(f"no snap rows for {season}")
        else:
            result["snaps_unmatched"] = int(snaps["player_id"].isna().sum())
            result["snaps_written"] = save_snap_counts(snaps)
            if result["snaps_unmatched"]:
                logger.warning("%s snap rows have no GSIS id", result["snaps_unmatched"])
    except Exception as error:
        logger.error("snap count ingestion failed: %s", error)
        warnings.append(str(error))
    if warnings:
        result["player_warning"] = "; ".join(warnings)
    logger.info(
        "reference data season=%s teams=%s players=%s rosters=%s depth=%s stats=%s snaps=%s",
        season,
        result["teams_written"],
        result["players_written"],
        result["rosters_written"],
        result["depth_written"],
        result["stats_written"],
        result["snaps_written"],
    )
    return result
