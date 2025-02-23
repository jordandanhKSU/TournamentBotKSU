import os
import aiosqlite
import asyncio
from openpyxl import load_workbook
from dotenv import load_dotenv, find_dotenv
import discord
import aiohttp

load_dotenv(find_dotenv())
DB_PATH = os.getenv('DB_PATH')
SPREADSHEET_PATH = os.path.abspath(os.getenv('SPREADSHEET_PATH'))

async def get_db_connection():
    return await aiosqlite.connect(DB_PATH)

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
    async with await get_db_connection(DB_PATH) as conn:
        async with conn.execute("SELECT Wins, GamesPlayed FROM PlayerStats WHERE DiscordID = ?", (discord_id,)) as cursor:
            result = await cursor.fetchone()
    if result:
        wins, games_played = result
        win_rate = (wins / games_played) * 100 if games_played > 0 else 0
        await conn.execute("UPDATE PlayerStats SET WinRate = ? WHERE DiscordID = ?", (win_rate, discord_id))
        await conn.commit()

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

async def update_username(player: discord.Member):
    try:
        current_username = player.display_name
        async with aiosqlite.connect(DB_PATH) as conn:
            # Fetch the player's current data from the database
            async with conn.execute(
                "SELECT DiscordUsername FROM PlayerStats WHERE DiscordID = ?",
                (str(player.id),)
            ) as cursor:
                player_stats = await cursor.fetchone()

            # If player exists in the database and the username is outdated, update it
            if player_stats:
                stored_username = player_stats[0]
                if stored_username != current_username:
                    await conn.execute(
                        "UPDATE PlayerStats SET DiscordUsername = ? WHERE DiscordID = ?",
                        (current_username, str(player.id))
                    )
                    await conn.commit()
                    print(f"Updated username for {player.id} to '{current_username}'.")
            else:
                # Insert new player if they don't exist
                await conn.execute(
                    """INSERT INTO PlayerStats (DiscordID, DiscordUsername)
                       VALUES (?, ?)""",
                    (str(player.id), current_username)
                )
                await conn.commit()
                print(f"Added new player {player.id} with username '{current_username}'.")
    except Exception as e:
        print(f"Error updating username: {e}")

async def link(interaction: discord.Interaction, riot_id: str):
    member = interaction.user

    # Riot ID is in the format 'username#tagline', e.g., 'jacstogs#1234'
    if '#' not in riot_id:
        await interaction.response.send_message(
            "Invalid Riot ID format. Please enter your Riot ID in the format 'username#tagline'.",
            ephemeral=True
        )
        return

    # Split the Riot ID into name and tagline
    summoner_name, tagline = riot_id.split('#', 1)
    summoner_name = summoner_name.strip()
    tagline = tagline.strip()

    # Verify that the Riot ID exists using the Riot API
    api_key = os.getenv("RIOT_API_KEY")
    headers = {"X-Riot-Token": api_key}
    url = f"https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{summoner_name}/{tagline}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    # Riot ID exists, proceed to link it
                    data = await response.json()  # Get the response data

                    # Debugging: Print the data to see what comes back from the API
                    print(f"Riot API response: {data}")

                    async with aiosqlite.connect(DB_PATH) as conn:
                        try:
                            # Check if the user already exists in the database
                            async with conn.execute("SELECT * FROM PlayerStats WHERE DiscordID = ?", (str(member.id),)) as cursor:
                                result = await cursor.fetchone()

                            if result:
                                # Update the existing record with the new Riot ID
                                await conn.execute(
                                    "UPDATE PlayerStats SET PlayerRiotID = ? WHERE DiscordID = ?",
                                    (riot_id, str(member.id))
                                )
                            else:
                                # Insert a new record if the user doesn't exist in the database
                                await conn.execute(
                                    "INSERT INTO PlayerStats (DiscordID, DiscordUsername, PlayerRiotID) VALUES (?, ?, ?)",
                                    (str(member.id), member.display_name, riot_id)
                                )

                            await conn.commit()

                            await interaction.response.send_message(
                                f"Your Riot ID '{riot_id}' has been successfully linked to your Discord account.",
                                ephemeral=True
                            )
                        except aiosqlite.IntegrityError as e:
                            # Handle UNIQUE constraint violation (i.e., Riot ID already linked)
                            if 'UNIQUE constraint failed: PlayerStats.PlayerRiotID' in str(e):
                                # Riot ID is already linked to another user
                                async with conn.execute("""
                                    SELECT DiscordID, DiscordUsername FROM PlayerStats WHERE PlayerRiotID = ?
                                """, (riot_id,)) as cursor:
                                    existing_user_data = await cursor.fetchone()

                                if existing_user_data:
                                    existing_user_id, existing_username = existing_user_data
                                    await interaction.response.send_message(
                                        f"Error: This Riot ID is already linked to another Discord user: <@{existing_user_id}>. "
                                        "If this is a mistake, please contact an administrator.",
                                        ephemeral=True
                                    )
                            else:
                                raise e  # Reraise the error if it's not related to UNIQUE constraint
                else:
                    # Riot ID does not exist or other error
                    error_msg = await response.text()
                    print(f"Riot API error response: {error_msg}")
                    await interaction.response.send_message(
                        f"The Riot ID '{riot_id}' could not be found. Please double-check and try again.",
                        ephemeral=True
                    )
    except Exception as e:
        print(f"An error occurred while connecting to the Riot API: {e}")
        await interaction.response.send_message(
            "An unexpected error occurred while trying to link your Riot ID. Please try again later.",
            ephemeral=True
        )

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