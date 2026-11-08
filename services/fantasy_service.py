from database.fantasy import (
    get_fantasy_offense_matchup as load_fantasy_offense,
    rank_weekly_fantasy_matchups,
    rank_weekly_fantasy_position,
)
from services.catalog import normalize_position, normalize_team
from services.errors import AppError, respond, success
from services.snapshot import snapshot_meta


def _not_playing(team, meta):
    week = meta.get("week")
    when = f" in Week {week}" if week is not None else ""
    raise AppError("TEAM_NOT_PLAYING", f"{team} does not have a scheduled game{when}.")


def get_best_fantasy_matchups(context=None):
    def action():
        meta = snapshot_meta()
        return success(rank_weekly_fantasy_matchups(True), meta)

    return respond(action)


def get_worst_fantasy_matchups(context=None):
    def action():
        meta = snapshot_meta()
        return success(rank_weekly_fantasy_matchups(False), meta)

    return respond(action)


def get_fantasy_position_rankings(position, context=None):
    def action():
        pos = normalize_position(position)
        meta = snapshot_meta(pos)
        return success(rank_weekly_fantasy_position(pos), meta)

    return respond(action)


def get_fantasy_offense_matchup(team, position, context=None):
    def action():
        abbr = normalize_team(team)
        pos = normalize_position(position)
        meta = snapshot_meta(pos)
        record = load_fantasy_offense(abbr, pos)
        if record.get("bye"):
            _not_playing(abbr, meta)
        return success(record, meta)

    return respond(action)
