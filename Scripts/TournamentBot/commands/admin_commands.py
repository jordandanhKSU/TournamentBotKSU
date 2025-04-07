"""
Admin commands for TournamentBot.

This module contains commands that are intended for admin use, including
channel configuration, check-in management, and game administration.
"""
import discord
from discord import app_commands
import os
import sys
from typing import List, Optional
from dotenv import find_dotenv, set_key

# First add the parent directory (TournamentBot) to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Then add the Scripts directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import from local package using relative paths
from ..utils import helpers
from ..ui.check_in import StartGameView

def setup_admin_commands(bot, MY_GUILD):
    """
    Set up admin commands for the bot.
    
    Args:
        bot: Discord bot instance
        MY_GUILD: Guild to register commands in
    """
    
    @bot.tree.command(
        name="createadminchannel",
        description="Set the current channel as the admin channel for game management",
        guild=MY_GUILD
    )
    async def create_admin_channel(interaction: discord.Interaction):
        """Sets the current channel as the admin channel for tournament management."""
        # Check if user has admin permissions
        if not helpers.has_admin_permission(interaction.user):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return
            
        channel_id = str(interaction.channel.id)
        os.environ["ADMIN_CHANNEL"] = channel_id
        dotenv_path = find_dotenv()
        set_key(dotenv_path, "ADMIN_CHANNEL", channel_id)
        await interaction.response.send_message(
            f"Admin channel set to {interaction.channel.mention}.",
            ephemeral=True
        )

    @bot.tree.command(
        name="checkin",
        description="Start a check-in process for a game",
        guild=MY_GUILD
    )
    async def checkin(interaction: discord.Interaction):
        """Command to start a check-in process for a game."""
        # Check if user has admin permissions
        if not helpers.has_admin_permission(interaction.user):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return
            
        embed = discord.Embed(
            title="Game Check-in",
            description="Click the buttons below to check in for the game!",
            color=helpers.COLOR_BLUE
        )
        
        embed.add_field(
            name="Checked-in Players (0)",
            value="No players checked in yet",
            inline=False
        )
        
        embed.set_footer(text="A minimum of 10 players is required to start a game")
        
        view = StartGameView(interaction.user.id)
        await interaction.response.send_message(embed=embed, view=view)

    @bot.tree.command(
        name="force_check_in",
        description="Force check-in users by their ID range (Admin only)",
        guild=MY_GUILD
    )
    async def force_check_in(interaction: discord.Interaction, start_id: int, end_id: int):
        """
        Forcefully check in a range of users by their ID.
        Useful for testing with a small group of real users.
        
        Args:
            interaction: Discord interaction
            start_id: Starting ID in the range
            end_id: Ending ID in the range
        """
        # Check if user has admin permissions
        if not helpers.has_admin_permission(interaction.user):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return
            
        await interaction.response.defer(ephemeral=True)
        
        # Create a check-in view
        embed = discord.Embed(
            title="Game Check-in (Force)",
            description="Forced check-in is active!",
            color=helpers.COLOR_BLUE
        )
        
        view = StartGameView(interaction.user.id)
        
        # Add dummy members to the check-in list
        from Scripts.TournamentBot.ui.check_in import DummyMember
        for i in range(start_id, end_id + 1):
            view.checked_in_users.append(DummyMember(i))
        
        # Update the embed with the user list
        user_list = []
        for i, user in enumerate(view.checked_in_users):
            user_list.append(f"{i+1}. {user.mention}")
        
        if user_list:
            embed.add_field(
                name=f"Checked-in Players ({len(view.checked_in_users)})",
                value="\n".join(user_list),
                inline=False
            )
        
        # Send the check-in message
        message = await interaction.channel.send(embed=embed, view=view)
        
        await interaction.followup.send(
            f"Force-checked in {len(view.checked_in_users)} users.",
            ephemeral=True
        )