import logging

import discord
from discord import app_commands

from services.admin_service import get_data_status, update_data

from interfaces.discord.context import request_context
from interfaces.discord.formatters.admin import render_status, render_update
from interfaces.discord.formatters.common import as_embeds, format_service_error

logger = logging.getLogger("interfaces.discord")
DENIED = "You do not have permission to run this command."


class Admin(app_commands.Group):
    def __init__(self, config):
        super().__init__(name="admin", description="Snapshot maintenance")
        self.config = config

    def _context(self, interaction):
        return request_context(interaction.user, self.config.admin_role_id)

    @app_commands.command(name="update", description="Download the latest completed defense snapshot.")
    async def update(self, interaction: discord.Interaction):
        await interaction.response.defer()
        text = render_update(self._context(interaction), update_data)
        await interaction.followup.send(embeds=as_embeds(text))

    @app_commands.command(name="status", description="Show the stored season and defense snapshot week.")
    async def status(self, interaction: discord.Interaction):
        context = self._context(interaction)
        if context.access_level != "ADMIN":
            logger.warning("admin permission denied for %s", context.caller_id)
            await interaction.response.send_message(embed=format_service_error({"code": "PERMISSION_DENIED", "message": DENIED}))
            return
        await interaction.response.defer()
        await interaction.followup.send(embeds=as_embeds(render_status(context, get_data_status)))
