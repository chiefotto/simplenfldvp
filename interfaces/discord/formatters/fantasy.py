from services.catalog import normalize_top_n

from interfaces.discord.formatters.common import call_service, signed


def _heading(result, title):
    lines = []
    note = result.get("meta", {}).get("note")
    if note:
        lines.append(note)
    lines.append(title)
    return lines


def _pair(record):
    return f"{record['offense']} offense vs {record['defense']} defense"


def _fantasy_line(record, include_position):
    position = f"{record['position'].upper()} " if include_position else ""
    return (
        f"{record['weekly_rank']}. {_pair(record)} - "
        f"{position}{record['fpts_allowed']:.2f}, z {signed(record['fpts_z_score'])}, "
        f"DEF RANK {record['defensive_fpts_rank']}, {record['label']}"
    )


def format_fantasy_rankings(result, title, top, include_position):
    records = result["data"][: normalize_top_n(top)]
    lines = _heading(result, title)
    for record in records:
        lines.append(_fantasy_line(record, include_position))
    if not records:
        lines.append("No matchups.")
    return "\n".join(lines)


def format_fantasy_best(result, top):
    week = result["meta"].get("week")
    return format_fantasy_rankings(
        result,
        f"Best Fantasy Matchups - Week {week}",
        top,
        True,
    )


def format_fantasy_worst(result, top):
    week = result["meta"].get("week")
    return format_fantasy_rankings(
        result,
        f"Difficult Fantasy Matchups - Week {week}",
        top,
        True,
    )


def format_fantasy_position(result):
    position = str(result["meta"].get("position", "")).upper()
    records = result["data"]
    lines = _heading(result, f"{position} Fantasy Matchups - Week {result['meta'].get('week')}")
    for record in records:
        lines.append(_fantasy_line(record, False))
    if not records:
        lines.append("No matchups.")
    return "\n".join(lines)


def format_fantasy_offense(result):
    record = result["data"]
    lines = _heading(result, f"{record['offense']} OFFENSE")
    lines.extend([
        f"Opponent Defense: {record['defense']}",
        f"Position: {record['position'].upper()}",
        f"Week: {record['week']}",
        f"Opponent {record['position'].upper()} FPTS Allowed: {record['fpts_allowed']:.2f}",
        f"League Mean: {record['league_mean']:.2f}",
        f"FPTS Z-score: {signed(record['fpts_z_score'])}",
        f"Defensive Rank: {record['defensive_fpts_rank']}",
        f"Label: {record['label']}",
    ])
    return "\n".join(lines)


def render_fantasy_best(top, context, service):
    return call_service(lambda: service(context=context), lambda result: format_fantasy_best(result, top))


def render_fantasy_worst(top, context, service):
    return call_service(lambda: service(context=context), lambda result: format_fantasy_worst(result, top))


def render_fantasy_position(position, context, service):
    return call_service(lambda: service(position, context=context), format_fantasy_position)


def render_fantasy_offense(team, position, context, service):
    return call_service(lambda: service(team, position, context=context), format_fantasy_offense)
