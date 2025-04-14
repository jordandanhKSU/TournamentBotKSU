"""
Player commands for TournamentBot.

This module contains commands that are intended for player use, including
stats viewing, account linking, role preferences, and toxicity management.
"""
import discord
from discord import app_commands
import sys
import os
from typing import List, Optional

# First add the parent directory (TournamentBot) to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Then add the Scripts directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import from local package using relative paths
from ..utils import helpers
from ..ui.role_preference import create_role_preference_ui

# Import from parent directory
import databaseManager

def setup_player_commands(bot, MY_GUILD):
    """
    Set up player commands for the bot.
    
    Args:
        bot: Discord bot instance
        MY_GUILD: Guild to register commands in
    """
    
    @bot.tree.command(
        name="stats", 
        description="Display player statistics", 
        guild=MY_GUILD
    )
    async def stats(interaction: discord.Interaction, discord_id: str):
        """
        Displays statistics for a player based on their Discord ID.
        
        Args:
            interaction: Discord interaction
            discord_id: Discord ID of the player to display stats for
        """
        # Retrieve player information using the provided discord_id
        player = await databaseManager.get_player_info(discord_id)
        
        if not player:
            await interaction.response.send_message(
                f"No player found with Discord ID: {discord_id}", 
                ephemeral=True
            )
            return

        # Build the embed with the player's statistics
        embed = discord.Embed(
            title=f"Statistics for {player.username}", 
            color=helpers.COLOR_BLUE
        )
        embed.add_field(name="Discord ID", value=player.discord_id, inline=True)
        embed.add_field(name="Username", value=player.username, inline=True)
        embed.add_field(
            name="Riot ID", 
            value=player.player_riot_id if player.player_riot_id else "Not linked", 
            inline=True
        )
        embed.add_field(name="Participation", value=player.participation, inline=True)
        embed.add_field(name="Wins", value=player.wins, inline=True)
        embed.add_field(name="MVPs", value=player.mvps, inline=True)
        embed.add_field(name="Toxicity Points", value=player.toxicity_points, inline=True)
        embed.add_field(name="Games Played", value=player.games_played, inline=True)
        embed.add_field(
            name="Win Rate", 
            value=f"{player.win_rate:.2f}%" if player.win_rate is not None else "N/A", 
            inline=True
        )
        embed.add_field(name="Total Points", value=player.total_points, inline=True)
        embed.add_field(name="Player Tier", value=player.tier, inline=True)
        embed.add_field(name="Player Rank", value=player.rank, inline=True)
        
        # Convert role preference list to string (if exists)
        role_pref = "".join(str(x) for x in player.role_preference) if player.role_preference else "None"
        embed.add_field(name="Role Preference", value=role_pref, inline=True)
        
        await interaction.response.send_message(embed=embed, ephemeral=False)

    @bot.tree.command(
        name="unlink",
        description="Unlink your Riot ID from your Discord account",
        guild=MY_GUILD
    )
    async def unlink_riot_id_command(interaction: discord.Interaction):
        """
        Unlinks the user's Riot ID from their Discord account.
        
        Args:
            interaction: Discord interaction
        """
        # Defer response while we process
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Call the unlink function
            result = await databaseManager.unlink_riot_id(str(interaction.user.id))
            await interaction.followup.send(result, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(
                f"An unexpected error occurred: {str(e)}",
                ephemeral=True
            )

    @bot.tree.command(
        name="link",
        description="Link your Discord account with your Riot ID",
        guild=MY_GUILD
    )
    async def link_riot_id(interaction: discord.Interaction, riot_id: str):
        """
        Links the user's Discord account with their Riot ID.
        
        Args:
            interaction: Discord interaction
            riot_id: Riot ID to link (format: username#tagline)
        """
        # Defer response while we process
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Call the link function which now directly returns a message
            result = await databaseManager.link(interaction.user, riot_id)
            
            # Just use plain ephemeral messages instead of embeds
            if "ERROR:" in result:
                # Add suggestion for API key issues
                result += "\n\nPlease verify your Riot API key or obtain a new one from the Riot Developer Portal."
                
            await interaction.followup.send(result, ephemeral=True)
        
        except Exception as e:
            await interaction.followup.send(
                f"An unexpected error occurred: {str(e)}",
                ephemeral=True
            )

    @bot.tree.command(
        name="rolepreference",
        description="Set your role preferences",
        guild=MY_GUILD
    )
    async def role_preference(interaction: discord.Interaction):
        """
        Command to set role preferences for matchmaking.
        
        Args:
            interaction: Discord interaction
        """
        await create_role_preference_ui(interaction)