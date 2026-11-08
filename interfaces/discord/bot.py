import logging

import discord
from discord import app_commands

import services  # noqa: F401  (configures logging)
from interfaces.discord.commands.admin import Admin
from interfaces.discord.commands.fantasy import Fantasy
from interfaces.discord.commands.help import register_help
from interfaces.discord.commands.matchup import Matchup
from interfaces.discord.commands.system import System
from interfaces.discord.commands.touchdown import Touchdown
from interfaces.discord.config import load_config

logger = logging.getLogger("interfaces.discord")


class DvpBot(discord.Client):
    def __init__(self, config):
        super().__init__(intents=discord.Intents.default())
        self.config = config
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        self.tree.add_command(System())
        self.tree.add_command(Matchup(self.config))
        self.tree.add_command(Fantasy(self.config))
        self.tree.add_command(Admin(self.config))
        self.tree.add_command(Touchdown(self.config))
        register_help(self.tree)
        if self.config.guild_id:
            guild = discord.Object(id=self.config.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
        else:
            synced = await self.tree.sync()
        logger.info("synced %s commands", len(synced))


def main():
    config = load_config()
    logger.info("bot starting")
    bot = DvpBot(config)
    try:
        bot.run(config.token, log_handler=None)
    finally:
        logger.info("bot shutdown")


if __name__ == "__main__":
    main()
