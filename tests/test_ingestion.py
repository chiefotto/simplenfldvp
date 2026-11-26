import unittest

import pandas as pd

from database.abbreviations import canonical_abbr, unknown_abbreviations
from database.analysis import IncompleteMetric, analyze_metric, label_z
from database.storage import STAT_COLUMNS
from scraper.nfl_data import (
    SchemaError,
    prepare_depth_charts,
    prepare_player_stats,
    prepare_players,
    prepare_rosters,
    prepare_snap_counts,
    prepare_teams,
)
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


class PlayerSourceTests(unittest.TestCase):
    def test_depth_charts_keep_history_and_map_missing_gsis(self):
        import sqlite3

        from database.storage import save_depth_charts

        raw = pd.DataFrame([
            {"dt": "2026-11-20T12:00:00Z", "team": "LA", "player_name": "Rams WR", "gsis_id": "00-rams", "pos_abb": "WR", "pos_slot": 1, "pos_rank": 1},
            {"dt": "2026-11-25T12:00:00Z", "team": "DET", "player_name": "By ESPN", "gsis_id": None, "espn_id": "99", "pos_abb": "QB", "pos_slot": 1, "pos_rank": 1},
            {"dt": "2026-11-25T12:00:00Z", "team": "XYZ", "player_name": "Unknown", "gsis_id": "00-x", "pos_abb": "RB", "pos_slot": 1, "pos_rank": 1},
            {"week": 10, "team": "DET", "player_name": "Legacy", "gsis_id": "00-old", "pos_abb": "TE", "pos_slot": 1, "pos_rank": 1, "season": "2025"},
        ])
        with self.assertLogs("database.abbreviations", level="WARNING"):
            prepared = prepare_depth_charts(raw, {"99": "00-espn"}, season=2026)
        self.assertEqual(set(prepared["team"]), {"LAR", "DET", "XYZ"})
        self.assertEqual(prepared.loc[prepared["player_id"] == "00-espn", "season"].iloc[0], "2026")
        legacy = prepared.loc[prepared["player_id"] == "00-old"].iloc[0]
        self.assertEqual(legacy["observed_at"], "2025-W10")
        self.assertEqual(legacy["week"], 10)
        with temporary_database() as path:
            self.assertEqual(save_depth_charts(prepared), len(prepared))
            self.assertEqual(save_depth_charts(prepared), len(prepared))
            self.assertEqual(save_depth_charts(pd.DataFrame()), 0)
            later = prepared.loc[prepared["player_id"] == "00-rams"].assign(pos_rank=2, observed_at="2026-11-27T12:00:00Z")
            save_depth_charts(later)
            with sqlite3.connect(path) as conn:
                count = conn.execute("SELECT COUNT(*) FROM depth_charts").fetchone()[0]
                ranks = conn.execute(
                    "SELECT observed_at, pos_rank FROM depth_charts WHERE player_id = '00-rams' ORDER BY observed_at"
                ).fetchall()
            self.assertEqual(count, len(prepared) + 1)
            self.assertEqual(ranks, [("2026-11-20T12:00:00Z", 1), ("2026-11-27T12:00:00Z", 2)])

    def test_stats_and_snaps_skip_empty_downloads_and_non_regular_season(self):
        import sqlite3

        from database.storage import save_player_stats, save_players, save_snap_counts

        stats = prepare_player_stats(pd.DataFrame([
            {"player_id": "00-1", "player_display_name": "One", "season": 2026, "week": 10, "season_type": "REG", "team": "LA", "position": "QB", "game_id": "g1", "attempts": 20, "passing_tds": 1, "passing_yards": 200, "carries": 2, "rushing_yards": 8, "rushing_tds": 0, "targets": None, "receptions": None, "receiving_yards": None, "receiving_tds": None},
            {"player_id": "00-1", "player_display_name": "One", "season": 2026, "week": 10, "season_type": "REG", "team": "LAR", "position": "QB", "game_id": "g1b", "attempts": 5, "passing_tds": 1, "passing_yards": 40, "carries": 0, "rushing_yards": 0, "rushing_tds": 0, "targets": 0, "receptions": 0, "receiving_yards": 0, "receiving_tds": 0},
            {"player_id": "00-1", "player_display_name": "One", "season": 2026, "week": 19, "season_type": "POST", "team": "LAR", "position": "QB", "attempts": 40, "passing_tds": 4},
            {"player_id": "00-k", "player_display_name": "Kicker", "season": 2026, "week": 10, "season_type": "REG", "team": "DET", "position": "K", "attempts": 0},
        ]))
        self.assertEqual(len(stats), 1)
        self.assertEqual(stats.iloc[0]["team"], "LAR")
        self.assertEqual(stats.iloc[0]["attempts"], 25)
        self.assertEqual(stats.iloc[0]["passing_tds"], 2)
        snaps = prepare_snap_counts(pd.DataFrame([
            {"season": 2026, "week": 10, "game_type": "REG", "team": "LA", "pfr_player_id": "Rams00", "position": "WR", "offense_snaps": 40, "offense_pct": 0.6, "game_id": "g1"},
            {"season": 2026, "week": 10, "game_type": "POST", "team": "LAR", "pfr_player_id": "Rams00", "position": "WR", "offense_snaps": 10, "offense_pct": 0.1},
            {"season": 2026, "week": 10, "game_type": "REG", "team": "DET", "pfr_player_id": "NoMap", "position": "QB", "offense_snaps": 5, "offense_pct": 0.1},
        ]), {"Rams00": "00-1"})
        self.assertEqual(len(snaps), 2)
        self.assertEqual(snaps.loc[snaps["pfr_player_id"] == "Rams00", "player_id"].iloc[0], "00-1")
        self.assertEqual(snaps.loc[snaps["pfr_player_id"] == "Rams00", "team"].iloc[0], "LAR")
        self.assertTrue(snaps.loc[snaps["pfr_player_id"] == "NoMap", "player_id"].isna().all())
        with temporary_database() as path:
            save_players(pd.DataFrame([
                {"player_id": "00-1", "player_name": "One", "position": "qb", "headshot_url": None, "pfr_id": "Rams00", "espn_id": "99"},
            ]))
            self.assertEqual(save_player_stats(stats), 1)
            self.assertEqual(save_player_stats(pd.DataFrame()), 0)
            self.assertEqual(save_snap_counts(snaps), 2)
            self.assertEqual(save_snap_counts(pd.DataFrame()), 0)
            with sqlite3.connect(path) as conn:
                stat_count = conn.execute("SELECT COUNT(*), SUM(attempts) FROM player_weekly_stats").fetchone()
                snap_count = conn.execute("SELECT COUNT(*) FROM player_snap_counts").fetchone()[0]
                pfr = conn.execute("SELECT pfr_id FROM players").fetchone()[0]
            self.assertEqual(stat_count, (1, 25))
            self.assertEqual(snap_count, 2)
            self.assertEqual(pfr, "Rams00")

    def test_stat_aliases_rejects_bad_schema_and_collapses_same_game(self):
        aliased = prepare_player_stats(pd.DataFrame([
            {"gsis_id": "00-1", "player_display_name": "One", "season": 2026, "week": 10, "season_type": "REG", "recent_team": "LA", "position": "QB", "game_id": "g1", "attempts": 10, "passing_tds": 1},
            {"gsis_id": "00-1", "player_display_name": "One", "season": 2026, "week": 10, "season_type": "REG", "recent_team": "LAR", "position": "QB", "game_id": "g1", "attempts": 99, "passing_tds": 3},
        ]))
        self.assertEqual(len(aliased), 1)
        self.assertEqual(aliased.iloc[0]["team"], "LAR")
        self.assertEqual(aliased.iloc[0]["attempts"], 99)
        self.assertEqual(len(prepare_player_stats(pd.DataFrame())), 0)
        with self.assertRaises(SchemaError) as raised:
            prepare_player_stats(pd.DataFrame([{"player_id": "00-1", "season": 2026, "week": 1}]))
        self.assertIn("team", str(raised.exception))
        with self.assertRaises(SchemaError):
            prepare_snap_counts(pd.DataFrame([{"season": 2026, "week": 1, "team": "DET", "offense_snaps": 10}]))
        with self.assertRaises(SchemaError):
            prepare_depth_charts(pd.DataFrame([{"player_name": "No Team", "pos_rank": 1}]))
        dropped = prepare_depth_charts(pd.DataFrame([
            {"dt": "2026-11-20T12:00:00Z", "team": "DET", "player_name": "Placeholder", "gsis_id": "NA", "espn_id": "NA", "pos_abb": "QB", "pos_slot": 1, "pos_rank": 1},
        ]), season=2026)
        self.assertTrue(dropped.empty)


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
