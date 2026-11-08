UNEXPECTED = "An unexpected error occurred while processing the command."


def format_service_error(error):
    if not error or error.get("code") == "INTERNAL_ERROR":
        return UNEXPECTED
    return error.get("message") or UNEXPECTED
