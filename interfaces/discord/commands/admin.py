import logging

import discord
from discord import app_commands

from interfaces.discord.context import access_level_for

logger = logging.getLogger("interfaces.discord")
UNAVAILABLE = "Admin commands are not available yet."
DENIED = "You do not have permission to run this command."


class Admin(app_commands.Group):
    def __init__(self, config):
        super().__init__(name="admin", description="Snapshot maintenance")
        self.config = config

    @app_commands.command(name="update", description="Admin data updates are not connected yet.")
    async def update(self, interaction: discord.Interaction):
        if self.config.admin_role_id and access_level_for(interaction.user, self.config.admin_role_id) != "ADMIN":
            logger.warning("admin permission denied for %s", interaction.user.id)
            await interaction.response.send_message(DENIED)
            return
        await interaction.response.send_message(UNAVAILABLE)
