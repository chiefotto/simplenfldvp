import discord
from discord import app_commands

from services.catalog import MAX_TOP_N, POSITIONS
from services.fantasy_service import (
    get_best_fantasy_matchups,
    get_fantasy_offense_matchup,
    get_fantasy_position_rankings,
    get_worst_fantasy_matchups,
)

from interfaces.discord.context import request_context
from interfaces.discord.formatters.common import as_embeds
from interfaces.discord.formatters.fantasy import (
    render_fantasy_best,
    render_fantasy_offense,
    render_fantasy_position,
    render_fantasy_worst,
)

POSITION_CHOICES = [app_commands.Choice(name=name.upper(), value=name) for name in POSITIONS]


class Fantasy(app_commands.Group):
    def __init__(self, config):
        super().__init__(name="fantasy", description="Positional fantasy matchups")
        self.config = config

    def _context(self, interaction):
        return request_context(interaction.user, self.config.admin_role_id)

    @app_commands.command(name="best", description="Show the most favorable FPTS positional matchups.")
    @app_commands.describe(top="How many rows to show, from 1 to 32.")
    async def best(
        self,
        interaction: discord.Interaction,
        top: app_commands.Range[int, 1, MAX_TOP_N] | None = None,
    ):
        await interaction.response.defer()
        text = render_fantasy_best(top, self._context(interaction), get_best_fantasy_matchups)
        await interaction.followup.send(embeds=as_embeds(text))

    @app_commands.command(name="worst", description="Show the least favorable FPTS positional matchups.")
    @app_commands.describe(top="How many rows to show, from 1 to 32.")
    async def worst(
        self,
        interaction: discord.Interaction,
        top: app_commands.Range[int, 1, MAX_TOP_N] | None = None,
    ):
        await interaction.response.defer()
        text = render_fantasy_worst(top, self._context(interaction), get_worst_fantasy_matchups)
        await interaction.followup.send(embeds=as_embeds(text))

    @app_commands.command(name="position", description="Rank scheduled offenses for one fantasy position.")
    @app_commands.describe(position="qb, rb, wr, or te")
    @app_commands.choices(position=POSITION_CHOICES)
    async def position(self, interaction: discord.Interaction, position: str):
        await interaction.response.defer()
        text = render_fantasy_position(position, self._context(interaction), get_fantasy_position_rankings)
        await interaction.followup.send(embeds=as_embeds(text))

    @app_commands.command(name="offense", description="Show one offense's FPTS matchup against its opponent.")
    @app_commands.describe(team="Offense abbreviation.", position="qb, rb, wr, or te")
    @app_commands.choices(position=POSITION_CHOICES)
    async def offense(self, interaction: discord.Interaction, team: str, position: str):
        await interaction.response.defer()
        text = render_fantasy_offense(team, position, self._context(interaction), get_fantasy_offense_matchup)
        await interaction.followup.send(embeds=as_embeds(text))
