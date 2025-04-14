"""
Utility functions for the TournamentBot.

This module provides helper functions and constants used throughout the bot.
"""
import discord
from typing import Optional, List, Dict, Any, Tuple, Union
import asyncio

# Constants
ROLE_NAMES = ["Top", "Jun", "Mid", "Bot", "Sup"]
ROLE_EMOJIS = {"Top": "🏝", "Jun": "🌳", "Mid": "🐐", "Bot": "🎯", "Sup": "🛡️"}
BUTTON_STYLES = {
    "positive": discord.ButtonStyle.green,
    "negative": discord.ButtonStyle.red,
    "neutral": discord.ButtonStyle.gray,
    "primary": discord.ButtonStyle.blurple
}

# Color constants for embeds
COLOR_BLUE = discord.Color.blue()
COLOR_RED = discord.Color.red()
COLOR_GREEN = discord.Color.green()
COLOR_GOLD = discord.Color.gold()
COLOR_PURPLE = discord.Color.purple()

# Discord message/embed formatting functions
def create_game_embed(game_data: Dict[str, Any], game_index: int) -> discord.Embed:
    """
    Create a standardized embed for game display.
    
    Args:
        game_data: Dictionary containing game information
        game_index: Index of the game
        
    Returns:
        Discord embed for displaying game information
    """
    blue_team = game_data.get("blue", [])
    red_team = game_data.get("red", [])
    result = game_data.get("result", None)
    
    # Create the base embed
    if result == "blue":
        embed = discord.Embed(title=f"Game {game_index + 1} - Blue Team Won!", color=COLOR_BLUE)
    elif result == "red":
        embed = discord.Embed(title=f"Game {game_index + 1} - Red Team Won!", color=COLOR_RED)
    else:
        embed = discord.Embed(title=f"Game {game_index + 1}", color=COLOR_PURPLE)
    
    # Add blue team field
    blue_field_value = ""
    for i, player in enumerate(blue_team):
        role_name = ROLE_NAMES[i]
        emoji = ROLE_EMOJIS.get(role_name, "")
        player_name = getattr(player, "username", "Unknown")
        player_tier = getattr(player, "tier", "Unknown")
        player_rank = getattr(player, "rank", "Unknown")

        blue_field_value += (f"{emoji}\n"
                             f"**{role_name}**: {player_name}\n"
                             f"**Rank**: {player_rank}\n"  
                             f"**Tier**: {player_tier}\n\n"
                             )
    
    embed.add_field(name="Blue Team", value=blue_field_value or "No players", inline=True)
    
    # Add red team field
    red_field_value = ""
    for i, player in enumerate(red_team):
        role_name = ROLE_NAMES[i]
        emoji = ROLE_EMOJIS.get(role_name, "")
        player_name = getattr(player, "username", "Unknown")
        player_tier = getattr(player, "tier", "Unknown")
        player_rank = getattr(player, "rank", "Unknown")

        red_field_value += (f"{emoji}\n" 
                            f"**{role_name}**: {player_name}\n"
                            f"**Rank**: {player_rank}\n"  
                            f"**Tier**: {player_tier}\n\n"
                             )
    
    embed.add_field(name="Red Team", value=red_field_value or "No players", inline=True)
    
    # Add MVP if available
    mvp_id = game_data.get("mvp", None)
    if mvp_id:
        for team in [blue_team, red_team]:
            for player in team:
                if getattr(player, "discord_id", None) == mvp_id:
                    embed.add_field(name="MVP", value=getattr(player, "username", "Unknown"), inline=False)
                    break
    
    return embed

def create_sitting_out_embed(players: List[Any]) -> discord.Embed:
    """
    Create an embed for players who are sitting out.
    
    Args:
        players: List of players sitting out
        
    Returns:
        Discord embed for displaying sitting out players
    """
    embed = discord.Embed(title="Players Sitting Out", color=COLOR_GOLD)
    
    player_list = ""
    for i, player in enumerate(players):
        player_name = getattr(player, "username", "Unknown")
        player_list += f"{i+1}. {player_name}\n"
    
    embed.description = player_list or "No players sitting out"
    return embed

# Interaction helpers
async def safe_respond(
    interaction: discord.Interaction,
    content: Optional[str] = None,
    embed: Optional[discord.Embed] = None,
    view: Optional[discord.ui.View] = None,
    ephemeral: bool = False
) -> bool:
    """
    Safely respond to an interaction, handling already-responded cases.
    
    Args:
        interaction: Discord interaction
        content: Message content
        embed: Message embed
        view: UI view
        ephemeral: Whether the response should be ephemeral
        
    Returns:
        True if response was successful, False otherwise
    """
    try:
        if interaction.response.is_done():
            # If already responded, use followup
            await interaction.followup.send(
                content=content,
                embed=embed,
                view=view,
                ephemeral=ephemeral
            )
        else:
            # Initial response
            await interaction.response.send_message(
                content=content,
                embed=embed,
                view=view,
                ephemeral=ephemeral
            )
        return True
    except Exception as e:
        print(f"Error responding to interaction: {e}")
        return False


# Permission helpers
def has_admin_permission(member: discord.Member) -> bool:
    """
    Check if a member has admin permissions.
    
    Args:
        member: Discord member to check
        
    Returns:
        True if member has admin permissions, False otherwise
    """
    return (
        member.guild_permissions.administrator or
        member.guild_permissions.manage_guild or
        any(role.name.lower() in ["admin", "moderator", "mod"] for role in member.roles)
    )