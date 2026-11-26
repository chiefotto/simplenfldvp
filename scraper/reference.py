import argparse
import logging
import sqlite3
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

from database.storage import DB_PATH
from nfl_data import ingest_reference_data

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def format_reference_result(result):
    lines = []
    for name in ("depth", "stats", "snaps"):
        status = result.get(name) or {}
        line = (
            f"{name}: {status.get('status', 'missing')} "
            f"downloaded={status.get('downloaded', 0)} "
            f"prepared={status.get('prepared', 0)} "
            f"written={status.get('written', 0)}"
        )
        if status.get("unmatched"):
            line += f" unmatched={status['unmatched']}"
        if status.get("error"):
            line += f" error={status['error']}"
        lines.append(line)
    lines.append(
        "rosters={rosters_written} players={players_written} teams={teams_written}".format(**result)
    )
    if result.get("roster_warning"):
        lines.append(f"roster warning: {result['roster_warning']}")
    if result.get("player_warning"):
        lines.append(f"player warning: {result['player_warning']}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Refresh roster, depth chart, stat, and snap reference data.")
    parser.add_argument("--season", required=True, type=int)
    result = ingest_reference_data(parser.parse_args().season)
    print(format_reference_result(result))
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        print("integrity", conn.execute("PRAGMA integrity_check").fetchone()[0])
    failed = [
        name for name in ("depth", "stats", "snaps")
        if (result.get(name) or {}).get("status") != "written"
    ]
    if failed:
        raise SystemExit(f"player refresh incomplete: {', '.join(failed)}")


if __name__ == "__main__":
    main()
