import discord
from discord import app_commands

from database.matchups import METRIC_ALIASES
from services.catalog import MAX_TOP_N, POSITIONS
from services.matchup_service import (
    get_best_metric_matchups,
    get_best_position_matchups,
    get_defense_profile,
    get_offense_matchup,
)
from services.opportunity_service import get_top_weekly_opportunities

from interfaces.discord.context import request_context
from interfaces.discord.formatters.common import as_embeds
from interfaces.discord.formatters.matchup import (
    render_best_matchup,
    render_defense_profile,
    render_metric_matchup,
    render_offense_matchup,
    render_opportunities,
)

POSITION_CHOICES = [app_commands.Choice(name=name.upper(), value=name) for name in POSITIONS]
METRIC_CHOICES = [app_commands.Choice(name=name, value=name) for name in sorted(METRIC_ALIASES)]


class Matchup(app_commands.Group):
    def __init__(self, config):
        super().__init__(name="matchup", description="Positional matchup rankings")
        self.config = config

    def _context(self, interaction):
        return request_context(interaction.user, self.config.admin_role_id)

    @app_commands.command(name="best", description="Rank offenses by that position's matchup score.")
    @app_commands.describe(position="qb, rb, wr, or te", top="How many rows to show, from 1 to 32.")
    @app_commands.choices(position=POSITION_CHOICES)
    async def best(
        self,
        interaction: discord.Interaction,
        position: str,
        top: app_commands.Range[int, 1, MAX_TOP_N] | None = None,
    ):
        await interaction.response.defer()
        text = render_best_matchup(position, top, self._context(interaction), get_best_position_matchups)
        await interaction.followup.send(embeds=as_embeds(text))

    @app_commands.command(name="metric", description="Rank offenses by one stat's league z-score.")
    @app_commands.describe(
        position="qb, rb, wr, or te",
        metric="A stat alias for that position.",
        top="How many rows to show, from 1 to 32.",
    )
    @app_commands.choices(position=POSITION_CHOICES, metric=METRIC_CHOICES)
    async def metric(
        self,
        interaction: discord.Interaction,
        position: str,
        metric: str,
        top: app_commands.Range[int, 1, MAX_TOP_N] | None = None,
    ):
        await interaction.response.defer()
        text = render_metric_matchup(position, metric, top, self._context(interaction), get_best_metric_matchups)
        await interaction.followup.send(embeds=as_embeds(text))

    @app_commands.command(name="defense", description="Show how a defense performs against a position.")
    @app_commands.describe(team="Defense abbreviation.", position="qb, rb, wr, or te")
    @app_commands.choices(position=POSITION_CHOICES)
    async def defense(self, interaction: discord.Interaction, team: str, position: str):
        await interaction.response.defer()
        text = render_defense_profile(team, position, self._context(interaction), get_defense_profile)
        await interaction.followup.send(embeds=as_embeds(text))

    @app_commands.command(name="offense", description="Show an offense's matchup against its opponent.")
    @app_commands.describe(team="Offense abbreviation.", position="qb, rb, wr, or te")
    @app_commands.choices(position=POSITION_CHOICES)
    async def offense(self, interaction: discord.Interaction, team: str, position: str):
        await interaction.response.defer()
        text = render_offense_matchup(team, position, self._context(interaction), get_offense_matchup)
        await interaction.followup.send(embeds=as_embeds(text))

    @app_commands.command(name="opportunities", description="Rank the strongest individual stat vulnerabilities.")
    @app_commands.describe(
        metric="Optional stat. Limits the board to that stat across every position that has it.",
        top="How many rows to show, from 1 to 32.",
    )
    @app_commands.choices(metric=METRIC_CHOICES)
    async def opportunities(
        self,
        interaction: discord.Interaction,
        metric: str | None = None,
        top: app_commands.Range[int, 1, MAX_TOP_N] | None = None,
    ):
        await interaction.response.defer()
        text = render_opportunities(top, self._context(interaction), get_top_weekly_opportunities, metric)
        await interaction.followup.send(embeds=as_embeds(text))
