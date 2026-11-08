import sqlite3
from pathlib import Path

import pandas as pd

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


def initialize_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        schema = SCHEMA_PATH.read_text()
        conn.executescript(schema)


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


def save_schedule(df, season):
    initialize_database()
    payload = df.reindex(columns=SCHEDULE_COLUMNS).copy()
    payload["season"] = str(season)
    for column in ("game_id", "game_type", "gameday", "gametime", "away_team", "home_team"):
        payload[column] = payload[column].map(lambda value: None if pd.isna(value) else str(value))
    placeholders = ", ".join("?" for _ in SCHEDULE_COLUMNS)
    sql = f"INSERT INTO schedule ({', '.join(SCHEDULE_COLUMNS)}) VALUES ({placeholders})"
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM schedule WHERE season = ?", (str(season),))
        conn.executemany(sql, _rows(payload, SCHEDULE_COLUMNS))


if __name__ == "__main__":
    initialize_database()