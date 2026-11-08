from interfaces.discord.formatters.common import base_embed, call_service


def format_status(result):
    data = result["data"]
    description = (
        f"Season {data['dvp_season']}\n"
        f"Current game week: {data['current_week']}\n"
        f"Defense snapshot week: {data['dvp_week']}"
    )
    return base_embed("Data Status", description, result.get("meta"))


def format_update(result):
    data = result["data"]
    description = (
        f"Updated {data['season']} week {data['week']}: "
        f"{data['rows_written']} dvp rows, {data['games_written']} games."
    )
    return base_embed("Data Update", description, result.get("meta"))


def render_status(context, service):
    return call_service(lambda: service(context=context), format_status)


def render_update(context, service):
    return call_service(lambda: service(context=context), format_update)
