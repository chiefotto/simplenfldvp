import pandas as pd
from io import StringIO

from teams import nickname_to_abbr


def parse_table(html):
    raw = pd.read_html(StringIO(html))[0]
    raw = raw.drop(index=0).drop(columns=raw.columns[0]).reset_index(drop=True)

    groups, names = raw.iloc[0], raw.iloc[1]
    df = raw.iloc[2:].copy().reset_index(drop=True)
    df.columns = [
        name if pd.isna(group) else f"{group}_{name}"
        for group, name in zip(groups, names)
    ]

    parts = df["Team"].str.split()
    df["position"] = parts.str[0].str.lower()
    df["team"] = parts.str[2]
    abbrs = nickname_to_abbr()
    missing = sorted(set(df["team"]) - set(abbrs))
    if missing:
        raise ValueError(f"no abbreviation for {', '.join(missing)}")
    df["team_abbr"] = df["team"].map(abbrs)
    return df.drop(columns="Team")