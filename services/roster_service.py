from database.rosters import roster_for, team_directory
from services.errors import respond, success


def get_roster(season, week, team=None, position=None, context=None):
    def action():
        roster = roster_for(season, week, team, position)
        return success(roster, {"season": str(season) if season is not None else None, "week": week})

    return respond(action)


def get_teams(context=None):
    def action():
        return success(team_directory())

    return respond(action)
