from interfaces.discord.formatters.common import (
    base_embed,
    call_service,
    matchup_name,
    metric_name,
    signed,
)


def _touchdown_block(record, ranked=True):
    lines = []
    if ranked:
        lines.append(f"{record['weekly_rank']}. {matchup_name(record)}")
    lines.append(f"{record['position'].upper()} {metric_name(record['td_type'])}")
    lines.append(
        f"Value: {record['metric_value']:.2f} | Z: {signed(record['z_score'])} | "
        f"Def Rank: {record['defensive_metric_rank']} | {record['label']}"
    )
    return "\n".join(lines)


def format_touchdowns(result):
    records = result["data"]
    position = result["meta"].get("position")
    scope = f"{str(position).upper()} " if position else ""
    blocks = [_touchdown_block(record) for record in records]
    return base_embed(
        f"Best {scope}Touchdown Matchups - Week {result['meta'].get('week')}",
        "\n\n".join(blocks) if blocks else "No matchups.",
        result.get("meta"),
    )


def format_touchdown_offense(result):
    records = result["data"]
    first = records[0]
    blocks = [_touchdown_block(record, ranked=False) for record in records]
    return base_embed(
        f"{first['offense']} Offense vs {first['defense']} Defense",
        "\n\n".join(blocks),
        result.get("meta"),
    )


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
