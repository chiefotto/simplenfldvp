import discord
from discord import app_commands

from interfaces.discord.formatters.fantasy import format_fantasy_placeholder


class Fantasy(app_commands.Group):
    def __init__(self):
        super().__init__(name="fantasy", description="Positional fantasy matchups")

    @app_commands.command(name="best", description="Fantasy rankings are not connected yet.")
    async def best(self, interaction: discord.Interaction):
        await interaction.response.send_message(format_fantasy_placeholder())
