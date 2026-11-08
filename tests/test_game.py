import unittest

from database.matchups import game_hot_spots, rank_weekly_opportunities
from database.queries import known_team_abbrs, team_on_bye
from services.context import RequestContext
from services.matchup_service import get_game_hot_spots

from interfaces.discord.formatters.matchup import format_game


def _key(record):
    return (record["offense"], record["defense"], record["position"], record["metric"])


class GameHotSpotTests(unittest.TestCase):
    def test_both_sides_keep_existing_hot_scores(self):
        full = {_key(record): record for record in rank_weekly_opportunities()}
        game = game_hot_spots("mia")
        self.assertEqual([side["offense"] for side in game["sides"]], ["MIA", game["defense"]])
        self.assertEqual(game["sides"][1]["defense"], "MIA")
        self.assertNotEqual(game["offense"], game["defense"])
        for side in game["sides"]:
            self.assertTrue(side["spots"])
            scores = [spot["z_score"] for spot in side["spots"]]
            self.assertEqual(scores, sorted(scores, reverse=True))
            for spot in side["spots"]:
                self.assertEqual(spot["label"], "HOT")
                self.assertEqual(spot["offense"], side["offense"])
                source = full[_key(spot)]
                self.assertEqual(spot["z_score"], source["z_score"])
                self.assertEqual(spot["defensive_metric_rank"], source["defensive_metric_rank"])
                self.assertEqual(spot["opportunity_score"], source["opportunity_score"])

    def test_service_titles_the_entered_team_first(self):
        result = get_game_hot_spots("mia", context=RequestContext(caller_id="test"))
        self.assertTrue(result["success"])
        self.assertEqual(result["meta"]["offense"], "MIA")
        embed = format_game(result)
        self.assertTrue(embed.title.startswith("MIA vs "))
        self.assertIn("MIA offense vs", embed.description)
        self.assertIn("HOT", embed.description)

    def test_bye_and_unknown_team(self):
        bye = next(team for team in sorted(known_team_abbrs()) if team_on_bye(team))
        result = get_game_hot_spots(bye, context=RequestContext(caller_id="test"))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "TEAM_NOT_PLAYING")
        unknown = get_game_hot_spots("DTT", context=RequestContext(caller_id="test"))
        self.assertFalse(unknown["success"])
        self.assertEqual(unknown["error"]["code"], "INVALID_TEAM")


if __name__ == "__main__":
    unittest.main()
