from database.matchups import rank_weekly_opportunities
from services.catalog import normalize_top_n
from services.errors import respond, success
from services.snapshot import snapshot_meta


def get_top_weekly_opportunities(top_n=None, context=None):
    def action():
        count = normalize_top_n(top_n)
        meta = snapshot_meta()
        meta["top_n"] = count
        return success(rank_weekly_opportunities()[:count], meta)

    return respond(action)
