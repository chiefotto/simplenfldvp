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


def _metric_line(metric):
    return (
        f"{metric['metric']} {metric['metric_value']:.2f} "
        f"z {signed(metric['z_score'])} rank {metric['rank']} {metric['label']}"
    )


def format_best_matchups(result, top):
    count = normalize_top_n(top)
    records = result["data"][:count]
    position = str(result["meta"].get("position", "")).upper()
    lines = _heading(result, f"Best {position} Matchups - Week {result['meta'].get('week')}")
    for record in records:
        lines.append(f"{record['matchup_rank']}. {_pair(record)} - {signed(record['matchup_score'])}")
    if len(lines) == 1 or (result.get("meta", {}).get("note") and len(lines) == 2):
        lines.append("No matchups.")
    return "\n".join(lines)


def format_metric_matchups(result, top):
    count = normalize_top_n(top)
    records = result["data"][:count]
    position = str(result["meta"].get("position", "")).upper()
    metric = result["meta"].get("metric", "")
    lines = _heading(result, f"{position} {metric} - Week {result['meta'].get('week')}")
    for record in records:
        lines.append(
            f"{record['matchup_rank']}. {_pair(record)} - "
            f"{record['metric_value']:.2f}, z {signed(record['z_score'])}, "
            f"DEF RANK {record['league_rank']}, {record['label']}"
        )
    if not records:
        lines.append("No matchups.")
    return "\n".join(lines)


def format_defense_profile(result):
    profile = result["data"]
    lines = _heading(
        result,
        f"{profile['team']} DEFENSE VS {profile['position'].upper()}",
    )
    lines.append(f"Snapshot: {profile['season']} Week {profile['week']}")
    for metric in profile["metrics"]:
        lines.append(_metric_line(metric))
    return "\n".join(lines)


def format_offense_matchup(result):
    record = result["data"]
    lines = _heading(result, f"{record['offense']} OFFENSE")
    lines.extend([
        f"Opponent Defense: {record['defense']}",
        f"Position: {record['position'].upper()}",
        f"Week: {record['week']}",
        f"Matchup Score: {signed(record['matchup_score'])}",
    ])
    for metric in record["metrics"]:
        lines.append(_metric_line(metric))
    return "\n".join(lines)


def format_opportunities(result, top):
    count = normalize_top_n(top)
    records = result["data"][:count]
    lines = _heading(result, f"Top Matchup Opportunities - Week {result['meta'].get('week')}")
    for record in records:
        lines.append(
            f"{record['weekly_rank']}. {_pair(record)} - "
            f"{record['position'].upper()} {record['metric']} "
            f"{record['metric_value']:.2f}, z {signed(record['z_score'])}, "
            f"DEF RANK {record['defensive_metric_rank']}, {record['label']}"
        )
    if not records:
        lines.append("No matchups.")
    return "\n".join(lines)


def render_best_matchup(position, top, context, service):
    return call_service(
        lambda: service(position, context=context),
        lambda result: format_best_matchups(result, top),
    )


def render_metric_matchup(position, metric, top, context, service):
    return call_service(
        lambda: service(position, metric, context=context),
        lambda result: format_metric_matchups(result, top),
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


def render_opportunities(top, context, service):
    return call_service(
        lambda: service(top, context=context),
        lambda result: format_opportunities(result, top),
    )
