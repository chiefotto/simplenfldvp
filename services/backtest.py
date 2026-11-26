import argparse
import math
import sqlite3

import pandas as pd

from database.matchups import PLAYER_STAT_COLUMNS, canonical_metric
from database.player_stats import snap_counts, weekly_stats
from database.queries import defense_snapshot_for
from services.player_service import _games_for, weekly_player_opportunities


def _mean(values, transform):
    if not values:
        return None
    return sum(transform(value) for value in values) / len(values)


def _metrics(errors):
    if not errors:
        return {"count": 0, "mae": None, "rmse": None, "bias": None}
    return {
        "count": len(errors),
        "mae": _mean(errors, abs),
        "rmse": math.sqrt(_mean(errors, lambda value: value * value)),
        "bias": _mean(errors, lambda value: value),
    }


def _completed_games(season):
    from database.storage import DB_PATH

    with sqlite3.connect(DB_PATH) as conn:
        frame = pd.read_sql(
            """
            SELECT game_id, season, week, gameday, away_team, home_team, away_score, home_score
            FROM schedule
            WHERE season = ? AND away_score IS NOT NULL AND home_score IS NOT NULL
            """,
            conn,
            params=(str(season),),
        )
    if frame.empty:
        return []
    return frame.to_dict(orient="records")


def _actuals(season, week):
    stats = weekly_stats(season)
    snaps = snap_counts(season)
    if not stats.empty:
        stats = stats.loc[stats["week"] == int(week)]
    if not snaps.empty:
        snaps = snaps.loc[snaps["week"] == int(week)]
    logs = _games_for(stats, snaps, int(week) + 1)
    actual = {}
    for player_id, games in logs.items():
        for game in games:
            if game["week"] != int(week):
                continue
            actual[player_id] = game
    return actual


def evaluate(season, metric=None):
    metrics = [canonical_metric(metric)] if metric else list(PLAYER_STAT_COLUMNS)
    games = _completed_games(season)
    report = {
        "season": str(season),
        "completed_games": len(games),
        "metrics": {},
        "note": (
            "Errors are conditional on the player playing that week. "
            "Expected players who did not play are counted separately and are not removed from the sample to improve the score. "
            "Estimates use only earlier weeks, an earlier depth chart, and a defensive snapshot from before the game."
        ),
        "weeks_without_snapshot": 0,
    }
    completed_ids = {game["game_id"] for game in games}
    weeks = sorted({int(game["week"]) for game in games})
    by_week = {}
    for week in weeks:
        if defense_snapshot_for(season, week)[1] is None:
            report["weeks_without_snapshot"] += 1
            by_week[week] = {"rows": [], "actual": {}}
            continue
        by_week[week] = {
            "rows": weekly_player_opportunities(season, week, baseline="season", scope="relevant"),
            "actual": _actuals(season, week),
        }
    for metric_name in metrics:
        column = PLAYER_STAT_COLUMNS[metric_name]
        usable = []
        did_not_play = 0
        no_estimate = 0
        missing_snapshot = 0
        for week, payload in by_week.items():
            actuals = payload["actual"]
            for row in payload["rows"]:
                if row["game_id"] not in completed_ids or row["metric"] != metric_name:
                    continue
                if row.get("snapshot_week") is None:
                    missing_snapshot += 1
                    continue
                game = actuals.get(row["player_id"])
                if game is None or not game["played"]:
                    did_not_play += 1
                    continue
                actual = game["values"].get(column)
                if actual is None and game["via"] == "snaps":
                    actual = 0.0
                if actual is None or row.get("player_avg") is None or row.get("adjusted") is None or row.get("z_adjusted") is None:
                    no_estimate += 1
                    continue
                usable.append((row["player_avg"] - actual, row["adjusted"] - actual, row["z_adjusted"] - actual))
        report["metrics"][metric_name] = {
            "usable": len(usable),
            "did_not_play": did_not_play,
            "no_estimate": no_estimate,
            "missing_snapshot": missing_snapshot,
            "baseline": _metrics([item[0] for item in usable]),
            "ratio": _metrics([item[1] for item in usable]),
            "z": _metrics([item[2] for item in usable]),
        }
    return report


def _format_score(score):
    if score["count"] == 0:
        return "no comparable cases"
    return f"n={score['count']} MAE={score['mae']:.3f} RMSE={score['rmse']:.3f} bias={score['bias']:.3f}"


def format_report(report):
    lines = [
        f"Backtest {report['season']}: {report['completed_games']} completed games",
        report["note"],
    ]
    if report.get("weeks_without_snapshot"):
        lines.append(f"{report['weeks_without_snapshot']} completed weeks have no earlier defensive snapshot.")
    if not report["metrics"]:
        lines.append("No metrics were requested.")
        return "\n".join(lines)
    for metric, result in report["metrics"].items():
        lines.append(
            f"{metric}: usable {result['usable']}, did not play {result['did_not_play']}, "
            f"no estimate {result['no_estimate']}, missing snapshot {result['missing_snapshot']}"
        )
        if result["usable"] == 0:
            lines.append("  Not enough historical cases to score this stat.")
            continue
        lines.append(f"  baseline {_format_score(result['baseline'])}")
        lines.append(f"  ratio    {_format_score(result['ratio'])}")
        lines.append(f"  z-score  {_format_score(result['z'])}")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare experimental player estimates with completed games.")
    parser.add_argument("--season", required=True)
    parser.add_argument("--metric", default=None)
    args = parser.parse_args(argv)
    try:
        report = evaluate(args.season, args.metric)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    print(format_report(report))
    return 0


if __name__ == "__main__":
    main()
