import discord
from discord.ext import commands
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')

@bot.command()
async def checkin(ctx):
    """Create a check-in embed with buttons"""
    embed = discord.Embed(
        title="📋 Check-In List",
        color=discord.Color.green()
        
    )
    embed.add_field(
        name="Checked-in Users",
        value="No one has checked in yet.",
        inline=False
    )
    await ctx.send(embed=embed, view=CheckInView())

class CheckInView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.checked_in_users = []

    @discord.ui.button(label="Check In", style=discord.ButtonStyle.green)
    async def check_in_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if any(user.id == interaction.user.id for user in self.checked_in_users):
            await interaction.response.send_message("You've already checked in!", ephemeral=True)
            return

        self.checked_in_users.append(interaction.user)
        await self.update_embed(interaction)
        await interaction.response.send_message("Successfully checked in!", ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red)
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_checked_in = any(user.id == interaction.user.id for user in self.checked_in_users)
        if not user_checked_in:
            await interaction.response.send_message("You're not checked in!", ephemeral=True)
            return

        self.checked_in_users = [user for user in self.checked_in_users if user.id != interaction.user.id]
        await self.update_embed(interaction)
        await interaction.response.send_message("You've left the check-in list.", ephemeral=True)

    async def update_embed(self, interaction: discord.Interaction):
        """Helper function to update the embed with the current check-in list"""
        checked_in_list = [f"{user.mention}" for user in self.checked_in_users]
        embed = interaction.message.embeds[0]
        embed.set_field_at(
            index=0,
            name="Checked-in Users",
            value="\n".join(checked_in_list) or "No one has checked in yet."
        )
        await interaction.message.edit(embed=embed)



bot.run(TOKEN)