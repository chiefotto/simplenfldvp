from datetime import date

import nflreadpy as nfl
import pandas as pd

SCHEDULE_COLUMNS = [
    "game_id", "season", "week", "game_type", "gameday", "gametime",
    "away_team", "home_team", "away_score", "home_score",
]


def season_year(today=None):
    today = today or date.today()
    return today.year if today.month >= 3 else today.year - 1


def load_schedule(season):
    raw = nfl.load_schedules([season])
    regular = raw.filter(raw["game_type"] == "REG").select(SCHEDULE_COLUMNS)
    table = pd.DataFrame(regular.to_dicts())
    table["season"] = table["season"].astype(int)
    return table


def completed_week(schedule, season):
    games = schedule.loc[schedule["season"] == season]
    finished = []
    for week, week_games in games.groupby("week"):
        scores_in = week_games["away_score"].notna() & week_games["home_score"].notna()
        if scores_in.all() and not week_games.empty:
            finished.append(int(week))
    if not finished:
        return None
    return max(finished)
