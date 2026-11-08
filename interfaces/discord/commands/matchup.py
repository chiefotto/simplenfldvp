import discord
from discord import app_commands

from services.catalog import MAX_TOP_N, POSITIONS

from interfaces.discord.context import request_context
from interfaces.discord.formatters.matchup import render_best_matchup
from services.matchup_service import get_best_position_matchups


class Matchup(app_commands.Group):
    def __init__(self, config):
        super().__init__(name="matchup", description="Positional matchup rankings")
        self.config = config

    @app_commands.command(name="best", description="Rank offenses by that position's matchup score.")
    @app_commands.describe(position="qb, rb, wr, or te", top="How many rows to show, from 1 to 32.")
    @app_commands.choices(position=[app_commands.Choice(name=name.upper(), value=name) for name in POSITIONS])
    async def best(
        self,
        interaction: discord.Interaction,
        position: str,
        top: app_commands.Range[int, 1, MAX_TOP_N] | None = None,
    ):
        await interaction.response.defer()
        context = request_context(interaction.user, self.config.admin_role_id)
        text = render_best_matchup(position, top, context, get_best_position_matchups)
        await interaction.followup.send(text)
