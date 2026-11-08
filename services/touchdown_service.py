from database.matchups import touchdown_opportunities
from database.queries import team_on_bye
from services.catalog import normalize_position, normalize_team, normalize_top_n
from services.errors import AppError, respond, success
from services.snapshot import snapshot_meta


def _not_playing(team, meta):
    week = meta.get("week")
    when = f" in Week {week}" if week is not None else ""
    raise AppError("TEAM_NOT_PLAYING", f"{team} does not have a scheduled game{when}.")


def get_best_touchdown_opportunities(position=None, top_n=None, context=None):
    def action():
        pos = normalize_position(position) if position else None
        count = normalize_top_n(top_n)
        meta = snapshot_meta(pos)
        meta["top_n"] = count
        return success(touchdown_opportunities(pos)[:count], meta)

    return respond(action)


def get_touchdown_offense(team, context=None):
    def action():
        abbr = normalize_team(team)
        meta = snapshot_meta()
        if team_on_bye(abbr):
            _not_playing(abbr, meta)
        rows = [record for record in touchdown_opportunities() if record["offense"] == abbr]
        if not rows:
            _not_playing(abbr, meta)
        rows.sort(key=lambda record: record["z_score"], reverse=True)
        return success(rows, meta)

    return respond(action)
