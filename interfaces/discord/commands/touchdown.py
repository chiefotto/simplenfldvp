import discord
from discord import app_commands

from services.catalog import MAX_TOP_N, POSITIONS
from services.matchup_service import get_best_metric_matchups
from services.touchdown_service import get_best_touchdown_opportunities, get_touchdown_offense

from interfaces.discord.context import request_context
from interfaces.discord.formatters.common import as_embeds
from interfaces.discord.formatters.matchup import render_metric_matchup
from interfaces.discord.formatters.touchdown import render_touchdown_offense, render_touchdowns

POSITION_CHOICES = [app_commands.Choice(name=name.upper(), value=name) for name in POSITIONS]


class Touchdown(app_commands.Group):
    def __init__(self, config):
        super().__init__(name="touchdown", description="Touchdown defensive matchups")
        self.config = config

    def _context(self, interaction):
        return request_context(interaction.user, self.config.admin_role_id)

    @app_commands.command(name="best", description="Rank the strongest touchdown matchups on the slate.")
    @app_commands.describe(position="Optional qb, rb, wr, or te filter.", top="How many rows to show, from 1 to 32.")
    @app_commands.choices(position=POSITION_CHOICES)
    async def best(
        self,
        interaction: discord.Interaction,
        position: str | None = None,
        top: app_commands.Range[int, 1, MAX_TOP_N] | None = None,
    ):
        await interaction.response.defer()
        text = render_touchdowns(position, top, self._context(interaction), get_best_touchdown_opportunities)
        await interaction.followup.send(embeds=as_embeds(text))

    @app_commands.command(name="offense", description="Show one offense's touchdown matchups.")
    @app_commands.describe(team="Offense abbreviation.")
    async def offense(self, interaction: discord.Interaction, team: str):
        await interaction.response.defer()
        text = render_touchdown_offense(team, self._context(interaction), get_touchdown_offense)
        await interaction.followup.send(embeds=as_embeds(text))

    @app_commands.command(name="passing", description="Rank QB passing-touchdown matchups.")
    @app_commands.describe(top="How many rows to show, from 1 to 32.")
    async def passing(
        self,
        interaction: discord.Interaction,
        top: app_commands.Range[int, 1, MAX_TOP_N] | None = None,
    ):
        await interaction.response.defer()
        text = render_metric_matchup(
            "qb",
            "passing_td",
            top,
            self._context(interaction),
            get_best_metric_matchups,
            title="Best QB Passing TD Matchups",
        )
        await interaction.followup.send(embeds=as_embeds(text))
