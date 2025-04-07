"""
TournamentBot - Main entry point

This is the main entry point for the TournamentBot, responsible for initializing
all components, registering commands, and running the bot.
"""
import random
import os
import asyncio
import sys
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv, find_dotenv
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", mode="a")
    ]
)
logger = logging.getLogger("TournamentBot")

# Add the parent directory (Scripts) to path to ensure imports work correctly
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)

# Import modules directly with explicit paths to avoid any potential import issues
from Scripts.TournamentBot.commands.admin_commands import setup_admin_commands
from Scripts.TournamentBot.commands.player_commands import setup_player_commands
from Scripts.TournamentBot.game.game_state import GlobalGameState

# Import modules from parent directory
import databaseManager
import Matchmaking

# ========== Configuration and Initialization ==========

load_dotenv(find_dotenv())

TOKEN = os.getenv('DISCORD_TOKEN')
SPREADSHEET_PATH = os.path.abspath(os.getenv('SPREADSHEET_PATH'))
DB_PATH = os.getenv('DB_PATH')
DISCORD_GUILD_ID = int(os.getenv('DISCORD_GUILD_ID'))
MY_GUILD = discord.Object(id=DISCORD_GUILD_ID)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Global variables to track the state of the application
current_checkin_view = None

# Reset the game state singleton on startup
GlobalGameState.reset_instance()


# ========== Bot Event Handlers ==========

@bot.event
async def on_ready():
    """Handler for when the bot is ready and connected to Discord."""
    logger.info(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await databaseManager.initialize_database()
    
    # Sync commands with the guild
    bot.tree.copy_global_to(guild=MY_GUILD)
    await bot.tree.sync(guild=MY_GUILD)
    
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} commands")
    except Exception as e:
        logger.error(f"Error syncing commands: {e}")


# ========== Register Commands ==========

# Set up admin commands
setup_admin_commands(bot, MY_GUILD)

# Set up player commands
setup_player_commands(bot, MY_GUILD)


# ========== Main Function ==========

def main():
    """Main function to run the bot."""
    if not TOKEN:
        logger.error("Discord token not found. Please check your .env file.")
        return
        
    try:
        logger.info("Starting bot...")
        bot.run(TOKEN)
    except discord.errors.LoginFailure:
        logger.error("Invalid Discord token. Please check your TOKEN in the .env file.")
    except Exception as e:
        logger.error(f"Error starting bot: {e}")


# ========== Entry Point ==========

if __name__ == "__main__":
    main()