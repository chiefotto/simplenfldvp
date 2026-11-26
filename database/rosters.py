import sqlite3

import pandas as pd

from database.abbreviations import canonical_abbr
from database.storage import DB_PATH, initialize_database


def _records(frame):
    if frame is None or frame.empty:
        return []
    rows = []
    for record in frame.to_dict(orient="records"):
        cleaned = {}
        for key, value in record.items():
            if value is None or pd.isna(value):
                cleaned[key] = None
            else:
                cleaned[key] = value
        rows.append(cleaned)
    return rows


def roster_for(season, week, team=None, position=None):
    initialize_database()
    requested = None if week is None else int(week)
    with sqlite3.connect(DB_PATH) as conn:
        if requested is None:
            found = None
        else:
            found = conn.execute(
                """
                SELECT MAX(week) FROM weekly_rosters
                WHERE season = ? AND week <= ?
                """,
                (str(season), requested),
            ).fetchone()[0]
        if found is None:
            return {
                "players": [],
                "roster_week": None,
                "roster_note": "Roster information is unavailable for this week.",
            }
        sql = """
            SELECT season, week, player_id, player_name, team, position,
                   roster_status, jersey_number, headshot_url
            FROM weekly_rosters
            WHERE season = ? AND week = ?
        """
        params = [str(season), int(found)]
        if team:
            sql += " AND team = ?"
            params.append(canonical_abbr(team))
        if position:
            sql += " AND position = ?"
            params.append(str(position).lower())
        sql += " ORDER BY player_name, player_id"
        frame = pd.read_sql(sql, conn, params=params)
    note = None
    if requested is not None and int(found) != requested:
        note = f"showing week {int(found)} roster for week {requested}"
    return {"players": _records(frame), "roster_week": int(found), "roster_note": note}


def team_directory():
    initialize_database()
    with sqlite3.connect(DB_PATH) as conn:
        frame = pd.read_sql(
            """
            SELECT team_abbr, team_name, team_logo_url, color_primary, color_secondary
            FROM teams
            ORDER BY team_abbr
            """,
            conn,
        )
    return {row["team_abbr"]: row for row in _records(frame)}
