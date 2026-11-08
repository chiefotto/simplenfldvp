import logging

import discord

UNEXPECTED = "An unexpected error occurred while processing the command."
DESCRIPTION_LIMIT = 4096
FIT_NOTE = "\nShowing the lines that fit."

logger = logging.getLogger("interfaces.discord")

METRIC_NAMES = {
    "Receiving_Recpt": "Receiving Receptions",
    "Receiving_Targt": "Receiving Targets",
    "Receiving_Yd": "Receiving Yards",
    "Receiving_TD": "Receiving TD",
    "Rushing_Att": "Rushing Attempts",
    "Rushing_Yd": "Rushing Yards",
    "Rushing_TD": "Rushing TD",
    "Passing_Yd": "Passing Yards",
    "Passing_TD": "Passing TD",
    "FPTS": "FPTS",
}


def signed(value):
    if value is None:
        return "n/a"
    return f"{float(value):+.2f}"


def metric_name(metric):
    return METRIC_NAMES.get(metric, str(metric).replace("_", " "))


def matchup_name(record):
    return f"{record['offense']} offense vs {record['defense']} defense"


def fit_description(text):
    if text is None:
        return None
    if len(text) <= DESCRIPTION_LIMIT:
        return text
    kept = []
    size = 0
    for block in text.split("\n\n"):
        extra = len(block) + (2 if kept else 0)
        if size + extra + len(FIT_NOTE) > DESCRIPTION_LIMIT:
            break
        kept.append(block)
        size += extra
    if not kept:
        return text[: DESCRIPTION_LIMIT - len(FIT_NOTE)] + FIT_NOTE
    return "\n\n".join(kept) + FIT_NOTE


def footer_text(meta):
    if not meta:
        return ""
    parts = []
    if meta.get("season"):
        parts.append(f"Season {meta['season']}")
    if meta.get("week") is not None:
        parts.append(f"Week {meta['week']}")
    if meta.get("note"):
        parts.append(meta["note"])
    return " | ".join(parts)[:2048]


def base_embed(title, description="", meta=None):
    embed = discord.Embed(title=str(title)[:256], description=fit_description(description or "") or None)
    footer = footer_text(meta)
    if footer:
        embed.set_footer(text=footer)
    return embed


def error_title(code):
    if not code or code == "INTERNAL_ERROR":
        return "Error"
    return str(code).replace("_", " ").title()


def format_service_error(error):
    error = error or {}
    code = error.get("code")
    if not code or code == "INTERNAL_ERROR":
        message = UNEXPECTED
    else:
        message = error.get("message") or UNEXPECTED
    return base_embed(error_title(code), message)


def as_embeds(value):
    if isinstance(value, list):
        return value
    return [value]


def highlight_metrics(metrics, limit=4):
    strong = [metric for metric in metrics or [] if metric.get("label") != "NEUTRAL"]
    return strong[:limit]


def call_service(service_call, present):
    from services.errors import AppError

    try:
        result = service_call()
    except Exception:
        logger.exception("command failed")
        return format_service_error({"code": "INTERNAL_ERROR", "message": UNEXPECTED})
    if not result.get("success"):
        return format_service_error(result.get("error"))
    try:
        return present(result)
    except AppError as error:
        return format_service_error({"code": error.code, "message": error.message})
