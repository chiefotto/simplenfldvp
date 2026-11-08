from pathlib import Path

import pandas as pd

TEAMS_PATH = Path(__file__).resolve().parent.parent / "nfl_teams.csv"
HISTORICAL_ABBRS = {"OAK", "SD", "STL", "LA"}


def nickname_to_abbr():
    teams = pd.read_csv(TEAMS_PATH, usecols=["team_abbr", "team_nick"])
    current = teams.loc[~teams["team_abbr"].isin(HISTORICAL_ABBRS)].copy()
    duplicates = current.loc[current["team_nick"].duplicated(keep=False), "team_nick"]
    if not duplicates.empty:
        names = ", ".join(sorted(duplicates.unique()))
        raise ValueError(f"duplicate team nicknames: {names}")
    return dict(zip(current["team_nick"], current["team_abbr"]))
