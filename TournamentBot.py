import aiosqlite 
from openpyxl import load_workbook
import asyncio
import discord
from discord.ext import commands
from discord import AllowedMentions, app_commands
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
        await conn.commit() # used to save changes to the db file


global_game_state = None
class GlobalGameState:
    def __init__(self, games: list):
        self.games = games  
        self.game_messages = {}
        self.selected = None

    def generate_embed(self, game_index: int) -> discord.Embed:
        game = self.games[game_index]
        embed = discord.Embed(title=f"Game {game_index+1}", color=discord.Color.blue())
        embed.add_field(name="Blue Team", value="\n".join(game["blue"]), inline=True)
        embed.add_field(name="Red Team", value="\n".join(game["red"]), inline=True)
        return embed

    async def update_all_messages(self):
        """Update every game message with the current team lists and new views."""
        for game_index, message in self.game_messages.items():
            embed = self.generate_embed(game_index)
            view = GameSwapView(self, game_index)
            try:
                await message.edit(embed=embed, view=view)
            except Exception as e:
                print(f"Failed to update message for Game {game_index+1}: {e}")

    async def handle_selection(
        self,
        interaction: discord.Interaction,
        game_index: int,
        team: str,
        player_index: int,
        player_name: str,
    ):
        """
        Handle a button press from any game.
        If no selection is stored, store this selection.
        If one already exists, swap the two players and update all game messages.
        """
        if self.selected is None:
            self.selected = (game_index, team, player_index, player_name)
            await interaction.response.send_message(
                f"Selected **{player_name}** from Game {game_index+1} ({team} Team). Now select another player to swap.",
                ephemeral=True,
            )
        else:
            first_game_index, first_team, first_player_index, first_player_name = self.selected
            second = (game_index, team, player_index, player_name)
            if (first_game_index, first_team, first_player_index) == (game_index, team, player_index):
                self.selected = None
                await interaction.response.send_message("Selection cancelled.", ephemeral=True)
                return

            temp = self.games[first_game_index][first_team][first_player_index]
            self.games[first_game_index][first_team][first_player_index] = self.games[game_index][team][player_index]
            self.games[game_index][team][player_index] = temp

            self.selected = None 
            await self.update_all_messages()
            await interaction.response.send_message("Players swapped!", ephemeral=True)



bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await initialize_database()

# test command for adding users
'''
@bot.command()
async def adduser(self, ctx, user: discord.User):
    cursor = await self.bot.db.cursor()
    await cursor.execute("SELECT DiscordID FROM user WHERE DiscordID = ?", (user.id,))
    re = await cursor.fetchone()

    if re is not None:
        return await ctx.send("This user id is already in the user id list")
    
    await cursor.execute("INSERT INTO USER(DISCORDID) VALUES(?)", (user.id,))
    await self.bot.db.commit()
    await ctx.send("Entered the data in database!")
'''

@bot.command()
async def checkin(ctx):
    """Sends a check-in embed with buttons for checking in, leaving, and starting the game."""
    embed = discord.Embed(
        title="📋 Check-In List", color=discord.Color.green()
    )
    embed.add_field(
        name="Checked-in Users",
        value="No one has checked in yet.",
        inline=False,
    )
    await ctx.send(embed=embed, view=StartGameView(ctx.author.id))

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

class StartGameView(discord.ui.View):
    def __init__(self, creator_id: int):
        super().__init__(timeout=None)
        self.creator_id = creator_id
        self.checked_in_users = []

    @discord.ui.button(label="Check In", style=discord.ButtonStyle.green)
    async def check_in_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if any(user.id == interaction.user.id for user in self.checked_in_users):
            await interaction.response.send_message("You've already checked in!", ephemeral=True)
            return
        self.checked_in_users.append(interaction.user)
        await self.update_embed(interaction)
        await interaction.response.send_message("Successfully checked in!", ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red)
    async def leave_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not any(user.id == interaction.user.id for user in self.checked_in_users):
            await interaction.response.send_message("You're not checked in!", ephemeral=True)
            return
        self.checked_in_users = [user for user in self.checked_in_users if user.id != interaction.user.id]
        await self.update_embed(interaction)
        await interaction.response.send_message("You've left the check-in list.", ephemeral=True)

    async def update_embed(self, interaction: discord.Interaction):
        checked_in_list = [f"{user.mention}" for user in self.checked_in_users]
        embed = interaction.message.embeds[0]
        embed.set_field_at(
            index=0,
            name="Checked-in Users",
            value="\n".join(checked_in_list) or "No one has checked in yet.",
            inline=False,
        )
        await interaction.message.edit(embed=embed)

    @discord.ui.button(label="Start\nGame", style=discord.ButtonStyle.grey)
    async def start_game_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message("Only the creator can start the game!", ephemeral=True)
            return

        fakeDataBlue = [
            ["Player1", "Player2", "Player3", "Player4", "Player5"],
            ["Player6", "Player7", "Player8", "Player9", "Player10"],
        ]
        fakeDataRed = [
            ["Player11", "Player12", "Player13", "Player14", "Player15"],
            ["Player16", "Player17", "Player18", "Player19", "Player20"],
        ]
        games = []
        for i in range(len(fakeDataBlue)):
            games.append({
                "blue": fakeDataBlue[i],
                "red": fakeDataRed[i],
            })


        global global_game_state
        global_game_state = GlobalGameState(games)

        for i, game in enumerate(games):
            embed = global_game_state.generate_embed(i)
            view = GameSwapView(global_game_state, i)
            msg = await interaction.channel.send(embed=embed, view=view)
            global_game_state.game_messages[i] = msg

        await interaction.response.send_message(
            "Game messages created! You can swap players across games.", ephemeral=True
        )

class GamePlayerButton(discord.ui.Button):
    """
    A button representing a player in a specific game.
    It stores the game index, team, and player index so that the global state
    can be updated correctly when clicked.
    """
    def __init__(self, game_index: int, team: str, player_index: int, label: str):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.game_index = game_index
        self.team = team
        self.player_index = player_index

    async def callback(self, interaction: discord.Interaction):
        global global_game_state
        await global_game_state.handle_selection(interaction, self.game_index, self.team, self.player_index, self.label)

class StopSwappingButton(discord.ui.Button):
    """
    A button to stop swapping for this game message.
    Disables all buttons on that message.
    """
    def __init__(self):
        super().__init__(label="Stop Swapping", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        for child in self.view.children:
            child.disabled = True
        await interaction.response.edit_message(view=self.view)
        await interaction.followup.send("Swapping session ended for this game.", ephemeral=True)

class GameSwapView(discord.ui.View):
    """
    A view attached to an individual game message.
    It creates a button for each player (for both teams) using the global state,
    plus a Stop Swapping button.
    """
    def __init__(self, global_state: GlobalGameState, game_index: int):
        super().__init__(timeout=None)
        self.global_state = global_state
        self.game_index = game_index
        game = self.global_state.games[game_index]
        for i, player in enumerate(game["blue"]):
            self.add_item(GamePlayerButton(game_index, "blue", i, player))
        for i, player in enumerate(game["red"]):
            self.add_item(GamePlayerButton(game_index, "red", i, player))
        self.add_item(StopSwappingButton())

# Function that updates user's username in the database
async def update_username(player: discord.Member):
    try:
        async with aiosqlite.connect(DB_PATH) as conn:
            # Fetch the player's current data from the database
            async with conn.execute("SELECT DiscordUsername FROM PlayerStats WHERE DiscordID=?", (str(player.id),)) as cursor:
                player_stats = await cursor.fetchone()

            # If player exists in the database and the username is outdated, update it
            if player_stats:
                stored_username = player_stats[0]
                current_username = player.display_name

                if stored_username != current_username:
                    await conn.execute(
                        "UPDATE PlayerStats SET DiscordUsername = ? WHERE DiscordID = ?",
                        (current_username, str(player.id))
                    )
                    await conn.commit()
                    print(f"Updated username in database for {player.id} from '{stored_username}' to '{current_username}'.")
    except Exception as e:
        # Log the error or handle it appropriately
        print(f"An error occurred while updating username: {e}")

# function that updates a user's participation points
async def update_points(members):
    async with aiosqlite.connect(DB_PATH) as conn:
        not_found_users = []
        updated_users = []

        # Iterate through all members with Player or Volunteer roles
        for member in members:
            async with conn.execute("SELECT Participation, GamesPlayed FROM PlayerStats WHERE DiscordID = ?", (str(member.id),)) as cursor:
                result = await cursor.fetchone()

            if result:
                participation, games_played = result

                # Check if the member has the Player or Volunteer role
                if any(role.name == "Player" for role in member.roles):
                    # Update both Participation and GamesPlayed for Players
                    await conn.execute(
                        "UPDATE PlayerStats SET Participation = ?, GamesPlayed = ? WHERE DiscordID = ?",
                        (participation + 1, games_played + 1, str(member.id))
                    )
                    updated_users.append(member.display_name)
                elif any(role.name == "Volunteer" for role in member.roles):
                    # Update only Participation for Volunteers
                    await conn.execute(
                        "UPDATE PlayerStats SET Participation = ? WHERE DiscordID = ?",
                        (participation + 1, str(member.id))
                    )
                    updated_users.append(member.display_name)
            else:
                # Add users who are not found in the database to the list
                not_found_users.append(member.display_name)

        await conn.commit()

    return {"success": updated_users, "not_found": not_found_users}

# function that updates a user's toxicity points
async def update_toxicity(member):
    async with aiosqlite.connect(DB_PATH) as conn:
        # Attempt to find the user in the PlayerStats table
        async with conn.execute("SELECT ToxicityPoints FROM PlayerStats WHERE DiscordID = ?", (str(member.id),)) as cursor:
            result = await cursor.fetchone()

        if result:
            toxicity_points = result[0]
            # Increment the ToxicityPoints and update TotalPoints accordingly
            await conn.execute(
                """
                UPDATE PlayerStats 
                SET ToxicityPoints = ?, TotalPoints = (Participation + Wins - ?)
                WHERE DiscordID = ?
                """,
                (toxicity_points + 1, toxicity_points + 1, str(member.id))
            )
            await conn.commit()
            return True  # Successfully updated user

        return False  # User not found

# function used to update player win points    
async def update_wins(winners):
    async with aiosqlite.connect(DB_PATH) as conn:
        for winner in winners:
            # Since we already checked for existence, we can directly update
            async with conn.execute("SELECT Wins, GamesPlayed FROM PlayerStats WHERE DiscordID = ?", (str(winner.id),)) as cursor:
                result = await cursor.fetchone()
                if result:
                    wins, games_played = result
                    # Update the Wins and GamesPlayed for the player
                    await conn.execute(
                        "UPDATE PlayerStats SET Wins = ?, GamesPlayed = ? WHERE DiscordID = ?",
                        (wins + 1, games_played + 1, str(winner.id))
                    )
                    # Update win rate for the player
                    await update_win_rate(str(winner.id))

        await conn.commit()
        
# code to calculate and update winrate in database
async def update_win_rate(discord_id):
    async with await get_db_connection() as conn:
        async with conn.execute("SELECT Wins, GamesPlayed FROM PlayerStats WHERE DiscordID = ?", (discord_id,)) as cursor:
            result = await cursor.fetchone()
    if result:
        wins, games_played = result
        win_rate = (wins / games_played) * 100 if games_played > 0 else 0
        await conn.execute("UPDATE PlayerStats SET WinRate = ? WHERE DiscordID = ?", (win_rate, discord_id))
        await conn.commit()

# goes through the database and checks for discordIDs that have wins
async def check_winners_in_db(winners):
    not_found_users = []
    async with aiosqlite.connect(DB_PATH) as conn:
        for winner in winners:
            # Check if the player exists in the database
            async with conn.execute("SELECT Wins, GamesPlayed FROM PlayerStats WHERE DiscordID = ?", (str(winner.id),)) as cursor:
                result = await cursor.fetchone()

            if not result:
                # Add to not found list
                not_found_users.append(winner)

# bot command that updates toxicity
@bot.command
async def toxicity(interaction: discord.Interaction, member: discord.Member):
    try:
        # Defer the response to prevent interaction timeout
        await interaction.response.defer(ephemeral=True)

        # Update the toxicity points in the database
        found_user = await update_toxicity(member)

        if found_user:
            await interaction.followup.send(f"{member.display_name}'s toxicity points have been updated.")
        else:
            await interaction.followup.send(f"{member.display_name} could not be found in the database.")
    except commands.MissingPermissions:
        await interaction.response.send_message("You do not have permission to use this command. Only administrators can give toxicity points.", ephemeral=True)
    except Exception as e:
        print(f'An error occurred: {e}')
        await interaction.followup.send("An unexpected error occurred while updating toxicity points.", ephemeral=True)

active_matches = {}

# probably needs changes
@bot.command
@app_commands.describe(match_number="Choose the match number (1, 2, or 3).",
                       lobby_number="Specify the lobby number.",
                       team="Choose the winning team (red or blue).")
@app_commands.choices(
    match_number=[
        app_commands.Choice(name="1", value="1"),
        app_commands.Choice(name="2", value="2"),
        app_commands.Choice(name="3", value="3")
    ],
    team=[
        app_commands.Choice(name="Red", value="red"),
        app_commands.Choice(name="Blue", value="blue")
    ]
)
async def win(interaction: discord.Interaction, match_number: str, lobby_number: str, team: str):
    try:
        # Ensure that the match and lobby exist by checking against the matchmaking result
        match_key = f"match_{match_number}_lobby_{lobby_number}"
        if match_key not in active_matches:
            await interaction.response.send_message(
                "Error: No match found. Please run `/matchmake` for this match and lobby first.",
                ephemeral=True
            )
            return

        # Get the winning team's players
        winning_team = active_matches[match_key][team.lower()]

        # Update wins for each player on the winning team
        await interaction.response.defer(ephemeral=True)

         # This part of the command's code checking for unfound users should basically never be necessary anymore because it was added at a time when this command asked an admin to
         # specify 5 usernames. However, it's being kept here for error handling in case a team is somehow created with users who are not in the database during /matchmaking testing.
        not_found_users = await check_winners_in_db(winning_team)

        if not_found_users:
            missing_users = ", ".join([user.username for user in not_found_users])
            await interaction.followup.send(
                f"Data integrity error; the following players could not be found in the database, so no wins were updated: \n{missing_users}",
                ephemeral=True
            )
        else:
            await update_wins(winning_team)
            await interaction.followup.send(
                "All players on the winning team have had their 'Wins' updated.",
                ephemeral=True
            )

    except commands.MissingPermissions:
        await interaction.response.send_message(
            "You do not have permission to use this command. Only administrators can update players' wins.",
            ephemeral=True
        )

    except Exception as e:
        print(f'An error occurred: {e}')
        await interaction.followup.send(
            "An error occurred while updating wins.",
            ephemeral=True
        )

bot.run(TOKEN)

