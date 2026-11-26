import unittest

import pandas as pd

from database.matchups import POSITION_METRICS
from database.storage import STAT_COLUMNS, save_dvp, save_rosters, save_schedule
from services.health import format_health_report, player_data_health
from services.player_service import weekly_player_opportunities
from tests.db_utils import temporary_database
from tests.test_players import TEAMS


class HealthTests(unittest.TestCase):
    def test_missing_player_stats_are_named_and_reported(self):
        with temporary_database():
            save_schedule(pd.DataFrame([{
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
            }]), 2026)
            rows = []
            for position, metrics in POSITION_METRICS.items():
                for index, team in enumerate(TEAMS):
                    row = {column: float(index) for column in STAT_COLUMNS}
                    row.update({"season": "2026", "week": 11, "team": team, "team_abbr": team, "position": position})
                    rows.append(row)
            save_dvp(pd.DataFrame(rows))
            save_rosters(pd.DataFrame([
                {"season": "2026", "week": 12, "player_id": "00-qb", "player_name": "Alpha", "team": "ARI", "position": "qb", "roster_status": "ACT", "jersey_number": "1", "headshot_url": None},
                {"season": "2026", "week": 12, "player_id": "00-two", "player_name": "Bravo", "team": "ARI", "position": "qb", "roster_status": "ACT", "jersey_number": "2", "headshot_url": None},
            ]))
            opportunities = weekly_player_opportunities("2026", 12, scope="relevant")
            self.assertEqual(opportunities, [])
            everyone = weekly_player_opportunities("2026", 12, scope="eligible")
            self.assertTrue(everyone)
            self.assertTrue(all(row["role"] == "Unranked" for row in everyone))
            self.assertTrue(all(row["reason"] == "Player stats not ingested." for row in everyone))
            health = player_data_health("2026", 12)
            self.assertEqual(health["sources"]["stats"]["status"], "Missing")
            self.assertEqual(health["sources"]["defense"]["status"], "Available")
            self.assertIn("Player stats", format_health_report(health))
            self.assertIn("not in the database", health["player_warning"])
