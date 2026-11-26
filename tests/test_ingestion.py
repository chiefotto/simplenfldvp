import unittest

import pandas as pd

from database.abbreviations import canonical_abbr, unknown_abbreviations
from database.analysis import IncompleteMetric, analyze_metric, label_z
from database.storage import STAT_COLUMNS
from scraper.nfl_data import prepare_players, prepare_rosters, prepare_teams
from scraper.schedule import completed_week
from tests.db_utils import temporary_database


class AbbreviationTests(unittest.TestCase):
    def test_rams_alias_is_explicit(self):
        self.assertEqual(canonical_abbr("la"), "LAR")
        self.assertEqual(canonical_abbr("LAR"), "LAR")
        self.assertIn("XYZ", unknown_abbreviations(["XYZ", "LAR", "LA"]))
        self.assertNotIn("LA", unknown_abbreviations(["LA"]))

    def test_team_frame_prefers_canonical_rams_row(self):
        prepared = prepare_teams(pd.DataFrame([
            {"team_abbr": "LA", "team_name": "Los Angeles Rams", "team_logo_espn": "http://la", "team_color": "#111", "team_color2": "#222"},
            {"team_abbr": "LAR", "team_name": "Los Angeles Rams", "team_logo_espn": "http://lar", "team_color": "#003", "team_color2": "#fff"},
        ]))
        self.assertEqual(prepared.iloc[0]["team_abbr"], "LAR")
        self.assertEqual(prepared.iloc[0]["team_logo_url"], "http://lar")

    def test_only_nflverse_rams_abbreviation_is_stored_as_lar(self):
        prepared = prepare_teams(pd.DataFrame([
            {"team_abbr": "LA", "team_name": "Los Angeles Rams", "team_logo_wikipedia": "http://la"},
        ]))
        self.assertEqual(prepared.iloc[0]["team_abbr"], "LAR")
        self.assertEqual(prepared.iloc[0]["team_logo_url"], "http://la")


class RosterPreparationTests(unittest.TestCase):
    def test_skill_positions_deduped_and_unknown_teams_kept(self):
        raw = pd.DataFrame([
            {"season": 2026, "week": 12, "gsis_id": "00-1", "full_name": "A Player", "team": "DET", "position": "WR", "status": "ACT", "jersey_number": 11, "headshot_url": "http://a"},
            {"season": 2026, "week": 12, "gsis_id": "00-1", "full_name": "A Player Updated", "team": "DET", "position": "WR", "status": "INA", "jersey_number": 11},
            {"season": 2026, "week": 12, "gsis_id": "00-2", "full_name": "Lineman", "team": "DET", "position": "OL", "status": "ACT"},
            {"season": 2026, "week": 12, "gsis_id": "00-3", "full_name": "Mystery", "team": "XYZ", "position": "QB", "status": "ACT"},
        ])
        with self.assertLogs("database.abbreviations", level="WARNING") as logs:
            prepared = prepare_rosters(raw)
        self.assertEqual(len(prepared), 2)
        updated = prepared.loc[prepared["player_id"] == "00-1"].iloc[0]
        self.assertEqual(updated["player_name"], "A Player Updated")
        self.assertEqual(updated["position"], "wr")
        self.assertEqual(updated["roster_status"], "INA")
        self.assertIn("XYZ", prepared["team"].tolist())
        self.assertTrue(any("XYZ" in message for message in logs.output))

    def test_player_metadata_uses_stable_id(self):
        prepared = prepare_players(pd.DataFrame([
            {"gsis_id": "00-9", "display_name": "Named", "position": "RB", "headshot": "http://face"},
            {"gsis_id": None, "display_name": "Dropped", "position": "RB"},
        ]))
        self.assertEqual(len(prepared), 1)
        self.assertEqual(prepared.iloc[0]["player_id"], "00-9")
        self.assertEqual(prepared.iloc[0]["headshot_url"], "http://face")


class PersistenceTests(unittest.TestCase):
    def test_upserts_are_idempotent_and_do_not_erase_history(self):
        from database.storage import save_players, save_rosters, save_schedule, save_teams
        import sqlite3

        with temporary_database() as path:
            self.assertEqual(save_teams(pd.DataFrame()), 0)
            self.assertEqual(save_teams(pd.DataFrame([
                {"team_abbr": "DET", "team_name": "Detroit Lions", "team_logo_url": "http://det", "color_primary": "#0076b6", "color_secondary": "#b0b7bc"},
            ])), 1)
            self.assertEqual(save_teams(pd.DataFrame([
                {"team_abbr": "DET", "team_name": "Detroit Lions", "team_logo_url": None, "color_primary": "#0076b6", "color_secondary": None},
            ])), 1)
            with sqlite3.connect(path) as conn:
                logo, color = conn.execute("SELECT team_logo_url, color_secondary FROM teams").fetchone()
            self.assertEqual(logo, "http://det")
            self.assertEqual(color, "#b0b7bc")

            first = pd.DataFrame([
                {"season": "2026", "week": 12, "player_id": "00-1", "player_name": "Week Twelve", "team": "DET", "position": "wr", "roster_status": "ACT", "jersey_number": "14", "headshot_url": "http://w12"},
            ])
            later = pd.DataFrame([
                {"season": "2026", "week": 13, "player_id": "00-2", "player_name": "Week Thirteen", "team": "DET", "position": "wr", "roster_status": "ACT", "jersey_number": "15", "headshot_url": None},
            ])
            self.assertEqual(save_rosters(first), 1)
            self.assertEqual(save_rosters(first.assign(player_name="Week Twelve Updated")), 1)
            self.assertEqual(save_rosters(pd.DataFrame()), 0)
            self.assertEqual(save_rosters(later), 1)
            self.assertEqual(save_players(pd.DataFrame([
                {"player_id": "00-1", "player_name": "Week Twelve Updated", "position": "wr", "headshot_url": "http://w12"},
            ])), 1)
            with sqlite3.connect(path) as conn:
                rows = conn.execute("SELECT week, player_name FROM weekly_rosters ORDER BY week").fetchall()
            self.assertEqual(rows, [(12, "Week Twelve Updated"), (13, "Week Thirteen")])

            schedule = pd.DataFrame([{
                "game_id": "2026_12_LA_DET",
                "season": 2026,
                "week": 12,
                "game_type": "REG",
                "gameday": "2026-11-26",
                "gametime": "13:00",
                "away_team": "LA",
                "home_team": "DET",
                "away_score": None,
                "home_score": None,
            }])
            self.assertEqual(save_schedule(schedule, 2026), 1)
            self.assertEqual(save_schedule(pd.DataFrame(), 2026), 0)
            with sqlite3.connect(path) as conn:
                teams = conn.execute("SELECT away_team, home_team FROM schedule").fetchone()
            self.assertEqual(teams, ("LAR", "DET"))


class AnalysisRegressionTests(unittest.TestCase):
    def test_flag_thresholds_match_the_readme(self):
        self.assertEqual(label_z(1.5), "HOT")
        self.assertEqual(label_z(1.0), "WARM")
        self.assertEqual(label_z(0.99), "NEUTRAL")
        self.assertEqual(label_z(-0.99), "NEUTRAL")
        self.assertEqual(label_z(-1.0), "COOL")
        self.assertEqual(label_z(-1.49), "COOL")
        self.assertEqual(label_z(-1.5), "COLD")

    def test_ties_share_a_rank_and_missing_metrics_are_skipped(self):
        frame = pd.DataFrame({
            "team": ["A", "B"],
            "team_abbr": ["A", "B"],
            "position": ["qb", "qb"],
            "season": ["2026", "2026"],
            "week": [1, 1],
            "Passing_Yd": [10.0, 10.0],
        })
        scored = analyze_metric(frame, "qb", "Passing_Yd", expected_teams=2)
        self.assertEqual(list(scored["rank"]), [1, 1])
        self.assertEqual(set(scored["label"]), {"NEUTRAL"})
        incomplete = frame.copy()
        incomplete.loc[1, "Passing_Yd"] = None
        with self.assertRaises(IncompleteMetric):
            analyze_metric(incomplete, "qb", "Passing_Yd", expected_teams=2)

    def test_partial_week_is_not_complete(self):
        schedule = pd.DataFrame({
            "season": [2026, 2026, 2026],
            "week": [1, 1, 2],
            "away_score": [7, None, 10],
            "home_score": [3, None, 14],
        })
        self.assertIsNone(completed_week(schedule.loc[schedule["week"] == 1], 2026))
        self.assertEqual(completed_week(schedule, 2026), 2)
        self.assertTrue(STAT_COLUMNS)
