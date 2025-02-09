import aiosqlite # Asynchronous processing support instead of sqlite
from openpyxl import load_workbook
import asyncio
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

TOKEN = os.getenv('DISCORD_TOKEN')

SPREADSHEET_PATH = os.path.abspath(os.getenv('SPREADSHEET_PATH'))
DB_PATH = os.getenv('DB_PATH')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# SQLite connection
async def get_db_connection():
    return await aiosqlite.connect(DB_PATH)

# creating db tables if they don't already exist
async def initialize_database():
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS "PlayerStats" (
                "DiscordID" TEXT NOT NULL UNIQUE,
                "DiscordUsername" TEXT NOT NULL,
                "PlayerRiotID" TEXT UNIQUE,
                "Participation" NUMERIC DEFAULT 0,
                "Wins" INTEGER DEFAULT 0,
                "MVPs" INTEGER DEFAULT 0,
                "ToxicityPoints" NUMERIC DEFAULT 0,
                "GamesPlayed" INTEGER DEFAULT 0,
                "WinRate" REAL,
                "TotalPoints" NUMERIC DEFAULT 0,
                "PlayerTier" INTEGER DEFAULT 0,
                "PlayerRank" TEXT DEFAULT 'UNRANKED',
                "RolePreference" TEXT DEFAULT '55555',
                PRIMARY KEY("DiscordID")
)
        ''')
        await conn.commit()

# assign bot prefix
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    await initialize_database()

def update_excel(discord_id, player_data):
    try:
        # Load the workbook and get the correct sheet
        workbook = load_workbook(SPREADSHEET_PATH)
        sheet_name = 'PlayerStats'
        if sheet_name in workbook.sheetnames:
            sheet = workbook[sheet_name]
        else:
            raise ValueError(f'Sheet {sheet_name} does not exist in the workbook')

        # Check if the player already exists in the sheet
        found = False
        for row in sheet.iter_rows(min_row=2):  # Assuming the first row is headers
            if str(row[0].value) == discord_id:  # Check if Discord ID matches
                # Update only if there's a difference
                for idx, key in enumerate(player_data.keys()):
                    if row[idx].value != player_data[key]:
                        row[idx].value = player_data[key]
                        found = True
                break

        # If player not found, add a new row
        if not found:
            # Find the first truly empty row, ignoring formatting
            empty_row_idx = sheet.max_row + 1
            for i, row in enumerate(sheet.iter_rows(min_row=2), start=2):
                if all(cell.value is None for cell in row):
                    empty_row_idx = i
                    break

            # Insert the new data into the empty row
            for idx, key in enumerate(player_data.keys(), start=1):
                sheet.cell(row=empty_row_idx, column=idx).value = player_data[key]

        # Save the workbook after updates
        workbook.save(SPREADSHEET_PATH)
        print(f"Spreadsheet '{SPREADSHEET_PATH}' has been updated successfully.")

    except Exception as e:
        print(f"Error updating Excel file: {e}")

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

@bot.command()
async def resetdb(interaction: discord.Interaction):
    # Only the server owner can use this command
    if interaction.user != interaction.guild.owner:
        await interaction.response.send_message(
            "You do not have permission to use this command. Only the server owner can reset the database.",
            ephemeral=True
        )
        return

    # Send confirmation message to the server owner
    await interaction.response.send_message(
        "You are about to reset the player database to default values for participation, wins, MVPs, toxicity points, games played, win rate, and total points (excluding rank, tier, and role preferences). "
        "Please type /resetdb again within the next 10 seconds to confirm.",
        ephemeral=True
    )

    def check(res: discord.Interaction):
        # Check if the command is resetdb and if it's the same user who issued the original command
        return res.command.name == 'resetdb' and res.user == interaction.user

    try:
        # Wait for the confirmation within 10 seconds
        response = await bot.wait_for('interaction', timeout=10.0, check=check)

        # If the confirmation is received, proceed with resetting the database
        async with aiosqlite.connect(DB_PATH) as conn:
            await conn.execute("""
                UPDATE PlayerStats
                SET
                    Participation = 0,
                    Wins = 0,
                    MVPs = 0,
                    ToxicityPoints = 0,
                    GamesPlayed = 0,
                    WinRate = NULL,
                    TotalPoints = 0
            """)
            await conn.commit()

        # Send a follow-up message indicating the reset was successful
        await response.followup.send(
            "The player database has been successfully reset to default values, excluding rank, tier, and role preferences.",
            ephemeral=True
        )

    except asyncio.TimeoutError:
        # If no confirmation is received within 10 seconds, send a follow-up message indicating timeout
        await interaction.followup.send(
            "Reset confirmation timed out. Please type /resetdb again if you still wish to reset the database.",
            ephemeral=True
        )

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