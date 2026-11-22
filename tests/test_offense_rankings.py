import unittest

from database.matchups import offense_stat_rankings, rank_weekly_opportunities
from database.queries import known_team_abbrs, team_on_bye
from services.context import RequestContext
from services.matchup_service import get_offense_stat_rankings

from interfaces.discord.formatters.matchup import format_offense_rankings


def _key(record):
    return (record["offense"], record["defense"], record["position"], record["metric"])


class OffenseRankingTests(unittest.TestCase):
    def test_every_stat_stays_on_the_existing_score(self):
        full = {_key(record): record for record in rank_weekly_opportunities() if record["offense"] == "CHI"}
        ranking = offense_stat_rankings("chi")
        spots = ranking["spots"]
        self.assertEqual(ranking["offense"], "CHI")
        self.assertNotEqual(ranking["defense"], "CHI")
        self.assertEqual({_key(spot) for spot in spots}, set(full))
        self.assertGreater(len({spot["position"] for spot in spots}), 1)
        self.assertGreater(len({spot["label"] for spot in spots}), 1)
        scores = [spot["z_score"] for spot in spots]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(spots[0]["offense_rank"], 1)
        for spot in spots:
            source = full[_key(spot)]
            self.assertEqual(spot["z_score"], source["z_score"])
            self.assertEqual(spot["defensive_metric_rank"], source["defensive_metric_rank"])

    def test_embed_names_the_offense(self):
        result = get_offense_stat_rankings("chi", context=RequestContext(caller_id="test"))
        self.assertTrue(result["success"])
        embed = format_offense_rankings(result)
        self.assertTrue(embed.title.startswith("CHI offense vs "))
        self.assertIn(result["data"]["spots"][0]["position"].upper(), embed.description)

    def test_bye_and_unknown_team(self):
        bye = next(team for team in sorted(known_team_abbrs()) if team_on_bye(team))
        result = get_offense_stat_rankings(bye, context=RequestContext(caller_id="test"))
        self.assertEqual(result["error"]["code"], "TEAM_NOT_PLAYING")
        unknown = get_offense_stat_rankings("DTT", context=RequestContext(caller_id="test"))
        self.assertEqual(unknown["error"]["code"], "INVALID_TEAM")


if __name__ == "__main__":
    unittest.main()
