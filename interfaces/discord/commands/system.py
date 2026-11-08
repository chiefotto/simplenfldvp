import discord
from discord import app_commands


class System(app_commands.Group):
    def __init__(self):
        super().__init__(name="system", description="Bot status")

    @app_commands.command(name="ping", description="Check that the bot is online.")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("Bot is online.")
