import logging
import unittest
from types import SimpleNamespace

from services.context import RequestContext

from interfaces.discord.config import load_config
from interfaces.discord.context import access_level_for, request_context
from interfaces.discord.formatters.common import UNEXPECTED, format_service_error
from interfaces.discord.formatters.matchup import render_best_matchup


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
        message = format_service_error({"code": "INVALID_POSITION", "message": "Position 'CB' is not valid."})
        self.assertEqual(message, "Position 'CB' is not valid.")

    def test_internal_error_is_generic(self):
        message = format_service_error({"code": "INTERNAL_ERROR", "message": "secret traceback"})
        self.assertEqual(message, UNEXPECTED)
        self.assertNotIn("traceback", message)

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
                }],
                "meta": {"week": 10, "position": "wr"},
            }

        text = render_best_matchup("wr", 1, RequestContext(interface="discord", caller_id="5"), service)
        self.assertIn("Best WR Matchups - Week 10", text)
        self.assertIn("1. MIA offense vs DET defense - +1.42", text)

    def test_render_shows_service_error(self):
        def service(position, context=None):
            return {"success": False, "error": {"code": "INVALID_TEAM", "message": "Team 'DTT' was not recognized."}}

        text = render_best_matchup("wr", None, RequestContext(caller_id="5"), service)
        self.assertEqual(text, "Team 'DTT' was not recognized.")

    def test_render_hides_unexpected_exception(self):
        def service(position, context=None):
            raise RuntimeError("database password")

        text = render_best_matchup("wr", None, RequestContext(caller_id="5"), service)
        self.assertEqual(text, UNEXPECTED)
        self.assertNotIn("password", text)


if __name__ == "__main__":
    unittest.main()
