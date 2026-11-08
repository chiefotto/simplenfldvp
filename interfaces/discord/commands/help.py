import discord

from interfaces.discord.formatters.help import format_help


def register_help(tree):
    @tree.command(name="help", description="Explain the matchup and fantasy commands.")
    async def help_command(interaction: discord.Interaction):
        await interaction.response.send_message(format_help())
