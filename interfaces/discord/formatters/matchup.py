from services.catalog import normalize_top_n

from interfaces.discord.formatters.common import (
    base_embed,
    call_service,
    highlight_metrics,
    matchup_name,
    metric_name,
    signed,
)


def _signal(value, label):
    return f"{signed(value)} | {label}"


def _metric_summary(metric):
    return f"{metric_name(metric['metric'])}: {_signal(metric['z_score'], metric['label'])}"


def format_best_matchups(result, top):
    records = result["data"][: normalize_top_n(top)]
    position = str(result["meta"].get("position", "")).upper()
    blocks = []
    for record in records:
        lines = [
            f"{record['matchup_rank']}. {matchup_name(record)}",
            f"{position} Matchup Score: {signed(record['matchup_score'])}",
        ]
        lines.extend(_metric_summary(metric) for metric in highlight_metrics(record.get("metrics")))
        blocks.append("\n".join(lines))
    description = "\n\n".join(blocks) if blocks else "No matchups."
    return base_embed(f"Best {position} Matchups - Week {result['meta'].get('week')}", description, result.get("meta"))


def format_metric_matchups(result, top, title=None):
    records = result["data"][: normalize_top_n(top)]
    position = str(result["meta"].get("position", "")).upper()
    metric = metric_name(result["meta"].get("metric", ""))
    blocks = []
    for record in records:
        blocks.append(
            "\n".join([
                f"{record['matchup_rank']}. {matchup_name(record)}",
                f"{position} {metric}",
                f"Value: {record['metric_value']:.2f} | Z: {signed(record['z_score'])} | "
                f"Def Rank: {record['league_rank']} | {record['label']}",
            ])
        )
    heading = title or f"{position} {metric} - Week {result['meta'].get('week')}"
    if title:
        heading = f"{title} - Week {result['meta'].get('week')}"
    return base_embed(heading, "\n\n".join(blocks) if blocks else "No matchups.", result.get("meta"))


def format_defense_profile(result):
    profile = result["data"]
    embed = base_embed(
        f"{profile['team']} Defense vs {profile['position'].upper()}",
        "",
        result.get("meta"),
    )
    for metric in profile["metrics"]:
        embed.add_field(
            name=metric_name(metric["metric"])[:256],
            value=(
                f"Value: {metric['metric_value']:.2f}\n"
                f"Z: {signed(metric['z_score'])}\n"
                f"Rank: {metric['rank']}\n"
                f"Label: {metric['label']}"
            )[:1024],
            inline=True,
        )
    return embed


def format_offense_matchup(result):
    record = result["data"]
    lines = [
        f"{record['position'].upper()} Matchup Score: {signed(record['matchup_score'])}",
    ]
    lines.extend(_metric_summary(metric) for metric in highlight_metrics(record.get("metrics")))
    return base_embed(
        f"{record['offense']} Offense vs {record['defense']} Defense - {record['position'].upper()}",
        "\n".join(lines),
        result.get("meta"),
    )


def format_opportunities(result, top):
    records = result["data"][: normalize_top_n(top)]
    metric = result.get("meta", {}).get("metric")
    blocks = []
    for record in records:
        stat = record["position"].upper()
        if not metric:
            stat = f"{stat} {metric_name(record['metric'])}"
        blocks.append(
            "\n".join([
                f"{record['weekly_rank']}. {matchup_name(record)}",
                stat,
                f"Value: {record['metric_value']:.2f} | Z: {signed(record['z_score'])} | "
                f"Def Rank: {record['defensive_metric_rank']} | {record['label']}",
            ])
        )
    if metric:
        title = f"Top {metric_name(metric)} Opportunities - Week {result['meta'].get('week')}"
        positions = ", ".join(position.upper() for position in result["meta"].get("positions", []))
        intro = f"Positions: {positions}" if positions else ""
    else:
        title = f"Top Matchup Opportunities - Week {result['meta'].get('week')}"
        intro = ""
    body = "\n\n".join(blocks) if blocks else "No matchups."
    description = f"{intro}\n\n{body}" if intro else body
    return base_embed(title, description, result.get("meta"))


def format_game(result):
    game = result["data"]
    sections = []
    for side in game["sides"]:
        header = f"{side['offense']} offense vs {side['defense']} defense"
        if not side["spots"]:
            sections.append(f"{header}\nNo HOT spots.")
            continue
        blocks = [
            "\n".join([
                f"{spot['position'].upper()} {metric_name(spot['metric'])}",
                f"Value: {spot['metric_value']:.2f} | Z: {signed(spot['z_score'])} | "
                f"Def Rank: {spot['defensive_metric_rank']} | {spot['label']}",
            ])
            for spot in side["spots"]
        ]
        sections.append(header + "\n\n" + "\n\n".join(blocks))
    return base_embed(
        f"{game['offense']} vs {game['defense']} - Week {result['meta'].get('week')}",
        "\n\n".join(sections),
        result.get("meta"),
    )


def render_game(team, context, service):
    return call_service(
        lambda: service(team, context=context),
        format_game,
    )


def render_best_matchup(position, top, context, service):
    return call_service(
        lambda: service(position, context=context),
        lambda result: format_best_matchups(result, top),
    )


def render_metric_matchup(position, metric, top, context, service, title=None):
    return call_service(
        lambda: service(position, metric, context=context),
        lambda result: format_metric_matchups(result, top, title),
    )


def render_defense_profile(team, position, context, service):
    return call_service(
        lambda: service(team, position, context=context),
        format_defense_profile,
    )


def render_offense_matchup(team, position, context, service):
    return call_service(
        lambda: service(team, position, context=context),
        format_offense_matchup,
    )


def render_opportunities(top, context, service, metric=None):
    return call_service(
        lambda: service(top, metric=metric, context=context),
        lambda result: format_opportunities(result, top),
    )
