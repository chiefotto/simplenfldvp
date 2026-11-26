from interfaces.discord.formatters.common import base_embed, call_service


def _present(result):
    data = result["data"]
    embed = base_embed(data["title"], data["description"], result.get("meta"))
    return embed, data.get("url"), data.get("button")


def render_weekly_link(base_url, season, week, context, service):
    return call_service(
        lambda: service(base_url, season, week, context=context),
        _present,
    )


def render_game_link(base_url, team, season, week, context, service):
    return call_service(
        lambda: service(base_url, team, season, week, context=context),
        _present,
    )


def render_rankings_link(base_url, position, metric, season, week, context, service):
    return call_service(
        lambda: service(base_url, position, metric, season, week, context=context),
        _present,
    )
