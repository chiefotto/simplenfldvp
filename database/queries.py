import sqlite3

import pandas as pd

from database.analysis import RESULT_COLUMNS, analyze_snapshot
from database.storage import DB_PATH, STAT_COLUMNS

LATEST_DVP = """
SELECT * FROM raw_dvp
WHERE season = (SELECT MAX(season) FROM raw_dvp)
  AND week = (
      SELECT MAX(week) FROM raw_dvp
      WHERE season = (SELECT MAX(season) FROM raw_dvp)
  )
"""


def latest_dvp():
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql(LATEST_DVP, conn)


def season_status():
    with sqlite3.connect(DB_PATH) as conn:
        dvp_season, dvp_week = conn.execute(
            """
            SELECT season, MAX(week)
            FROM raw_dvp
            WHERE season = (SELECT MAX(season) FROM raw_dvp)
            """
        ).fetchone()
        weeks = conn.execute(
            """
            SELECT week,
                   SUM(away_score IS NULL OR home_score IS NULL) AS unscored
            FROM schedule
            WHERE season = (SELECT MAX(season) FROM schedule)
            GROUP BY week
            ORDER BY week
            """
        ).fetchall()
    current_week = None
    for week, unscored in weeks:
        if unscored:
            current_week = week
            break
    if current_week is None and weeks:
        current_week = weeks[-1][0]
    return {
        "dvp_season": dvp_season,
        "dvp_week": dvp_week,
        "current_week": current_week,
    }


def known_team_abbrs():
    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("SELECT DISTINCT team_abbr FROM raw_dvp").fetchall()
    return {row[0] for row in rows}


def current_schedule():
    status = season_status()
    if status["current_week"] is None:
        return pd.DataFrame(columns=["gameday", "gametime", "away_team", "away_score", "home_team", "home_score"])
    with sqlite3.connect(DB_PATH) as conn:
        season = conn.execute("SELECT MAX(season) FROM schedule").fetchone()[0]
        return pd.read_sql(
            """
            SELECT gameday, gametime, away_team, away_score, home_team, home_score
            FROM schedule
            WHERE season = ? AND week = ?
            ORDER BY gameday, gametime, away_team
            """,
            conn,
            params=(season, status["current_week"]),
        )


def league_table(season, week):
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql(
            "SELECT * FROM raw_dvp WHERE season = ? AND week = ?",
            conn,
            params=(str(season), week),
        )


def _ordered_scores(scored, team=None):
    if scored.empty:
        return scored
    if team:
        scored = scored.loc[scored["team_abbr"] == team]
        return scored.sort_values(["position", "rank", "metric"]).reset_index(drop=True)
    return scored.sort_values(["position", "metric", "rank"]).reset_index(drop=True)


def normalized_defense(team=None, position=None):
    status = season_status()
    if status["dvp_week"] is None:
        return pd.DataFrame(columns=RESULT_COLUMNS)
    scored = analyze_snapshot(league_table(status["dvp_season"], status["dvp_week"]), position)
    return _ordered_scores(scored, team)


def defense_table(team=None, position=None):
    status = season_status()
    if status["dvp_week"] is None:
        return pd.DataFrame()
    sql = "SELECT * FROM raw_dvp WHERE season = ? AND week = ?"
    params = [status["dvp_season"], status["dvp_week"]]
    if team:
        sql += " AND team_abbr = ?"
        params.append(team)
    if position:
        sql += " AND position = ?"
        params.append(position)
    sql += " ORDER BY FPTS DESC"
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql(sql, conn, params=params)


def _dvp_week_exists(season, week):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT 1 FROM raw_dvp WHERE season = ? AND week = ? LIMIT 1",
            (str(season), week),
        ).fetchone()
    return row is not None


def matchup_context():
    status = season_status()
    current = status["current_week"]
    latest = status["dvp_week"]
    season = status["dvp_season"]
    if current is None or latest is None:
        return season, latest, None
    target = int(current) - 1
    if _dvp_week_exists(season, target):
        return season, target, None
    return season, int(latest), f"showing week {int(latest)} defense for week {int(current)} games"


def team_on_bye(team):
    status = season_status()
    if status["current_week"] is None:
        return False
    with sqlite3.connect(DB_PATH) as conn:
        season = conn.execute("SELECT MAX(season) FROM schedule").fetchone()[0]
        found = conn.execute(
            """
            SELECT 1 FROM schedule
            WHERE season = ? AND week = ? AND (away_team = ? OR home_team = ?)
            """,
            (season, status["current_week"], team, team),
        ).fetchone()
    return found is None


def matchups_table(team=None, position=None):
    status = season_status()
    season, defense_week, _note = matchup_context()
    if status["current_week"] is None or defense_week is None:
        return pd.DataFrame(columns=["offense", "defense", "position", *STAT_COLUMNS])
    with sqlite3.connect(DB_PATH) as conn:
        schedule_season = conn.execute("SELECT MAX(season) FROM schedule").fetchone()[0]
        games = pd.read_sql(
            """
            SELECT away_team, home_team
            FROM schedule
            WHERE season = ? AND week = ?
            ORDER BY gameday, gametime, away_team
            """,
            conn,
            params=(schedule_season, status["current_week"]),
        )
        defense = pd.read_sql(
            """
            SELECT team_abbr, position, season, week, {stats}
            FROM raw_dvp
            WHERE season = ? AND week = ?
            """.format(stats=", ".join(STAT_COLUMNS)),
            conn,
            params=(str(season), defense_week),
        )
    if team:
        games = games[(games["away_team"] == team) | (games["home_team"] == team)]
    sides = pd.concat(
        [
            games.rename(columns={"away_team": "offense", "home_team": "defense"}),
            games.rename(columns={"home_team": "offense", "away_team": "defense"}),
        ],
        ignore_index=True,
    )
    merged = sides.merge(defense, left_on="defense", right_on="team_abbr", how="inner")
    if position:
        merged = merged[merged["position"] == position]
    columns = ["offense", "defense", "position", "season", "week", *STAT_COLUMNS]
    return merged[columns].sort_values(["offense", "position"]).reset_index(drop=True)


def normalized_matchups(team=None, position=None):
    status = season_status()
    season, defense_week, _note = matchup_context()
    columns = ["offense", "defense", *RESULT_COLUMNS]
    if status["current_week"] is None or defense_week is None:
        return pd.DataFrame(columns=columns)
    scored = analyze_snapshot(league_table(season, defense_week), position)
    with sqlite3.connect(DB_PATH) as conn:
        schedule_season = conn.execute("SELECT MAX(season) FROM schedule").fetchone()[0]
        games = pd.read_sql(
            """
            SELECT away_team, home_team
            FROM schedule
            WHERE season = ? AND week = ?
            ORDER BY gameday, gametime, away_team
            """,
            conn,
            params=(schedule_season, status["current_week"]),
        )
    if team:
        games = games[(games["away_team"] == team) | (games["home_team"] == team)]
    sides = pd.concat(
        [
            games.rename(columns={"away_team": "offense", "home_team": "defense"}),
            games.rename(columns={"home_team": "offense", "away_team": "defense"}),
        ],
        ignore_index=True,
    )
    merged = sides.merge(scored, left_on="defense", right_on="team_abbr", how="inner")
    order = ["offense", "position", "rank", "metric"] if team else ["position", "metric", "rank", "offense"]
    return merged[columns].sort_values(order).reset_index(drop=True)
