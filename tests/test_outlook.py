import unittest

import pandas as pd

from database.abbreviations import CANONICAL_TEAMS
from database.matchups import POSITION_METRICS, rank_weekly_opportunities
from database.queries import defense_snapshot_for, week_games
from database.rosters import roster_for
from database.storage import STAT_COLUMNS, save_dvp, save_rosters, save_schedule
from services.context import RequestContext
from services.outlook_service import (
    describe_spot,
    filter_ranking_rows,
    get_game_link,
    get_game_outlook,
    get_leaderboards,
    get_rankings_link,
    get_weekly_link,
)
from tests.db_utils import temporary_database

TEAMS = sorted(CANONICAL_TEAMS)


def _dvp(week, value_for):
    rows = []
    for position, metrics in POSITION_METRICS.items():
        for index, team in enumerate(TEAMS):
            row = {column: 0.0 for column in STAT_COLUMNS}
            row.update({
                "season": "2026",
                "week": week,
                "team": team,
                "team_abbr": team,
                "position": position,
            })
            for metric in metrics:
                row[metric] = float(value_for(index))
            rows.append(row)
    return pd.DataFrame(rows)


def _schedule():
    return pd.DataFrame([{
        "game_id": "2026_12_ARI_WAS",
        "season": 2026,
        "week": 12,
        "game_type": "REG",
        "gameday": "2026-11-26",
        "gametime": "13:00",
        "away_team": "ARI",
        "home_team": "WAS",
        "away_score": None,
        "home_score": None,
    }])


class OutlookTests(unittest.TestCase):
    def test_snapshot_never_uses_a_future_defense_week(self):
        with temporary_database():
            save_schedule(_schedule(), 2026)
            save_dvp(_dvp(12, lambda index: 100))
            self.assertEqual(defense_snapshot_for("2026", 12)[1], None)
            self.assertEqual(rank_weekly_opportunities("2026", 12), [])
            save_dvp(_dvp(11, lambda index: index))
            snapshot = defense_snapshot_for("2026", 12)
            self.assertEqual(snapshot[1], 11)
            self.assertIsNone(snapshot[2])
            records = rank_weekly_opportunities("2026", 12)
            self.assertTrue(records)
            self.assertTrue(all(record["snapshot_week"] == 11 for record in records))
            self.assertTrue(any(record["label"] == "HOT" for record in records))
            self.assertFalse(all(record["z_score"] == 0 for record in records))

    def test_leaderboard_and_game_attach_the_offense_roster(self):
        with temporary_database():
            save_schedule(_schedule(), 2026)
            save_dvp(_dvp(11, lambda index: index))
            save_rosters(pd.DataFrame([
                {"season": "2026", "week": 12, "player_id": "00-12", "player_name": "Current Player", "team": "ARI", "position": "wr", "roster_status": "ACT", "jersey_number": "14", "headshot_url": "http://current"},
                {"season": "2026", "week": 12, "player_id": "00-chi", "player_name": "Chicago Player", "team": "CHI", "position": "wr", "roster_status": "ACT", "jersey_number": "1", "headshot_url": None},
                {"season": "2026", "week": 13, "player_id": "00-13", "player_name": "Future Player", "team": "ARI", "position": "wr", "roster_status": "INA", "jersey_number": "19", "headshot_url": None},
            ]))
            early = roster_for("2026", 10, "ARI", "wr")
            self.assertEqual(early["players"], [])
            self.assertIn("unavailable", early["roster_note"])
            current = roster_for("2026", 12, "ARI", "wr")
            self.assertEqual([player["player_name"] for player in current["players"]], ["Current Player"])
            later = roster_for("2026", 14, "ARI", "wr")
            self.assertEqual(later["roster_week"], 13)
            self.assertEqual([player["player_name"] for player in later["players"]], ["Future Player"])
            self.assertIn("week 13", later["roster_note"])

            boards = get_leaderboards("2026", 12, top=3, metric="receiving_td", best=True, context=RequestContext(caller_id="test"))
            self.assertTrue(boards["success"])
            receiving = boards["data"]["categories"]
            self.assertEqual(len(receiving), 1)
            self.assertLessEqual(len(receiving[0]["rows"]), 3)
            self.assertEqual(receiving[0]["rows"][0]["display_rank"], 1)
            worst = get_leaderboards("2026", 12, top=1, metric="receiving_td", best=False, context=RequestContext(caller_id="test"))
            self.assertLess(worst["data"]["categories"][0]["rows"][0]["z_score"], receiving[0]["rows"][0]["z_score"])

            game = get_game_outlook("2026_12_ARI_WAS", "2026", 12, context=RequestContext(caller_id="test"))
            self.assertTrue(game["success"])
            sides = {side["offense"]: side for side in game["data"]["sides"]}
            self.assertEqual(set(sides), {"ARI", "WAS"})
            cardinals = sides["ARI"]["positions"][2]
            self.assertEqual(cardinals["position"], "wr")
            self.assertEqual([player["player_name"] for player in cardinals["players"]], ["Current Player"])
            self.assertNotIn("Chicago Player", [player["player_name"] for player in cardinals["players"]])
            self.assertNotIn("Future Player", [player["player_name"] for player in cardinals["players"]])
            self.assertTrue(cardinals["spots"])
            self.assertIn("than the league average", describe_spot(cardinals["spots"][0]))
            self.assertEqual({spot["defense"] for spot in sides["ARI"]["spots"]}, {"WAS"})

    def test_filters_do_not_change_scores(self):
        rows = [
            {"offense": "DET", "defense": "CHI", "position": "wr", "metric": "Receiving_TD", "z_score": 2.0, "label": "HOT", "weekly_rank": 1},
            {"offense": "CHI", "defense": "DET", "position": "qb", "metric": "Passing_TD", "z_score": -2.0, "label": "COLD", "weekly_rank": 2},
        ]
        filtered = filter_ranking_rows(rows, position="wr", flags=["HOT"])
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["z_score"], 2.0)
        self.assertEqual(filtered[0]["weekly_rank"], 1)
        frame = pd.DataFrame(filtered)
        exported = frame.to_csv(index=False)
        self.assertIn("DET", exported)
        self.assertNotIn("Passing_TD", exported)


class OutlookLinkTests(unittest.TestCase):
    def test_weekly_and_rankings_urls(self):
        weekly = get_weekly_link("https://dvp.example/", 2026, 12, context=RequestContext(caller_id="test"))
        self.assertTrue(weekly["success"])
        self.assertEqual(weekly["data"]["url"], "https://dvp.example/?season=2026&week=12")
        missing = get_weekly_link("", 2026, 12, context=RequestContext(caller_id="test"))
        self.assertTrue(missing["success"])
        self.assertIsNone(missing["data"]["url"])
        self.assertIn("WEB_APP_BASE_URL", missing["data"]["description"])
        rankings = get_rankings_link("https://dvp.example", "wr", None, 2026, 12, context=RequestContext(caller_id="test"))
        self.assertIn("position=WR", rankings["data"]["url"])
        self.assertTrue(rankings["data"]["url"].startswith("https://dvp.example/rankings?"))
        rejected = get_rankings_link("https://dvp.example", "wr", "passing_td", 2026, 12, context=RequestContext(caller_id="test"))
        self.assertFalse(rejected["success"])
        self.assertEqual(rejected["error"]["code"], "INVALID_METRIC_FOR_POSITION")

    def test_game_link_and_bye_week(self):
        with temporary_database():
            save_schedule(_schedule(), 2026)
            save_dvp(_dvp(11, lambda index: index))
            found = get_game_link("https://dvp.example", "ARI", 2026, 12, context=RequestContext(caller_id="test"))
            self.assertTrue(found["success"])
            self.assertIn("game_id=2026_12_ARI_WAS", found["data"]["url"])
            self.assertIn("/game?", found["data"]["url"])
            bye = get_game_link("https://dvp.example", "CHI", 2026, 12, context=RequestContext(caller_id="test"))
            self.assertEqual(bye["error"]["code"], "TEAM_NOT_PLAYING")
            unknown = get_game_link("https://dvp.example", "DTT", 2026, 12, context=RequestContext(caller_id="test"))
            self.assertEqual(unknown["error"]["code"], "INVALID_TEAM")
            games = week_games("2026", 12)
            self.assertEqual(games.iloc[0]["away_team"], "ARI")
