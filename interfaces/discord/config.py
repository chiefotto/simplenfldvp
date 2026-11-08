import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class DiscordConfig:
    token: str
    guild_id: int | None
    admin_role_id: int | None


def _optional_int(value, name):
    if not value:
        return None
    try:
        return int(value)
    except ValueError as error:
        raise RuntimeError(f"{name} must be an integer.") from error


def load_config(environ=None):
    if environ is None:
        load_dotenv(ROOT / ".env")
        environ = os.environ
    token = environ.get("DISCORD_BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("DISCORD_BOT_TOKEN is not configured.")
    return DiscordConfig(
        token=token,
        guild_id=_optional_int(environ.get("DISCORD_GUILD_ID", "").strip(), "DISCORD_GUILD_ID"),
        admin_role_id=_optional_int(environ.get("DISCORD_ADMIN_ROLE_ID", "").strip(), "DISCORD_ADMIN_ROLE_ID"),
    )
