import logging
import sqlite3
from pathlib import Path

import pandas as pd

from database.abbreviations import canonical_abbr

logger = logging.getLogger("database.storage")

BASE_DIR = Path(__file__).resolve().parent.parent

DB_PATH = BASE_DIR / "data" / "nfl_stats.db"
SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"

STAT_COLUMNS = [
    "Passing_Att", "Passing_Cmp", "Passing_Yd", "Passing_TD", "Passing_Int", "Passing_Rate",
    "Rushing_Att", "Rushing_Yd", "Rushing_Avg", "Rushing_TD",
    "FL", "FPTS",
    "Receiving_Targt", "Receiving_Recpt", "Receiving_Yd", "Receiving_Avg", "Receiving_TD",
]
SCHEDULE_COLUMNS = [
    "game_id", "season", "week", "game_type", "gameday", "gametime",
    "away_team", "home_team", "away_score", "home_score",
]
DVP_KEY = {"season", "week", "team", "position"}


def _rows(df, columns):
    payload = df.reindex(columns=columns)
    return [
        tuple(None if pd.isna(value) else value for value in row)
        for row in payload.itertuples(index=False, name=None)
    ]


def _ensure_player_id_columns(conn):
    existing = {row[1] for row in conn.execute("PRAGMA table_info(players)")}
    for name in ("pfr_id", "espn_id"):
        if name not in existing:
            conn.execute(f"ALTER TABLE players ADD COLUMN {name} TEXT")


def initialize_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        schema = SCHEMA_PATH.read_text()
        conn.executescript(schema)
        _ensure_player_id_columns(conn)


def save_dvp(df):
    initialize_database()
    columns = ["season", "week", "team", "team_abbr", "position", *STAT_COLUMNS]
    assignments = ", ".join(
        f"{name}=excluded.{name}" for name in columns if name not in DVP_KEY
    )
    sql = f"""
        INSERT INTO raw_dvp ({", ".join(columns)})
        VALUES ({", ".join("?" for _ in columns)})
        ON CONFLICT(season, week, team, position) DO UPDATE SET
            {assignments},
            updated_at=CURRENT_TIMESTAMP
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(sql, _rows(df, columns))


def _text_column(series):
    return series.map(lambda value: None if pd.isna(value) else str(value))


def save_schedule(df, season):
    initialize_database()
    if df is None or df.empty:
        logger.warning("skipping empty schedule for %s", season)
        return 0
    payload = df.reindex(columns=SCHEDULE_COLUMNS).copy()
    payload["season"] = str(season)
    for column in ("game_id", "game_type", "gameday", "gametime", "away_team", "home_team"):
        payload[column] = _text_column(payload[column])
    payload["away_team"] = payload["away_team"].map(canonical_abbr)
    payload["home_team"] = payload["home_team"].map(canonical_abbr)
    payload = payload.dropna(subset=["game_id", "away_team", "home_team"])
    if payload.empty:
        logger.warning("skipping schedule for %s with no valid games", season)
        return 0
    placeholders = ", ".join("?" for _ in SCHEDULE_COLUMNS)
    sql = f"INSERT INTO schedule ({', '.join(SCHEDULE_COLUMNS)}) VALUES ({placeholders})"
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM schedule WHERE season = ?", (str(season),))
        conn.executemany(sql, _rows(payload, SCHEDULE_COLUMNS))
    return len(payload)


def _upsert(table, columns, key_columns, df, preserve_nulls=()):
    initialize_database()
    if df is None or df.empty:
        logger.warning("skipping empty %s write", table)
        return 0
    payload = df.reindex(columns=columns).copy()
    payload = payload.dropna(subset=list(key_columns))
    if payload.empty:
        logger.warning("skipping %s write with no valid keys", table)
        return 0
    assignments = []
    for name in columns:
        if name in key_columns:
            continue
        if name in preserve_nulls:
            assignments.append(f"{name}=COALESCE(excluded.{name}, {table}.{name})")
        else:
            assignments.append(f"{name}=excluded.{name}")
    assignments.append("updated_at=CURRENT_TIMESTAMP")
    conflict = ", ".join(key_columns)
    sql = f"""
        INSERT INTO {table} ({", ".join(columns)})
        VALUES ({", ".join("?" for _ in columns)})
        ON CONFLICT({conflict}) DO UPDATE SET
            {", ".join(assignments)}
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(sql, _rows(payload, columns))
    return len(payload)


def save_teams(df):
    columns = ["team_abbr", "team_name", "team_logo_url", "color_primary", "color_secondary"]
    return _upsert("teams", columns, ["team_abbr"], df, preserve_nulls=("team_logo_url", "color_primary", "color_secondary"))


def save_players(df):
    columns = ["player_id", "player_name", "position", "headshot_url", "pfr_id", "espn_id"]
    return _upsert(
        "players",
        columns,
        ["player_id"],
        df,
        preserve_nulls=("position", "headshot_url", "pfr_id", "espn_id"),
    )


def save_depth_charts(df):
    columns = [
        "season", "observed_at", "week", "team", "player_id", "player_name",
        "position", "pos_abb", "pos_slot", "pos_rank",
    ]
    return _upsert(
        "depth_charts",
        columns,
        ["season", "observed_at", "team", "player_id", "pos_abb", "pos_slot"],
        df,
        preserve_nulls=("player_name", "week"),
    )


def save_player_stats(df):
    columns = [
        "season", "week", "player_id", "player_name", "team", "position", "game_id",
        "attempts", "passing_yards", "passing_tds", "carries", "rushing_yards", "rushing_tds",
        "targets", "receptions", "receiving_yards", "receiving_tds",
    ]
    return _upsert(
        "player_weekly_stats",
        columns,
        ["season", "week", "player_id"],
        df,
        preserve_nulls=("player_name", "position", "game_id"),
    )


def save_snap_counts(df):
    columns = [
        "season", "week", "team", "pfr_player_id", "player_id", "game_id",
        "position", "offense_snaps", "offense_pct",
    ]
    return _upsert(
        "player_snap_counts",
        columns,
        ["season", "week", "team", "pfr_player_id"],
        df,
        preserve_nulls=("player_id", "game_id", "position"),
    )


def save_rosters(df):
    columns = [
        "season", "week", "player_id", "player_name", "team", "position",
        "roster_status", "jersey_number", "headshot_url",
    ]
    return _upsert(
        "weekly_rosters",
        columns,
        ["season", "week", "player_id"],
        df,
        preserve_nulls=("roster_status", "jersey_number", "headshot_url"),
    )


if __name__ == "__main__":
    initialize_database()