"""
Utility functions for the TournamentBot.

This module provides helper functions and constants used throughout the bot.
"""
import discord
from typing import Optional, List, Dict, Any, Tuple, Union
import asyncio

# Constants
ROLE_NAMES = ["Top", "Jungle", "Mid", "Bot", "Support"]
ROLE_EMOJIS = {"Top": "🔝", "Jungle": "🌳", "Mid": "🔄", "Bot": "🎯", "Support": "🛡️"}
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
        blue_field_value += f"{emoji} **{role_name}**: {player_name}\n"
    
    embed.add_field(name="Blue Team", value=blue_field_value or "No players", inline=True)
    
    # Add red team field
    red_field_value = ""
    for i, player in enumerate(red_team):
        role_name = ROLE_NAMES[i]
        emoji = ROLE_EMOJIS.get(role_name, "")
        player_name = getattr(player, "username", "Unknown")
        red_field_value += f"{emoji} **{role_name}**: {player_name}\n"
    
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

def format_player_info(player: Any, include_role: bool = True) -> str:
    """
    Format player information for display.
    
    Args:
        player: Player object
        include_role: Whether to include role information
        
    Returns:
        Formatted player information string
    """
    player_name = getattr(player, "username", "Unknown")
    tier = getattr(player, "tier", None)
    rank = getattr(player, "rank", "UNRANKED")
    
    result = f"**{player_name}** ({rank})"
    
    if include_role and hasattr(player, "assigned_role") and player.assigned_role is not None:
        role_index = player.assigned_role
        if 0 <= role_index < len(ROLE_NAMES):
            result += f" - {ROLE_NAMES[role_index]}"
    
    return result

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

async def defer_or_respond(
    interaction: discord.Interaction,
    content: Optional[str] = None,
    ephemeral: bool = False
) -> bool:
    """
    Defer an interaction or respond with content if provided.
    
    Args:
        interaction: Discord interaction
        content: Message content (optional)
        ephemeral: Whether the response should be ephemeral
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if content:
            await interaction.response.send_message(content, ephemeral=ephemeral)
        else:
            await interaction.response.defer(ephemeral=ephemeral)
        return True
    except Exception as e:
        print(f"Error deferring/responding to interaction: {e}")
        return False

# Player data processing
def sort_players_by_tier(players: List[Any]) -> List[Any]:
    """
    Sort a list of players by their tier.
    
    Args:
        players: List of players to sort
        
    Returns:
        Sorted list of players
    """
    return sorted(players, key=lambda p: getattr(p, "tier", 7))

def calculate_team_balance(team1: List[Any], team2: List[Any]) -> float:
    """
    Calculate the balance between two teams.
    
    Args:
        team1: First team
        team2: Second team
        
    Returns:
        Balance score (lower is better)
    """
    if not team1 or not team2:
        return float('inf')
    
    team1_avg_tier = sum(getattr(p, "tier", 7) for p in team1) / len(team1)
    team2_avg_tier = sum(getattr(p, "tier", 7) for p in team2) / len(team2)
    
    return abs(team1_avg_tier - team2_avg_tier)

# UI component helpers
def create_disabled_view(original_view: discord.ui.View) -> discord.ui.View:
    """
    Create a disabled version of a view.
    
    Args:
        original_view: Original view to disable
        
    Returns:
        New view with all components disabled
    """
    new_view = discord.ui.View(timeout=original_view.timeout)
    
    for item in original_view.children:
        if isinstance(item, discord.ui.Button):
            new_button = discord.ui.Button(
                style=item.style,
                label=item.label,
                disabled=True,
                custom_id=item.custom_id,
                url=item.url,
                emoji=item.emoji,
                row=item.row
            )
            new_view.add_item(new_button)
        elif isinstance(item, discord.ui.Select):
            new_select = discord.ui.Select(
                placeholder=item.placeholder,
                min_values=item.min_values,
                max_values=item.max_values,
                options=item.options,
                disabled=True,
                custom_id=item.custom_id,
                row=item.row
            )
            new_view.add_item(new_select)
    
    return new_view

def get_button_style_for_role(role_name: str) -> discord.ButtonStyle:
    """
    Get the button style for a specific role.
    
    Args:
        role_name: Role name
        
    Returns:
        Button style for the role
    """
    role_styles = {
        "Top": discord.ButtonStyle.primary,
        "Jungle": discord.ButtonStyle.success,
        "Mid": discord.ButtonStyle.danger,
        "Bot": discord.ButtonStyle.secondary,
        "Support": discord.ButtonStyle.success
    }
    
    return role_styles.get(role_name, discord.ButtonStyle.secondary)

# Error handling
def format_error_message(error: Exception, user_friendly: bool = True) -> str:
    """
    Format an error message for display to users.
    
    Args:
        error: Exception object
        user_friendly: Whether to use user-friendly messages
        
    Returns:
        Formatted error message
    """
    if user_friendly:
        # Map common errors to user-friendly messages
        error_str = str(error).lower()
        
        if "permission" in error_str:
            return "I don't have permission to do that. Please check my role permissions."
        elif "not found" in error_str:
            return "The requested resource couldn't be found."
        elif "timeout" in error_str or "timed out" in error_str:
            return "The operation timed out. Please try again later."
        elif "rate limit" in error_str:
            return "I'm being rate limited. Please try again in a moment."
        else:
            return f"An error occurred: {str(error)}"
    else:
        # Return detailed error for logging
        return f"{type(error).__name__}: {str(error)}"

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