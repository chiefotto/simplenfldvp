import unittest

from database.matchups import game_hot_spots, rank_weekly_opportunities, slate_hot_spots
from database.queries import current_schedule, known_team_abbrs, team_on_bye
from services.context import RequestContext
from services.matchup_service import get_game_hot_spots, get_slate_hot_spots

from interfaces.discord.formatters.matchup import format_game, format_slate


def _key(record):
    return (record["offense"], record["defense"], record["position"], record["metric"])


class GameHotSpotTests(unittest.TestCase):
    def test_both_sides_keep_existing_hot_scores(self):
        full = {_key(record): record for record in rank_weekly_opportunities()}
        game = game_hot_spots("mia")
        self.assertEqual([side["offense"] for side in game["sides"]], ["MIA", game["defense"]])
        self.assertEqual(game["sides"][1]["defense"], "MIA")
        self.assertNotEqual(game["offense"], game["defense"])
        offenses = {side["offense"] for side in game["sides"]}
        expected = {
            _key(record)
            for record in full.values()
            if record["offense"] in offenses and record["label"] in {"HOT", "WARM"}
        }
        shown = set()
        for side in game["sides"]:
            self.assertTrue(side["spots"])
            scores = [spot["z_score"] for spot in side["spots"]]
            self.assertEqual(scores, sorted(scores, reverse=True))
            for spot in side["spots"]:
                self.assertIn(spot["label"], {"HOT", "WARM"})
                self.assertEqual(spot["offense"], side["offense"])
                source = full[_key(spot)]
                self.assertEqual(spot["z_score"], source["z_score"])
                self.assertEqual(spot["defensive_metric_rank"], source["defensive_metric_rank"])
                self.assertEqual(spot["opportunity_score"], source["opportunity_score"])
                shown.add(_key(spot))
        self.assertEqual(shown, expected)
        self.assertIn("WARM", {spot["label"] for side in game["sides"] for spot in side["spots"]})

    def test_service_titles_the_entered_team_first(self):
        result = get_game_hot_spots("mia", context=RequestContext(caller_id="test"))
        self.assertTrue(result["success"])
        self.assertEqual(result["meta"]["offense"], "MIA")
        embed = format_game(result)
        self.assertTrue(embed.title.startswith("MIA vs "))
        self.assertIn("MIA offense vs", embed.description)
        self.assertIn("HOT", embed.description)
        self.assertIn("WARM", embed.description)

    def test_bye_and_unknown_team(self):
        bye = next(team for team in sorted(known_team_abbrs()) if team_on_bye(team))
        result = get_game_hot_spots(bye, context=RequestContext(caller_id="test"))
        self.assertFalse(result["success"])
        self.assertEqual(result["error"]["code"], "TEAM_NOT_PLAYING")
        unknown = get_game_hot_spots("DTT", context=RequestContext(caller_id="test"))
        self.assertFalse(unknown["success"])
        self.assertEqual(unknown["error"]["code"], "INVALID_TEAM")


class SlateHotSpotTests(unittest.TestCase):
    def test_every_scheduled_game_keeps_hot_and_warm_spots(self):
        full = {_key(record): record for record in rank_weekly_opportunities()}
        schedule = list(current_schedule().itertuples(index=False))
        slate = slate_hot_spots()
        self.assertEqual(len(slate["games"]), len(schedule))
        seen = set()
        for game, row in zip(slate["games"], schedule):
            self.assertEqual(game["offense"], row.away_team)
            self.assertEqual(game["defense"], row.home_team)
            self.assertEqual([side["offense"] for side in game["sides"]], [row.away_team, row.home_team])
            self.assertEqual(game["sides"][1]["defense"], row.away_team)
            pair = frozenset((row.away_team, row.home_team))
            self.assertNotIn(pair, seen)
            seen.add(pair)
            offenses = {side["offense"] for side in game["sides"]}
            expected = {
                _key(record)
                for record in full.values()
                if record["offense"] in offenses and record["label"] in {"HOT", "WARM"}
            }
            shown = set()
            for side in game["sides"]:
                scores = [spot["z_score"] for spot in side["spots"]]
                self.assertEqual(scores, sorted(scores, reverse=True))
                for spot in side["spots"]:
                    self.assertIn(spot["label"], {"HOT", "WARM"})
                    self.assertEqual(spot["offense"], side["offense"])
                    source = full[_key(spot)]
                    self.assertEqual(spot["z_score"], source["z_score"])
                    self.assertEqual(spot["defensive_metric_rank"], source["defensive_metric_rank"])
                    shown.add(_key(spot))
            self.assertEqual(shown, expected)

    def test_service_formats_one_embed_per_game(self):
        result = get_slate_hot_spots(context=RequestContext(caller_id="test"))
        self.assertTrue(result["success"])
        embeds = format_slate(result)
        games = result["data"]["games"]
        self.assertEqual(len(embeds), len(games))
        self.assertTrue(embeds[0].title.startswith(f"{games[0]['offense']} vs "))
        self.assertIn(f"Week {result['meta']['week']}", embeds[0].title)
        bodies = "\n".join(embed.description or "" for embed in embeds)
        self.assertIn("HOT", bodies)
        self.assertIn("WARM", bodies)

    def test_empty_slate_embed(self):
        embed = format_slate({"data": {"games": []}, "meta": {"week": 12}})
        self.assertEqual(embed.title, "Week 12 Slate")
        self.assertEqual(embed.description, "No games.")


if __name__ == "__main__":
    unittest.main()
