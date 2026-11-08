import sys
from pathlib import Path

import pandas as pd
from fetch import fetch_html
from parse import parse_table
from schedule import completed_week, load_schedule, season_year

sys.path.append(str(Path(__file__).resolve().parent.parent))
from database.storage import save_dvp, save_schedule

URLS = {
    "qb": "https://www.cbssports.com/fantasy/football/stats/posvsdef/QB/all/avg/standard",
    "rb": "https://www.cbssports.com/fantasy/football/stats/posvsdef/RB/ALL/avg/standard",
    "wr": "https://www.cbssports.com/fantasy/football/stats/posvsdef/WR/ALL/avg/standard",
    "te": "https://www.cbssports.com/fantasy/football/stats/posvsdef/TE/ALL/avg/standard",
}

def load_current_snapshot():
    season = season_year()
    schedule = load_schedule(season)
    week = completed_week(schedule, season)
    if week is None:
        raise RuntimeError(f"no completed regular-season week for {season}")

    frames = []
    for url in URLS.values():
        html = fetch_html(url)
        frames.append(parse_table(html))

    df = pd.concat(frames, ignore_index=True)
    df["season"] = str(season)
    df["week"] = week
    save_schedule(schedule, season)
    save_dvp(df)
    return {
        "season": season,
        "week": week,
        "positions_updated": ["qb", "rb", "wr", "te"],
        "rows_written": len(df),
        "games_written": len(schedule),
    }


def main():
    try:
        result = load_current_snapshot()
    except RuntimeError as error:
        raise SystemExit(str(error)) from error
    print(
        f"saved {result['season']} week {result['week']}: "
        f"{result['rows_written']} dvp rows, {result['games_written']} games"
    )


if __name__ == "__main__":
    main()
