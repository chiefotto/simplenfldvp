from database.matchups import metric_opportunities, positions_for_metric, rank_weekly_opportunities
from services.catalog import normalize_metric_alias, normalize_top_n
from services.errors import respond, success
from services.snapshot import snapshot_meta


def get_top_weekly_opportunities(top_n=None, metric=None, context=None):
    def action():
        count = normalize_top_n(top_n)
        meta = snapshot_meta()
        meta["top_n"] = count
        if metric is None:
            return success(rank_weekly_opportunities()[:count], meta)
        canonical = normalize_metric_alias(metric)
        meta["metric"] = canonical
        meta["positions"] = positions_for_metric(canonical)
        return success(metric_opportunities(canonical)[:count], meta)

    return respond(action)
