import os
import aiosqlite
import asyncio
from openpyxl import load_workbook
from dotenv import load_dotenv, find_dotenv
import discord

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

# Function to update Discord username in the database if it's been changed.
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