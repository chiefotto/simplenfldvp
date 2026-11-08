import unittest

from database.matchups import metric_opportunities, rank_weekly_opportunities
from services.context import RequestContext
from services.opportunity_service import get_top_weekly_opportunities

from interfaces.discord.formatters.matchup import format_opportunities


def _key(record):
    return (record["offense"], record["defense"], record["position"], record["metric"])


class MetricOpportunityTests(unittest.TestCase):
    def test_receptions_keep_skill_positions_and_existing_scores(self):
        full = {_key(record): record for record in rank_weekly_opportunities()}
        rows = metric_opportunities("receptions")
        self.assertEqual(rows[0]["weekly_rank"], 1)
        self.assertTrue(rows)
        for record in rows:
            self.assertEqual(record["metric"], "Receiving_Recpt")
            self.assertIn(record["position"], {"rb", "wr", "te"})
            source = full[_key(record)]
            self.assertEqual(record["z_score"], source["z_score"])
            self.assertEqual(record["opportunity_score"], source["opportunity_score"])
            self.assertEqual(record["defensive_metric_rank"], source["defensive_metric_rank"])

    def test_rushing_yards_are_qb_and_rb(self):
        rows = metric_opportunities("rushing_yards")
        self.assertTrue(rows)
        self.assertEqual({record["position"] for record in rows}, {"qb", "rb"})
        self.assertTrue(all(record["metric"] == "Rushing_Yd" for record in rows))

    def test_unknown_stat_is_rejected(self):
        result = get_top_weekly_opportunities(5, "tackles", context=RequestContext(caller_id="test"))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "INVALID_METRIC")

    def test_omitted_stat_still_mixes_metrics(self):
        full = rank_weekly_opportunities()
        self.assertGreater(len({record["metric"] for record in full}), 1)
        result = get_top_weekly_opportunities(5, context=RequestContext(caller_id="test"))
        self.assertTrue(result["success"])
        self.assertNotIn("metric", result["meta"])
        self.assertEqual([_key(record) for record in result["data"]], [_key(record) for record in full[:5]])

    def test_service_reports_positions_and_embed_title(self):
        result = get_top_weekly_opportunities(10, "receptions", context=RequestContext(caller_id="test"))
        self.assertEqual(result["meta"]["metric"], "Receiving_Recpt")
        self.assertEqual(result["meta"]["positions"], ["rb", "wr", "te"])
        self.assertLessEqual(len(result["data"]), 10)
        embed = format_opportunities(result, 10)
        self.assertTrue(embed.title.startswith("Top Receiving Receptions Opportunities"))
        self.assertIn("Positions: RB, WR, TE", embed.description)
        self.assertIn("RB", embed.description)


if __name__ == "__main__":
    unittest.main()
