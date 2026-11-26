import argparse
import sqlite3

from database.queries import defense_snapshot_for
from database.storage import DB_PATH, initialize_database

SKILL = ("qb", "rb", "wr", "te")
ACTIVE = ("ACT", "ACTIVE")


def _count(conn, sql, params=()):
    row = conn.execute(sql, params).fetchone()
    return 0 if row is None or row[0] is None else row[0]


def _source(status, detail):
    return {"status": status, "detail": detail}


def data_revision(season):
    initialize_database()
    season = str(season)
    with sqlite3.connect(DB_PATH) as conn:
        stats = _count(conn, "SELECT COUNT(*) FROM player_weekly_stats WHERE season = ?", (season,))
        stat_week = _count(conn, "SELECT MAX(week) FROM player_weekly_stats WHERE season = ?", (season,))
        snaps = _count(conn, "SELECT COUNT(*) FROM player_snap_counts WHERE season = ?", (season,))
        mapped = _count(conn, "SELECT COUNT(*) FROM player_snap_counts WHERE season = ? AND player_id IS NOT NULL", (season,))
        depth = _count(conn, "SELECT COUNT(*) FROM depth_charts WHERE season = ?", (season,))
        observed = conn.execute("SELECT MAX(observed_at) FROM depth_charts WHERE season = ?", (season,)).fetchone()[0]
    return f"stats={stats}:{stat_week};snaps={snaps}:{mapped};depth={depth}:{observed}"


def player_data_health(season, week):
    initialize_database()
    season = str(season)
    week = int(week)
    with sqlite3.connect(DB_PATH) as conn:
        schedule_games = _count(conn, "SELECT COUNT(*) FROM schedule WHERE season = ? AND week = ?", (season, week))
        roster_rows = _count(
            conn,
            "SELECT COUNT(*) FROM weekly_rosters WHERE season = ? AND week = ? AND position IN ({})".format(",".join("?" * len(SKILL))),
            (season, week, *SKILL),
        )
        eligible = _count(
            conn,
            """
            SELECT COUNT(*) FROM weekly_rosters
            WHERE season = ? AND week = ? AND position IN ({}) AND roster_status IN ({})
            """.format(",".join("?" * len(SKILL)), ",".join("?" * len(ACTIVE))),
            (season, week, *SKILL, *ACTIVE),
        )
        roster_week = _count(conn, "SELECT MAX(week) FROM weekly_rosters WHERE season = ? AND week <= ?", (season, week))
        depth_rows = _count(conn, "SELECT COUNT(*) FROM depth_charts WHERE season = ?", (season,))
        latest_chart = conn.execute("SELECT MAX(observed_at) FROM depth_charts WHERE season = ?", (season,)).fetchone()[0]
        stat_rows = _count(conn, "SELECT COUNT(*) FROM player_weekly_stats WHERE season = ?", (season,))
        stat_week = conn.execute("SELECT MAX(week) FROM player_weekly_stats WHERE season = ? AND week < ?", (season, week)).fetchone()[0]
        prior_players = _count(
            conn,
            """
            SELECT COUNT(DISTINCT player_id) FROM player_weekly_stats
            WHERE season = ? AND week < ?
            """,
            (season, week),
        )
        covered = _count(
            conn,
            """
            SELECT COUNT(DISTINCT roster.player_id)
            FROM weekly_rosters AS roster
            JOIN player_weekly_stats AS stats
              ON stats.player_id = roster.player_id AND stats.season = roster.season AND stats.week < ?
            WHERE roster.season = ? AND roster.week = ? AND roster.position IN ({})
              AND roster.roster_status IN ({})
            """.format(",".join("?" * len(SKILL)), ",".join("?" * len(ACTIVE))),
            (week, season, week, *SKILL, *ACTIVE),
        )
        snap_rows = _count(conn, "SELECT COUNT(*) FROM player_snap_counts WHERE season = ?", (season,))
        snap_mapped = _count(
            conn,
            "SELECT COUNT(*) FROM player_snap_counts WHERE season = ? AND player_id IS NOT NULL",
            (season,),
        )
    snapshot_season, snapshot_week, snapshot_note = defense_snapshot_for(season, week)
    if schedule_games:
        schedule = _source("Available", f"{schedule_games} games in week {week}.")
    else:
        schedule = _source("Missing", "This week is not on the stored schedule.")
    if roster_rows and roster_week == week:
        roster = _source("Available", f"Week {roster_week} roster, {eligible} active skill players.")
    elif roster_rows:
        roster = _source("Stale", f"Using roster week {roster_week} for week {week}.")
    else:
        roster = _source("Missing", "No roster is stored for this season.")
    if snapshot_week is None:
        defense = _source("Missing", "No defensive snapshot is available before this week.")
    elif week - int(snapshot_week) > 2:
        defense = _source("Stale", snapshot_note or f"Latest defense week is {snapshot_week}.")
    elif snapshot_note:
        defense = _source("Partial", snapshot_note)
    else:
        defense = _source("Available", f"Defense snapshot week {snapshot_week}.")
    if not depth_rows:
        depth = _source("Missing", "No depth charts are stored for this season.")
    else:
        depth = _source("Available", f"Latest observation {latest_chart}.")
    if not stat_rows:
        stats = _source("Missing", "Weekly player stats have not been ingested.")
    elif stat_week is None:
        stats = _source("Missing", "No player stats are available before this week.")
    elif week - int(stat_week) > 2:
        stats = _source("Stale", f"Latest player stat week before this game is {int(stat_week)}.")
    elif eligible and covered / eligible < 0.5:
        stats = _source("Partial", f"{covered} of {eligible} active skill players have a prior game.")
    else:
        stats = _source("Available", f"Player stats through week {int(stat_week)}. {covered} of {eligible} active skill players have a prior game.")
    if not snap_rows:
        snaps = _source("Missing", "Snap counts have not been ingested.")
    else:
        rate = snap_mapped / snap_rows
        detail = f"{snap_mapped} of {snap_rows} snap rows have a GSIS id."
        snaps = _source("Available" if rate >= 0.8 else "Partial", detail)
    if not eligible or not stat_rows:
        baselines = _source("Missing", "Adjusted estimates need stored player stats from earlier weeks.")
    else:
        share = covered / eligible
        detail = f"{covered} of {eligible} active skill players have a baseline before week {week}."
        if share >= 0.5:
            baselines = _source("Available", detail)
        elif share > 0:
            baselines = _source("Partial", detail)
        else:
            baselines = _source("Missing", detail)
    warning = None
    if stats["status"] == "Missing":
        warning = "Player stats are not in the database yet, so averages and adjusted estimates are unavailable. Defensive matchup scores are unchanged."
    elif stats["status"] in {"Partial", "Stale"} or baselines["status"] in {"Partial", "Missing"}:
        warning = "Player history is incomplete for this week, so some averages and adjusted estimates are missing. Defensive matchup scores are unchanged."
    elif depth["status"] == "Missing":
        warning = "No pregame depth chart is stored, so numbered roles are based on recent usage when that usage exists."
    return {
        "season": snapshot_season or season,
        "week": week,
        "sources": {
            "schedule": schedule,
            "defense": defense,
            "roster": roster,
            "depth": depth,
            "stats": stats,
            "snaps": snaps,
            "baselines": baselines,
        },
        "player_warning": warning,
        "prior_players": prior_players,
    }


def format_health_report(health):
    lines = [f"Player data health {health['season']} week {health['week']}"]
    for key, source in health["sources"].items():
        lines.append(f"{key}: {source['status']} — {source['detail']}")
    if health.get("player_warning"):
        lines.append(health["player_warning"])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Report stored player-data coverage for one slate.")
    parser.add_argument("--season", required=True)
    parser.add_argument("--week", required=True, type=int)
    args = parser.parse_args()
    print(format_health_report(player_data_health(args.season, args.week)))


if __name__ == "__main__":
    main()
