import logging

from services.catalog import normalize_top_n
from services.errors import AppError

from interfaces.discord.formatters.common import UNEXPECTED, format_service_error

logger = logging.getLogger("interfaces.discord")


def format_best_matchups(result, top):
    count = normalize_top_n(top)
    records = result["data"][:count]
    position = str(result["meta"].get("position", "")).upper()
    week = result["meta"].get("week")
    lines = [f"Best {position} Matchups - Week {week}"]
    for record in records:
        score = record["matchup_score"]
        shown = "n/a" if score is None else f"{float(score):+.2f}"
        lines.append(
            f"{record['matchup_rank']}. {record['offense']} offense vs {record['defense']} defense - {shown}"
        )
    if len(lines) == 1:
        lines.append("No matchups.")
    return "\n".join(lines)


def render_best_matchup(position, top, context, service):
    try:
        result = service(position, context=context)
    except Exception:
        logger.exception("command failed")
        return UNEXPECTED
    if not result["success"]:
        return format_service_error(result["error"])
    try:
        return format_best_matchups(result, top)
    except AppError as error:
        return error.message
