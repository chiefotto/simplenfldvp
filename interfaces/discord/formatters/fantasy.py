from services.catalog import normalize_top_n

from interfaces.discord.formatters.common import base_embed, call_service, matchup_name, signed


def _fantasy_block(record, include_position):
    position = f"{record['position'].upper()} | " if include_position else ""
    stat = "FPTS allowed" if include_position else "FPTS"
    return "\n".join([
        f"{record['weekly_rank']}. {matchup_name(record)}",
        f"{position}{record['fpts_allowed']:.2f} {stat}",
        f"Z: {signed(record['fpts_z_score'])} | Def Rank: {record['defensive_fpts_rank']} | {record['label']}",
    ])


def _ranked_embed(result, title, records, include_position):
    blocks = [_fantasy_block(record, include_position) for record in records]
    return base_embed(title, "\n\n".join(blocks) if blocks else "No matchups.", result.get("meta"))


def format_fantasy_best(result, top):
    week = result["meta"].get("week")
    return _ranked_embed(
        result,
        f"Best Fantasy Matchups - Week {week}",
        result["data"][: normalize_top_n(top)],
        True,
    )


def format_fantasy_worst(result, top):
    week = result["meta"].get("week")
    return _ranked_embed(
        result,
        f"Difficult Fantasy Matchups - Week {week}",
        result["data"][: normalize_top_n(top)],
        True,
    )


def format_fantasy_position(result):
    position = str(result["meta"].get("position", "")).upper()
    return _ranked_embed(
        result,
        f"{position} Fantasy Matchups - Week {result['meta'].get('week')}",
        result["data"],
        False,
    )


def format_fantasy_offense(result):
    record = result["data"]
    description = "\n".join([
        f"FPTS allowed: {record['fpts_allowed']:.2f}",
        f"Z: {signed(record['fpts_z_score'])} | Def Rank: {record['defensive_fpts_rank']} | {record['label']}",
    ])
    return base_embed(
        f"{record['offense']} Offense vs {record['defense']} Defense - {record['position'].upper()}",
        description,
        result.get("meta"),
    )


def render_fantasy_best(top, context, service):
    return call_service(lambda: service(context=context), lambda result: format_fantasy_best(result, top))


def render_fantasy_worst(top, context, service):
    return call_service(lambda: service(context=context), lambda result: format_fantasy_worst(result, top))


def render_fantasy_position(position, context, service):
    return call_service(lambda: service(position, context=context), format_fantasy_position)


def render_fantasy_offense(team, position, context, service):
    return call_service(lambda: service(team, position, context=context), format_fantasy_offense)
