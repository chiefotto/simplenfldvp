import unittest

import pandas as pd

from database.abbreviations import CANONICAL_TEAMS
from database.matchups import POSITION_METRICS
from database.storage import STAT_COLUMNS, save_depth_charts, save_dvp, save_player_stats, save_rosters, save_schedule, save_snap_counts
from services.backtest import evaluate, format_report
from services.player_service import (
    _average,
    _flag_conflicts,
    _games_for,
    _limit,
    _order_players,
    filter_player_rows,
    sort_player_rows,
    weekly_player_opportunities,
)
from tests.db_utils import temporary_database

TEAMS = sorted(CANONICAL_TEAMS)


def _player(player_id, name, status="ACT", position="wr"):
    return {
        "player_id": player_id,
        "player_name": name,
        "team": "ARI",
        "position": position,
        "roster_status": status,
        "headshot_url": None,
    }


def _game(week, targets=0, attempts=0, snaps=10, team="ARI", played=True, via="snaps", receiving_tds=0, passing_tds=0):
    return {
        "week": week,
        "team": team,
        "played": played,
        "via": via,
        "offense_snaps": snaps,
        "values": {
            "targets": targets,
            "attempts": attempts,
            "carries": 0,
            "receiving_tds": receiving_tds,
            "passing_tds": passing_tds,
            "passing_yards": 0,
            "rushing_yards": 0,
            "rushing_tds": 0,
            "receptions": 0,
            "receiving_yards": 0,
        },
    }


class SelectionTests(unittest.TestCase):
    def test_default_limits_exclude_reserves_and_keep_charted_starters(self):
        members = [
            _player("starter", "Starter"),
            _player("other", "Other Starter"),
            _player("backup", "One Game Backup"),
            _player("reserve", "Reserve", status="RES"),
            _player("dev", "Practice", status="DEV"),
        ]
        chart = pd.DataFrame([
            {"player_id": "starter", "pos_rank": 1, "pos_slot": 1},
            {"player_id": "other", "pos_rank": 1, "pos_slot": 2},
            {"player_id": "backup", "pos_rank": 2, "pos_slot": 3},
        ])
        logs = {
            "starter": [_game(week, targets=4) for week in (8, 9, 10)],
            "other": [_game(week, targets=9) for week in (8, 9, 10)],
            "backup": [_game(10, targets=40)],
        }
        ordered = _order_players(members, chart, logs, "wr")
        relevant = _limit(ordered, "wr", "relevant")
        self.assertEqual([player["player_id"] for player in relevant], ["other", "starter", "backup"])
        self.assertEqual(relevant[0]["role"], "WR1")
        self.assertEqual(relevant[0]["role_source"], "Depth chart + recent usage")
        self.assertNotIn("reserve", [player["player_id"] for player in _limit(ordered, "wr", "eligible")])
        self.assertIn("reserve", [player["player_id"] for player in _limit(ordered, "wr", "all")])
        self.assertIsNone(next(player["role"] for player in ordered if player["player_id"] == "reserve"))

    def test_chart_disagreement_keeps_the_starter_and_a_new_starter_can_lack_an_estimate(self):
        members = [
            _player("qb1", "Charted", position="qb"),
            _player("qb2", "Usage", position="qb"),
        ]
        chart = pd.DataFrame([
            {"player_id": "qb1", "pos_rank": 1},
            {"player_id": "qb2", "pos_rank": 2},
        ])
        logs = {
            "qb1": [_game(10, attempts=1)],
            "qb2": [_game(week, attempts=20) for week in (8, 9, 10)],
        }
        ordered = _order_players(members, chart, logs, "qb")
        self.assertEqual(ordered[0]["player_id"], "qb1")
        self.assertEqual(ordered[0]["role_note"], "Role uncertain")
        promoted = _order_players(
            [_player("new", "Promoted", position="qb")],
            pd.DataFrame([{"player_id": "new", "pos_rank": 1}]),
            {},
            "qb",
        )[0]
        average = _average(promoted, "Passing_TD", "season", "ARI", {})
        self.assertIsNone(average["player_avg"])
        self.assertEqual(average["games"], 0)


class AverageTests(unittest.TestCase):
    def test_windows_played_zeros_missed_games_and_future_weeks(self):
        stats = pd.DataFrame([
            {"player_id": "qb", "week": week, "team": "CHI" if week < 6 else "ARI", "passing_tds": 2 if week != 9 else 0, "attempts": 30}
            for week in range(1, 11)
        ] + [
            {"player_id": "qb", "week": 11, "team": "ARI", "passing_tds": 0, "attempts": 0},
            {"player_id": "qb", "week": 12, "team": "ARI", "passing_tds": 9, "attempts": 40},
        ])
        snaps = pd.DataFrame(
            [{"player_id": "qb", "week": week, "team": "ARI", "offense_snaps": 0 if week == 11 else 40} for week in range(1, 13)]
        )
        logs = _games_for(stats, snaps, 12)
        played = [game for game in logs["qb"] if game["played"]]
        self.assertEqual([game["week"] for game in played], list(range(1, 11)))
        self.assertNotIn(12, [game["week"] for game in logs["qb"]])
        player = {"played": played, "player_id": "qb"}
        season = _average(player, "Passing_TD", "season", "ARI", { (10, "ARI"): "2026-11-09" })
        last3 = _average(player, "Passing_TD", "last3", "ARI", {})
        last5 = _average(player, "Passing_TD", "last5", "ARI", {})
        self.assertEqual(season["games"], 10)
        self.assertAlmostEqual(season["player_avg"], 1.8)
        self.assertEqual(last3["games"], 3)
        self.assertAlmostEqual(last3["player_avg"], (2 + 0 + 2) / 3)
        self.assertEqual(last5["games"], 5)
        self.assertTrue(any("previous team" in note for note in season["notes"]))
        self.assertEqual(season["last_date"], "2026-11-09")

    def test_box_score_fallback_is_labeled_and_absent_rows_are_not_zero(self):
        stats = pd.DataFrame([
            {"player_id": "wr", "week": 10, "team": "ARI", "targets": 4, "receiving_tds": None},
        ])
        logs = _games_for(stats, pd.DataFrame(), 12)
        self.assertEqual(logs["wr"][0]["via"], "box")
        player = {"played": logs["wr"], "player_id": "wr"}
        average = _average(player, "Receiving_TD", "season", "ARI", {})
        self.assertIsNone(average["player_avg"])
        self.assertTrue(average["notes"])
        present = _average(player, "Receiving_Targt", "season", "ARI", {})
        self.assertEqual(present["player_avg"], 4)


class OpportunityTests(unittest.TestCase):
    def _dvp(self, week, value_for):
        rows = []
        for position, metrics in POSITION_METRICS.items():
            for index, team in enumerate(TEAMS):
                row = {column: 0.0 for column in STAT_COLUMNS}
                row.update({"season": "2026", "week": week, "team": team, "team_abbr": team, "position": position})
                for metric in metrics:
                    row[metric] = float(value_for(index))
                rows.append(row)
        return pd.DataFrame(rows)

    def test_estimates_ignore_future_charts_stats_and_defense(self):
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
                "away_score": 10,
                "home_score": 7,
            }]), 2026)
            save_dvp(self._dvp(12, lambda index: 100))
            save_dvp(self._dvp(11, lambda index: index))
            save_rosters(pd.DataFrame([
                {"season": "2026", "week": 12, "player_id": "00-qb", "player_name": "Starter", "team": "ARI", "position": "qb", "roster_status": "ACT", "jersey_number": "1", "headshot_url": None},
                {"season": "2026", "week": 12, "player_id": "00-res", "player_name": "Reserve", "team": "ARI", "position": "qb", "roster_status": "RES", "jersey_number": "2", "headshot_url": None},
            ]))
            save_depth_charts(pd.DataFrame([
                {"season": "2026", "observed_at": "2026-11-20T00:00:00Z", "week": None, "team": "ARI", "player_id": "00-qb", "player_name": "Starter", "position": "qb", "pos_abb": "QB", "pos_slot": 1, "pos_rank": 1},
                {"season": "2026", "observed_at": "2026-11-26T00:00:00Z", "week": None, "team": "ARI", "player_id": "00-res", "player_name": "Reserve", "position": "qb", "pos_abb": "QB", "pos_slot": 1, "pos_rank": 1},
            ]))
            stats = []
            snaps = []
            for week in range(1, 11):
                stats.append({"season": "2026", "week": week, "player_id": "00-qb", "player_name": "Starter", "team": "ARI", "position": "qb", "game_id": f"g{week}", "attempts": 30, "passing_yards": 200, "passing_tds": 2, "carries": 2, "rushing_yards": 10, "rushing_tds": 0, "targets": 0, "receptions": 0, "receiving_yards": 0, "receiving_tds": 0})
                snaps.append({"season": "2026", "week": week, "team": "ARI", "pfr_player_id": "PFR", "player_id": "00-qb", "game_id": f"g{week}", "position": "qb", "offense_snaps": 60, "offense_pct": 1})
            stats.append({"season": "2026", "week": 12, "player_id": "00-qb", "player_name": "Starter", "team": "ARI", "position": "qb", "game_id": "future", "attempts": 50, "passing_yards": 400, "passing_tds": 5, "carries": 0, "rushing_yards": 0, "rushing_tds": 0, "targets": 0, "receptions": 0, "receiving_yards": 0, "receiving_tds": 0})
            save_player_stats(pd.DataFrame(stats))
            save_snap_counts(pd.DataFrame(snaps))
            rows = weekly_player_opportunities("2026", 12, baseline="season", scope="relevant")
            passing = [row for row in rows if row["player_id"] == "00-qb" and row["metric"] == "Passing_TD"]
            self.assertEqual(len(passing), 1)
            self.assertEqual(passing[0]["games"], 10)
            self.assertAlmostEqual(passing[0]["player_avg"], 2.0)
            self.assertEqual(passing[0]["snapshot_week"], 11)
            self.assertNotEqual(passing[0]["defense_avg"], 100)
            self.assertEqual(passing[0]["role"], "QB1")
            self.assertEqual(passing[0]["role_source"], "Depth chart")
            self.assertTrue(passing[0]["adjusted"] is None or passing[0]["method"] in {None, "ratio"})
            self.assertNotIn("00-res", {row["player_id"] for row in rows if row["position"] == "qb"})
            everyone = weekly_player_opportunities("2026", 12, scope="all")
            self.assertIn("00-res", {row["player_id"] for row in everyone})
            report = evaluate("2026", "passing_td")
            text = format_report(report)
            self.assertIn("Passing_TD", text)
            self.assertIn("did not play", text)
            self.assertGreaterEqual(report["metrics"]["Passing_TD"]["usable"], 1)

    def test_conflicts_and_sorts_do_not_mix_units(self):
        rows = [
            {"player_id": "a", "offense": "ARI", "metric": "Receiving_Recpt", "adjusted": 8, "z_score": 1},
            {"player_id": "a", "offense": "ARI", "metric": "Receiving_Targt", "adjusted": 5, "z_score": 2, "warning": None},
        ]
        _flag_conflicts(rows)
        self.assertIn("receptions exceed", rows[0]["warning"])
        mixed = sort_player_rows([
            {"metric": "Passing_Yd", "z_score": 0.2, "adjusted": 300},
            {"metric": "Passing_TD", "z_score": 2.0, "adjusted": 1},
        ], "adjusted")
        self.assertEqual(mixed[0]["metric"], "Passing_TD")
        filtered = filter_player_rows(mixed, metric="Passing_TD", minimum_games=0)
        self.assertEqual(len(filtered), 1)


if __name__ == "__main__":
    unittest.main()
