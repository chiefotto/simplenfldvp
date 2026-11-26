import discord
from discord import app_commands

from services.catalog import METRIC_ALIASES, POSITIONS
from services.outlook_service import get_game_link, get_rankings_link, get_weekly_link

from interfaces.discord.context import request_context
from interfaces.discord.formatters.common import as_embeds
from interfaces.discord.formatters.outlook import render_game_link, render_rankings_link, render_weekly_link

POSITION_CHOICES = [app_commands.Choice(name=name.upper(), value=name) for name in POSITIONS]
METRIC_CHOICES = [app_commands.Choice(name=name, value=name) for name in sorted(METRIC_ALIASES)]


class Outlook(app_commands.Group):
    def __init__(self, config):
        super().__init__(name="outlook", description="Links to the matchup web app")
        self.config = config

    def _context(self, interaction):
        return request_context(interaction.user, self.config.admin_role_id)

    async def _send(self, interaction, rendered):
        if isinstance(rendered, tuple):
            embed, url, label = rendered
            if url:
                view = discord.ui.View()
                view.add_item(discord.ui.Button(label=label or "Open", url=url))
                await interaction.followup.send(embed=embed, view=view)
                return
            await interaction.followup.send(embed=embed)
            return
        await interaction.followup.send(embeds=as_embeds(rendered))

    @app_commands.command(name="weekly", description="Link to the weekly outlook.")
    @app_commands.describe(season="Optional season.", week="Optional week, from 1 to 22.")
    async def weekly(
        self,
        interaction: discord.Interaction,
        season: int | None = None,
        week: app_commands.Range[int, 1, 22] | None = None,
    ):
        await interaction.response.defer()
        rendered = render_weekly_link(
            self.config.web_app_base_url,
            season,
            week,
            self._context(interaction),
            get_weekly_link,
        )
        await self._send(interaction, rendered)

    @app_commands.command(name="game", description="Link to one team's game outlook.")
    @app_commands.describe(team="Either team in the game.", season="Optional season.", week="Optional week, from 1 to 22.")
    async def game(
        self,
        interaction: discord.Interaction,
        team: str,
        season: int | None = None,
        week: app_commands.Range[int, 1, 22] | None = None,
    ):
        await interaction.response.defer()
        rendered = render_game_link(
            self.config.web_app_base_url,
            team,
            season,
            week,
            self._context(interaction),
            get_game_link,
        )
        await self._send(interaction, rendered)

    @app_commands.command(name="rankings", description="Link to the rankings page.")
    @app_commands.describe(
        position="Optional qb, rb, wr, or te.",
        metric="Optional stat alias.",
        season="Optional season.",
        week="Optional week, from 1 to 22.",
    )
    @app_commands.choices(position=POSITION_CHOICES, metric=METRIC_CHOICES)
    async def rankings(
        self,
        interaction: discord.Interaction,
        position: str | None = None,
        metric: str | None = None,
        season: int | None = None,
        week: app_commands.Range[int, 1, 22] | None = None,
    ):
        await interaction.response.defer()
        rendered = render_rankings_link(
            self.config.web_app_base_url,
            position,
            metric,
            season,
            week,
            self._context(interaction),
            get_rankings_link,
        )
        await self._send(interaction, rendered)
