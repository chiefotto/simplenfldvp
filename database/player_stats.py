import sqlite3

import pandas as pd

from database.storage import initialize_database


def _connect():
    from database.storage import DB_PATH

    initialize_database()
    return sqlite3.connect(DB_PATH)


def _read(sql, params):
    with _connect() as conn:
        return pd.read_sql(sql, conn, params=params)


def weekly_stats(season, before_week=None):
    sql = "SELECT * FROM player_weekly_stats WHERE season = ?"
    params = [str(season)]
    if before_week is not None:
        sql += " AND week < ?"
        params.append(int(before_week))
    return _read(sql, params)


def snap_counts(season, before_week=None):
    sql = """
        SELECT season, week, team, player_id, game_id, position, offense_snaps, offense_pct
        FROM player_snap_counts
        WHERE season = ? AND player_id IS NOT NULL
    """
    params = [str(season)]
    if before_week is not None:
        sql += " AND week < ?"
        params.append(int(before_week))
    return _read(sql, params)


def depth_charts(season):
    return _read(
        """
        SELECT season, observed_at, week, team, player_id, player_name,
               position, pos_abb, pos_slot, pos_rank
        FROM depth_charts
        WHERE season = ?
        """,
        [str(season)],
    )


def schedule_sides(season):
    sql = """
        SELECT week, gameday, gametime, away_team AS team FROM schedule WHERE season = ?
        UNION ALL
        SELECT week, gameday, gametime, home_team AS team FROM schedule WHERE season = ?
    """
    return _read(sql, [str(season), str(season)])


def game_dates(season):
    frame = _read(
        """
        SELECT week, away_team AS team, gameday FROM schedule WHERE season = ?
        UNION ALL
        SELECT week, home_team AS team, gameday FROM schedule WHERE season = ?
        """,
        [str(season), str(season)],
    )
    dates = {}
    for record in frame.to_dict(orient="records"):
        if record.get("gameday") is None or pd.isna(record.get("gameday")):
            continue
        dates[(int(record["week"]), record["team"])] = str(record["gameday"])[:10]
    return dates
