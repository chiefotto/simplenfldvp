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


def _td_line(record, ranked=True):
    body = (
        f"{record['position'].upper()} {record['td_type']} "
        f"{record['metric_value']:.2f}, z {signed(record['z_score'])}, "
        f"DEF RANK {record['defensive_metric_rank']}, {record['label']}"
    )
    if not ranked:
        return body
    return f"{record['weekly_rank']}. {_pair(record)} - {body}"


def format_touchdowns(result):
    records = result["data"]
    position = result["meta"].get("position")
    scope = f"{position.upper()} " if position else ""
    lines = _heading(result, f"Best {scope}Touchdown Matchups - Week {result['meta'].get('week')}")
    for record in records:
        lines.append(_td_line(record))
    if not records:
        lines.append("No matchups.")
    return "\n".join(lines)


def format_touchdown_offense(result):
    records = result["data"]
    first = records[0]
    lines = _heading(result, f"{first['offense']} OFFENSE")
    lines.append(f"Opponent Defense: {first['defense']}")
    for record in records:
        lines.append(_td_line(record, ranked=False))
    return "\n".join(lines)


def render_touchdowns(position, top, context, service):
    return call_service(
        lambda: service(position, top, context=context),
        format_touchdowns,
    )


def render_touchdown_offense(team, context, service):
    return call_service(
        lambda: service(team, context=context),
        format_touchdown_offense,
    )
