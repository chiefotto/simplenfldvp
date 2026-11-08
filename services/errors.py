import logging

logger = logging.getLogger("services")


class AppError(Exception):
    def __init__(self, code, message, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def success(data, meta=None):
    return {"success": True, "data": data, "meta": meta or {}}


def failure(error):
    return {
        "success": False,
        "error": {"code": error.code, "message": error.message, "details": error.details},
    }


def respond(action):
    try:
        return action()
    except AppError as error:
        return failure(error)
    except Exception:
        logger.exception("unexpected failure")
        return failure(AppError("INTERNAL_ERROR", "Something went wrong."))
