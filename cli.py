import pandas as pd
from rich import box
from rich.console import Console
from rich.table import Table

from database.queries import (
    current_schedule,
    defense_table,
    known_team_abbrs,
    latest_dvp,
    matchup_context,
    matchups_table,
    normalized_defense,
    normalized_matchups,
    season_status,
    team_on_bye,
)

from services.catalog import COMMANDS as SERVICE_COMMANDS
from services.catalog import DEFAULT_TOP_N, POSITIONS
from services.context import RequestContext
from services.fantasy_service import (
    get_best_fantasy_matchups,
    get_fantasy_offense_matchup,
    get_fantasy_position_rankings,
    get_worst_fantasy_matchups,
)
from services.matchup_service import (
    get_best_metric_matchups,
    get_best_position_matchups,
    get_defense_profile,
    get_offense_matchup,
)
from services.opportunity_service import get_top_weekly_opportunities

TOP_N = DEFAULT_TOP_N
CLI_CONTEXT = RequestContext(interface="cli", caller_id="local", access_level="ADMIN")
HIDDEN_COLUMNS = {"id", "created_at", "updated_at"}

COMMANDS = {
    "schedule": "this week's games",
    "dvp": "raw defense table for the latest stored week",
    "defense": "labeled weaknesses for a team or position",
    "matchups": "opponent labels for this week's games",
    "matchup": "best offensive matchups for a position",
    "fantasy": "positional fantasy matchups from FPTS allowed",
    "help": "how defense and matchups differ",
    "quit": "exit",
}


def show_menu():
    status = season_status()
    print(f"current game week: {status['current_week']}")
    print(f"dvp available through week: {status['dvp_week']} ({status['dvp_season']})")
    print()
    for name, description in COMMANDS.items():
        print(f"{name:<10} {description}")


def show_help():
    print("schedule  this week's games, including ones already played")
    print("dvp       raw defense table for the latest stored week")
    print("defense   a team's own labeled weaknesses, ranked against all 32 defenses")
    print("          defense det")
    print("          defense wr")
    print("          defense det wr")
    print("matchups  the opponent's labeled weaknesses for the current slate")
    print("          matchups")
    print("          matchups det")
    print("          matchups wr")
    print("          matchups det wr")
    print("matchup   ranked offensive matchups; matchups remains the full labeled table")
    for command in SERVICE_COMMANDS:
        if command["access"] != "PUBLIC":
            continue
        print(f"          {command['example']:<28} {command['description']}")
    print("raw       add raw to defense or matchups for the original CBS numbers")
    print("labels    HOT WARM NEUTRAL COOL COLD")
    print(f"positions {', '.join(POSITIONS)}")
    print("quit      exit")


def format_cell(value):
    if pd.isna(value):
        return ""
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        number = float(value)
        if number.is_integer():
            return str(int(number))
        return f"{number:.2f}"
    return str(value)


def show_table(df):
    if df.empty:
        print("no rows")
        return
    columns = [column for column in df.columns if column not in HIDDEN_COLUMNS]
    view = df[columns].dropna(axis=1, how="all")
    table = Table(box=box.SIMPLE_HEAD, header_style="bold", show_edge=False, pad_edge=False)
    for column in view.columns:
        numeric = pd.api.types.is_numeric_dtype(view[column])
        table.add_column(str(column), justify="right" if numeric else "left", no_wrap=True)
    for row in view.itertuples(index=False, name=None):
        table.add_row(*(format_cell(value) for value in row))
    Console(width=500, height=200).print(table)


def signed(value):
    if value is None or pd.isna(value):
        return "n/a"
    return f"{float(value):+.2f}"


def print_metrics(metrics):
    print(f"{'METRIC':<18}{'VALUE':>10}{'Z':>8}{'RANK':>8}  LABEL")
    for metric in metrics:
        print(
            f"{metric['metric']:<18}"
            f"{metric['metric_value']:>10.2f}"
            f"{signed(metric['z_score']):>8}"
            f"{metric['rank']:>8}  "
            f"{metric['label']}"
        )


def unwrap(result):
    if not result["success"]:
        print(result["error"]["message"])
        return None
    if result["meta"].get("note"):
        print(result["meta"]["note"])
    return result


def show_opportunities(limit):
    result = unwrap(get_top_weekly_opportunities(limit, context=CLI_CONTEXT))
    if result is None:
        return
    records = result["data"]
    week = result["meta"].get("week")
    print(f"WEEK {week} - TOP MATCHUP OPPORTUNITIES")
    print(f"{'RANK':<6}{'OFFENSE':<10}{'DEFENSE':<10}{'POS':<5}{'METRIC':<18}{'VALUE':>10}{'Z':>8}{'DEF RANK':>10}  LABEL")
    for record in records[:limit]:
        print(
            f"{record['weekly_rank']:<6}"
            f"{record['offense']:<10}"
            f"{record['defense']:<10}"
            f"{record['position'].upper():<5}"
            f"{record['metric']:<18}"
            f"{record['metric_value']:>10.2f}"
            f"{signed(record['z_score']):>8}"
            f"{record['defensive_metric_rank']:>10}  "
            f"{record['label']}"
        )
    if not records:
        return
    top = records[0]
    print()
    print(f"RANK {top['weekly_rank']}")
    print(f"Target Offense: {top['offense']}")
    print(f"Opponent Defense: {top['defense']}")
    print(f"Position: {top['position'].upper()}")
    print(f"Metric: {top['metric']}")
    print(f"Defense Allows: {top['metric_value']:.2f}")
    print(f"League Mean: {top['league_mean']:.2f}")
    print(f"Z-score: {signed(top['z_score'])}")
    print(f"Defensive League Rank: {top['defensive_metric_rank']}")
    print(f"Label: {top['label']}")


def show_best(position):
    result = unwrap(get_best_position_matchups(position, context=CLI_CONTEXT))
    if result is None:
        return
    records = result["data"]
    week = result["meta"].get("week")
    print(f"WEEK {week} - BEST {position.upper()} MATCHUPS")
    print(f"{'RANK':<6}{'OFFENSE':<10}{'DEFENSE':<10}SCORE")
    for record in records[:TOP_N]:
        print(
            f"{record['matchup_rank']:<6}"
            f"{record['offense']:<10}"
            f"{record['defense']:<10}"
            f"{signed(record['matchup_score'])}"
        )
    if not records:
        return
    top = records[0]
    print()
    print(f"1. {top['offense']} offense vs {top['defense']} defense")
    print(f"   Position: {top['position'].upper()}")
    print(f"   Matchup Score: {signed(top['matchup_score'])}")
    print()
    print_metrics(top["metrics"])


def show_best_metric(position, alias):
    result = unwrap(get_best_metric_matchups(position, alias, context=CLI_CONTEXT))
    if result is None:
        return
    records = result["data"]
    metric_name = result["meta"].get("metric", alias)
    week = result["meta"].get("week")
    print(f"WEEK {week} - BEST {position.upper()} {alias.upper()} MATCHUPS")
    print(f"{'RANK':<6}{'OFFENSE':<10}{'DEFENSE':<10}{metric_name:>12}{'Z':>8}{'DEF RANK':>10}  LABEL")
    for record in records[:TOP_N]:
        print(
            f"{record['matchup_rank']:<6}"
            f"{record['offense']:<10}"
            f"{record['defense']:<10}"
            f"{record['metric_value']:>12.2f}"
            f"{signed(record['z_score']):>8}"
            f"{record['league_rank']:>10}  "
            f"{record['label']}"
        )


def show_defense_profile(team, position):
    result = unwrap(get_defense_profile(team, position, context=CLI_CONTEXT))
    if result is None:
        return
    profile = result["data"]
    print(f"{profile['team']} DEFENSE VS {profile['position'].upper()}")
    print(f"Snapshot: {profile['season']} Week {profile['week']}")
    print()
    print_metrics(profile["metrics"])


def show_offense_matchup(team, position):
    result = unwrap(get_offense_matchup(team, position, context=CLI_CONTEXT))
    if result is None:
        return
    record = result["data"]
    print(f"{record['offense']} OFFENSE")
    print(f"Opponent Defense: {record['defense']}")
    print(f"Position: {record['position'].upper()}")
    print(f"Week: {record['week']}")
    print(f"Matchup Score: {signed(record['matchup_score'])}")
    print()
    print_metrics(record["metrics"])


def show_fantasy_table(records, title, limit, include_position, week):
    print(f"WEEK {week} - {title}")
    position_header = f"{'POS':<5}" if include_position else ""
    print(f"{'RANK':<6}{'OFFENSE':<10}{'DEFENSE':<10}{position_header}{'FPTS/G':>10}{'Z':>8}{'DEF RANK':>10}  LABEL")
    shown = records if limit is None else records[:limit]
    for record in shown:
        position = f"{record['position'].upper():<5}" if include_position else ""
        print(
            f"{record['weekly_rank']:<6}"
            f"{record['offense']:<10}"
            f"{record['defense']:<10}"
            f"{position}"
            f"{record['fpts_allowed']:>10.2f}"
            f"{signed(record['fpts_z_score']):>8}"
            f"{record['defensive_fpts_rank']:>10}  "
            f"{record['label']}"
        )


def show_fantasy_offense(team, position):
    result = unwrap(get_fantasy_offense_matchup(team, position, context=CLI_CONTEXT))
    if result is None:
        return
    record = result["data"]
    print(f"{record['offense']} OFFENSE")
    print(f"Opponent Defense: {record['defense']}")
    print(f"Position: {record['position'].upper()}")
    print(f"Week: {record['week']}")
    print()
    print(f"Opponent {record['position'].upper()} FPTS Allowed: {record['fpts_allowed']:.2f}")
    print(f"League Mean: {record['league_mean']:.2f}")
    print(f"FPTS Z-score: {signed(record['fpts_z_score'])}")
    print(f"Defensive Rank: {record['defensive_fpts_rank']}")
    print(f"Label: {record['label']}")


def show_fantasy(tokens):
    if not tokens:
        print("fantasy best | fantasy worst | fantasy position wr | fantasy offense det wr")
        return
    mode, *rest = tokens
    if mode == "best":
        if rest:
            print("fantasy best")
            return
        result = unwrap(get_best_fantasy_matchups(context=CLI_CONTEXT))
        if result is None:
            return
        show_fantasy_table(result["data"], "BEST FANTASY MATCHUPS", TOP_N, True, result["meta"].get("week"))
        return
    if mode == "worst":
        if rest:
            print("fantasy worst")
            return
        result = unwrap(get_worst_fantasy_matchups(context=CLI_CONTEXT))
        if result is None:
            return
        show_fantasy_table(
            result["data"],
            "DIFFICULT POSITIONAL MATCHUPS",
            TOP_N,
            True,
            result["meta"].get("week"),
        )
        return
    if mode == "position":
        if len(rest) != 1:
            print("fantasy position needs a position. positions: " + ", ".join(POSITIONS))
            return
        result = unwrap(get_fantasy_position_rankings(rest[0], context=CLI_CONTEXT))
        if result is None:
            return
        show_fantasy_table(
            result["data"],
            f"{result['meta']['position'].upper()} FANTASY MATCHUPS",
            None,
            False,
            result["meta"].get("week"),
        )
        return
    if mode == "offense":
        team, position, error = split_team_position(rest)
        if error:
            print(error)
            return
        show_fantasy_offense(team, position)
        return
    print("fantasy best | fantasy worst | fantasy position wr | fantasy offense det wr")


def split_team_position(tokens):
    allowed = ", ".join(name.upper() for name in POSITIONS)
    if len(tokens) != 2:
        return None, None, "needs a team and a position. positions: " + allowed
    first, second = tokens
    known = {abbr.lower() for abbr in known_team_abbrs()}
    if first in POSITIONS and second not in POSITIONS:
        return second, first, None
    if second in POSITIONS and first not in POSITIONS:
        return first, second, None
    if first in POSITIONS and second in POSITIONS:
        return None, None, "needs a team and a position. positions: " + allowed
    if second in known and first not in known:
        return second, first, None
    return first, second, None


def show_matchup(tokens):
    if not tokens:
        print("matchup best | matchup best wr | matchup best wr receptions | matchup defense det wr | matchup offense mia wr")
        return
    mode, *rest = tokens
    if mode == "best":
        if not rest:
            show_opportunities(TOP_N)
            return
        if rest[0].isdigit():
            if len(rest) != 1:
                print("matchup best 10")
                return
            show_opportunities(int(rest[0]))
            return
        if len(rest) == 1:
            show_best(rest[0])
            return
        if len(rest) == 2:
            show_best_metric(rest[0], rest[1])
            return
        print("matchup best wr receptions")
        return
    if mode in {"defense", "offense"}:
        team, position, error = split_team_position(rest)
        if error:
            print(error)
            return
        if mode == "defense":
            show_defense_profile(team, position)
        else:
            show_offense_matchup(team, position)
        return
    print("matchup best | matchup best wr | matchup best wr receptions | matchup defense det wr | matchup offense mia wr")


def classify(tokens):
    team = None
    position = None
    raw = False
    known = known_team_abbrs()
    for token in tokens:
        if token == "raw":
            if raw:
                return None, None, None, "raw can be used once"
            raw = True
            continue
        if token in POSITIONS:
            if position is not None:
                return None, None, None, "one position at a time. positions: " + ", ".join(POSITIONS)
            position = token
            continue
        abbr = token.upper()
        if abbr not in known:
            return None, None, None, f"{abbr} was not found. positions: {', '.join(POSITIONS)}"
        if team is not None:
            return None, None, None, "one team at a time"
        team = abbr
    return team, position, raw, None


def main():
    show_menu()
    while True:
        line = input("> ").strip().lower()
        if not line:
            show_menu()
            continue
        command, *tokens = line.split()
        if command == "quit":
            break
        if command == "help":
            show_help()
            continue
        if command == "dvp":
            show_table(latest_dvp())
            continue
        if command == "schedule":
            show_table(current_schedule())
            continue
        if command == "defense":
            team, position, raw, error = classify(tokens)
            if error:
                print(error)
                continue
            if raw:
                show_table(defense_table(team, position))
            else:
                show_table(normalized_defense(team, position))
            continue
        if command == "fantasy":
            show_fantasy(tokens)
            continue
        if command == "matchup":
            show_matchup(tokens)
            continue
        if command == "matchups":
            team, position, raw, error = classify(tokens)
            if error:
                print(error)
                continue
            if team and team_on_bye(team):
                print(f"{team} is on bye")
                continue
            _season, _week, note = matchup_context()
            if note:
                print(note)
            if raw:
                show_table(matchups_table(team, position))
            else:
                show_table(normalized_matchups(team, position))
            continue
        show_menu()


if __name__ == "__main__":
    main()
