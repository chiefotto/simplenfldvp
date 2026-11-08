import logging
import unittest
from types import SimpleNamespace

from services.context import RequestContext

from interfaces.discord.config import load_config
from interfaces.discord.context import access_level_for, request_context
from interfaces.discord.formatters.common import UNEXPECTED, format_service_error
from interfaces.discord.formatters.help import format_help
from interfaces.discord.formatters.matchup import format_opportunities, render_best_matchup


class Role:
    def __init__(self, role_id):
        self.id = role_id


class User:
    def __init__(self, user_id, role_ids=()):
        self.id = user_id
        self.roles = [Role(role_id) for role_id in role_ids]


class ConfigTests(unittest.TestCase):
    def test_missing_token(self):
        with self.assertRaises(RuntimeError) as raised:
            load_config(environ={})
        self.assertEqual(str(raised.exception), "DISCORD_BOT_TOKEN is not configured.")

    def test_token_is_not_logged(self):
        with self.assertLogs("interfaces.discord", level=logging.INFO) as logs:
            logging.getLogger("interfaces.discord").info("bot starting")
            config = load_config(environ={"DISCORD_BOT_TOKEN": "secret-token", "DISCORD_GUILD_ID": "42"})
        self.assertEqual(config.token, "secret-token")
        self.assertEqual(config.guild_id, 42)
        self.assertNotIn("secret-token", "\n".join(logs.output))


class ContextTests(unittest.TestCase):
    def test_public_caller(self):
        context = request_context(User(123))
        self.assertEqual(context, RequestContext(interface="discord", caller_id="123", access_level="PUBLIC"))

    def test_admin_role_mapping(self):
        user = User(7, role_ids=(99,))
        self.assertEqual(access_level_for(user, None), "PUBLIC")
        self.assertEqual(access_level_for(user, 99), "ADMIN")
        self.assertEqual(access_level_for(user, 100), "PUBLIC")
        self.assertEqual(request_context(user, 99).access_level, "ADMIN")


class ErrorTests(unittest.TestCase):
    def test_service_message_is_shown(self):
        embed = format_service_error({"code": "INVALID_POSITION", "message": "Position 'CB' is not valid."})
        self.assertEqual(embed.title, "Invalid Position")
        self.assertEqual(embed.description, "Position 'CB' is not valid.")

    def test_internal_error_is_generic(self):
        embed = format_service_error({"code": "INTERNAL_ERROR", "message": "secret traceback"})
        self.assertEqual(embed.description, UNEXPECTED)
        self.assertNotIn("traceback", embed.description)

    def test_render_uses_mocked_service(self):
        def service(position, context=None):
            self.assertEqual(position, "wr")
            self.assertEqual(context.caller_id, "5")
            return {
                "success": True,
                "data": [{
                    "matchup_rank": 1,
                    "offense": "MIA",
                    "defense": "DET",
                    "matchup_score": 1.42,
                    "metrics": [],
                }],
                "meta": {"week": 10, "position": "wr"},
            }

        embed = render_best_matchup("wr", 1, RequestContext(interface="discord", caller_id="5"), service)
        self.assertEqual(embed.title, "Best WR Matchups - Week 10")
        self.assertIn("1. MIA offense vs DET defense", embed.description)
        self.assertIn("+1.42", embed.description)

    def test_render_shows_service_error(self):
        def service(position, context=None):
            return {"success": False, "error": {"code": "INVALID_TEAM", "message": "Team 'DTT' was not recognized."}}

        embed = render_best_matchup("wr", None, RequestContext(caller_id="5"), service)
        self.assertEqual(embed.title, "Invalid Team")
        self.assertEqual(embed.description, "Team 'DTT' was not recognized.")

    def test_render_hides_unexpected_exception(self):
        def service(position, context=None):
            raise RuntimeError("database password")

        embed = render_best_matchup("wr", None, RequestContext(caller_id="5"), service)
        self.assertEqual(embed.description, UNEXPECTED)
        self.assertNotIn("password", embed.description)

    def test_opportunity_line_names_both_sides(self):
        embed = format_opportunities({
            "data": [{
                "weekly_rank": 1,
                "offense": "MIA",
                "defense": "DET",
                "position": "te",
                "metric": "Receiving_TD",
                "metric_value": 1.57,
                "z_score": 3.23,
                "defensive_metric_rank": 1,
                "label": "HOT",
            }],
            "meta": {"week": 9},
        }, 5)
        self.assertIn("1. MIA offense vs DET defense", embed.description)
        self.assertIn("TE Receiving TD", embed.description)

    def test_help_fits_and_explains_scores(self):
        embeds = format_help()
        self.assertEqual([embed.title for embed in embeds], ["Matchup", "Fantasy", "Touchdown", "Admin"])
        text = "\n".join(embed.description for embed in embeds)
        for embed in embeds:
            self.assertLessEqual(len(embed.description), 4096)
        self.assertIn("HOT", text)
        self.assertIn("Weekly rank", text)
        self.assertIn("/matchup best position:WR", text)
        self.assertIn("/matchup opportunities", text)
        self.assertIn("not player start or sit advice", text)


if __name__ == "__main__":
    unittest.main()
