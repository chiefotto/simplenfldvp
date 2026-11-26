from urllib.parse import urlencode


def app_url(base, path="", **params):
    if not base or not str(base).strip():
        return None
    root = str(base).strip().rstrip("/")
    query = urlencode({key: value for key, value in params.items() if value is not None and value != ""})
    route = "" if path in (None, "", "/") else "/" + str(path).strip("/")
    target = f"{root}/" if not route else f"{root}{route}"
    if query:
        return f"{target}?{query}"
    return target


def weekly_url(base, season, week, **extra):
    return app_url(base, "", season=season, week=week, **extra)


def schedule_url(base, season, week):
    return app_url(base, "schedule", season=season, week=week)


def game_url(base, season, week, game_id):
    return app_url(base, "game", season=season, week=week, game_id=game_id)


def rankings_url(base, season, week, position=None, metric=None):
    return app_url(base, "rankings", season=season, week=week, position=position, metric=metric)
