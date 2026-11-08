import importlib.util
import logging
import sys
from pathlib import Path

from database.queries import season_status
from services.context import RequestContext
from services.errors import AppError, respond, success

logger = logging.getLogger("services.admin")


def _scraper_module():
    root = Path(__file__).resolve().parents[1]
    scraper_dir = root / "scraper"
    for path in (str(scraper_dir), str(root)):
        if path not in sys.path:
            sys.path.insert(0, path)
    name = "dvp_scraper"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, scraper_dir / "main.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def get_data_status(context=None):
    def action():
        status = season_status()
        if status["dvp_week"] is None:
            raise AppError("SNAPSHOT_NOT_FOUND", "No defensive snapshot is available.")
        meta = {
            "season": status["dvp_season"],
            "week": status["current_week"],
            "snapshot_week": status["dvp_week"],
        }
        return success(status, meta)

    return respond(action)


def update_data(context=None):
    def action():
        ctx = context or RequestContext()
        if ctx.access_level != "ADMIN":
            logger.warning("permission denied for %s", ctx.caller_id)
            raise AppError("PERMISSION_DENIED", "You do not have permission to update data.")
        logger.info("data update started")
        try:
            data = _scraper_module().load_current_snapshot()
        except RuntimeError as error:
            logger.error("data update failed: %s", error)
            raise AppError("INTERNAL_ERROR", str(error)) from error
        logger.info("data update completed season=%s week=%s", data["season"], data["week"])
        return success(data, {"season": data["season"], "week": data["week"], "snapshot_week": data["week"]})

    return respond(action)
