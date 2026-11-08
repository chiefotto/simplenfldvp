import logging

UNEXPECTED = "An unexpected error occurred while processing the command."
MESSAGE_LIMIT = 2000
FIT_NOTE = "\nShowing the lines that fit."

logger = logging.getLogger("interfaces.discord")


def format_service_error(error):
    if not error or error.get("code") == "INTERNAL_ERROR":
        return UNEXPECTED
    return error.get("message") or UNEXPECTED


def signed(value):
    if value is None:
        return "n/a"
    return f"{float(value):+.2f}"


def fit_message(text):
    if len(text) <= MESSAGE_LIMIT:
        return text
    kept = []
    size = 0
    for line in text.splitlines():
        extra = len(line) + (1 if kept else 0)
        if size + extra + len(FIT_NOTE) > MESSAGE_LIMIT:
            break
        kept.append(line)
        size += extra
    if not kept:
        return text[: MESSAGE_LIMIT - len(FIT_NOTE)] + FIT_NOTE
    return "\n".join(kept) + FIT_NOTE


def call_service(service_call, present):
    from services.errors import AppError

    try:
        result = service_call()
    except Exception:
        logger.exception("command failed")
        return UNEXPECTED
    if not result.get("success"):
        return format_service_error(result.get("error"))
    try:
        return fit_message(present(result))
    except AppError as error:
        return error.message
