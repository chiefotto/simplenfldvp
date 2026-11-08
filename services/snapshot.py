from database.queries import matchup_context, season_status
from services.errors import AppError


def snapshot_meta(position=None):
    season, defense_week, note = matchup_context()
    status = season_status()
    if defense_week is None:
        raise AppError("SNAPSHOT_NOT_FOUND", "No defensive snapshot is available.")
    meta = {
        "season": season,
        "week": status["current_week"],
        "snapshot_week": defense_week,
        "note": note,
    }
    if position:
        meta["position"] = position
    return meta
