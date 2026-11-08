import pandas as pd

from database.storage import STAT_COLUMNS

LABEL_THRESHOLDS = {
    "hot": 1.5,
    "warm": 1.0,
    "cool": -1.0,
    "cold": -1.5,
}
HIGHER_STRONGER = {"Passing_Int", "FL"}
RESULT_COLUMNS = [
    "team",
    "team_abbr",
    "position",
    "season",
    "week",
    "metric",
    "metric_value",
    "league_mean",
    "z_score",
    "rank",
    "label",
]


class IncompleteMetric(ValueError):
    pass


def label_z(z_score, thresholds=None):
    cuts = thresholds or LABEL_THRESHOLDS
    if z_score >= cuts["hot"]:
        return "HOT"
    if z_score >= cuts["warm"]:
        return "WARM"
    if z_score > cuts["cool"]:
        return "NEUTRAL"
    if z_score > cuts["cold"]:
        return "COOL"
    return "COLD"


def _direction(metric, direction):
    if direction is None:
        return "higher_stronger" if metric in HIGHER_STRONGER else "higher_weaker"
    if direction not in {"higher_weaker", "higher_stronger"}:
        raise ValueError(f"unknown direction {direction}")
    return direction


def analyze_metric(df, position, metric, direction=None, expected_teams=32, thresholds=None):
    if "season" in df.columns and df["season"].nunique(dropna=True) > 1:
        raise ValueError("snapshot has more than one season")
    if "week" in df.columns and df["week"].nunique(dropna=True) > 1:
        raise ValueError("snapshot has more than one week")
    if "position" not in df.columns or position not in set(df["position"].dropna()):
        raise ValueError(f"position {position} not in snapshot")
    if metric not in df.columns:
        raise ValueError(f"metric {metric} not in snapshot")
    if not pd.api.types.is_numeric_dtype(df[metric]):
        raise ValueError(f"metric {metric} is not numeric")

    group = df.loc[df["position"] == position].copy()
    scored = group.dropna(subset=[metric])
    teams = scored["team_abbr"].nunique(dropna=True)
    if teams != expected_teams:
        raise IncompleteMetric(f"{position} {metric} has {teams} defenses, expected {expected_teams}")

    values = scored[metric].astype(float)
    mean = float(values.mean())
    std = float(values.std(ddof=0))
    if std == 0:
        z_score = pd.Series(0.0, index=scored.index)
    else:
        z_score = (values - mean) / std
    if _direction(metric, direction) == "higher_stronger":
        z_score = -z_score

    result = scored[["team", "team_abbr", "position", "season", "week"]].copy()
    result["metric"] = metric
    result["metric_value"] = values
    result["league_mean"] = mean
    result["z_score"] = z_score
    result["rank"] = z_score.rank(method="min", ascending=False).astype(int)
    result["label"] = z_score.map(lambda score: label_z(score, thresholds))
    return result[RESULT_COLUMNS].reset_index(drop=True)


def analyze_snapshot(df, position=None, expected_teams=32):
    if df.empty:
        return pd.DataFrame(columns=RESULT_COLUMNS)
    positions = [position] if position else sorted(df["position"].dropna().unique())
    if position and position not in set(df["position"].dropna()):
        raise ValueError(f"position {position} not in snapshot")
    frames = []
    for pos in positions:
        for metric in STAT_COLUMNS:
            if metric not in df.columns:
                continue
            try:
                frames.append(analyze_metric(df, pos, metric, expected_teams=expected_teams))
            except IncompleteMetric:
                continue
    if not frames:
        return pd.DataFrame(columns=RESULT_COLUMNS)
    return pd.concat(frames, ignore_index=True)
