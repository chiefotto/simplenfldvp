from database.matchups import (
    get_defense_profile as load_defense_profile,
    get_offense_matchup as load_offense_matchup,
    rank_weekly_matchups,
    rank_weekly_metric,
)
from services.catalog import normalize_metric, normalize_position, normalize_team
from services.errors import AppError, respond, success
from services.snapshot import snapshot_meta


def _not_playing(team, meta):
    week = meta.get("week")
    when = f" in Week {week}" if week is not None else ""
    raise AppError("TEAM_NOT_PLAYING", f"{team} does not have a scheduled game{when}.")


def get_best_position_matchups(position, context=None):
    def action():
        pos = normalize_position(position)
        meta = snapshot_meta(pos)
        return success(rank_weekly_matchups(pos), meta)

    return respond(action)


def get_best_metric_matchups(position, metric, context=None):
    def action():
        pos = normalize_position(position)
        canonical = normalize_metric(pos, metric)
        meta = snapshot_meta(pos)
        meta["metric"] = canonical
        return success(rank_weekly_metric(pos, canonical), meta)

    return respond(action)


def get_defense_profile(team, position, context=None):
    def action():
        abbr = normalize_team(team)
        pos = normalize_position(position)
        meta = snapshot_meta(pos)
        try:
            profile = load_defense_profile(abbr, pos)
        except ValueError as error:
            raise AppError("SNAPSHOT_NOT_FOUND", str(error)) from error
        return success(profile, meta)

    return respond(action)


def get_offense_matchup(team, position, context=None):
    def action():
        abbr = normalize_team(team)
        pos = normalize_position(position)
        meta = snapshot_meta(pos)
        record = load_offense_matchup(abbr, pos)
        if record.get("bye"):
            _not_playing(abbr, meta)
        return success(record, meta)

    return respond(action)
