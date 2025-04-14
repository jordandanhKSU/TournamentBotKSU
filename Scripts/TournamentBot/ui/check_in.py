"""
Check-in UI components for TournamentBot.

This module provides the UI elements for player check-in, including buttons
for checking in, leaving, volunteering, and starting/canceling games.
"""
import discord
import random
import os
from typing import List, Dict, Any, Optional, Tuple, Union
import sys

# First add the parent directory (TournamentBot) to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Then add the Scripts directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import from local package using relative paths
from ..utils import helpers
from ..game.game_state import GlobalGameState

# Import from parent directory
import databaseManager
import Matchmaking


class StartGameView(discord.ui.View):
    """View for the check-in and game start process."""
    def __init__(self, creator_id: int):
        """
        Initialize the check-in view.
        
        Args:
            creator_id: Discord ID of the creator of the check-in
        """
        super().__init__(timeout=None)
        self.creator_id = creator_id
        self.checked_in_users = []
        self.volunteers = []  # Track users who volunteer to be removed first
        self.check_in_started = True
        self.channel = None  # Store the channel where check-in is happening
        self.message_id = None  # Store the message ID of the check-in message
        self.auto_recheckin = False  # Flag to indicate if this view was auto-created by Next Game

    @discord.ui.button(label="Check In", style=discord.ButtonStyle.green)
    async def check_in_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Handle check-in requests from users.
        
        Args:
            interaction: Discord interaction
            button: The check-in button
        """
        # Check for duplicate check-ins, adapted to work with both real Discord users and dummy members
        user_id = str(interaction.user.id)
        is_duplicate = False
        
        for user in self.checked_in_users:
            # Handle both real Discord users and dummy members which might have different properties
            existing_id = getattr(user, 'id', None)
            if existing_id is None:
                # For dummy members, might be stored as attribute
                existing_id = getattr(user, 'discord_id', None)
            
            # Convert to string for comparison to be safe
            if str(existing_id) == user_id:
                is_duplicate = True
                break
        
        if is_duplicate:
            await interaction.response.send_message("You've already checked in!", ephemeral=True)
            return
        
        # Get player info to check for Riot ID and role preference
        player_info = await databaseManager.get_player_info(str(interaction.user.id))
        has_role_preference = player_info is not None and player_info.role_preference
        has_riot_id = player_info is not None and player_info.player_riot_id is not None
        
        # Check configuration status and send appropriate messages
        if not has_riot_id and not has_role_preference:
            await interaction.response.send_message(
                "Before checking in, you must link your Riot ID and set your role preference. "
                "Please use the `/link` command to connect your Riot ID and the `/rolepreference` command to set your role preference.",
                ephemeral=True
            )
            return
        elif not has_riot_id:
            await interaction.response.send_message(
                "You need to link your Riot ID before checking in. "
                "Please use the `/link` command to connect your account.",
                ephemeral=True
            )
            return
        elif not has_role_preference:
            await interaction.response.send_message(
                "You need to set your role preference before checking in. "
                "Please use the `/rolepreference` command to indicate your preferred roles.",
                ephemeral=True
            )
            return
        
        # Update username and check if rank has changed
        await databaseManager.update_username(interaction.user)
        
        # Check if player's rank has changed since last check-in
        has_changed, rank_message = await databaseManager.check_and_update_rank(
            str(interaction.user.id), player_info.player_riot_id
        )
        
        self.checked_in_users.append(interaction.user)
        await self.update_embed(interaction)
        
        # Construct the response message based on whether rank changed
        if has_changed:
            await interaction.response.send_message(
                f"Successfully checked in! {rank_message}",
                ephemeral=True
            )
        else:
            await interaction.response.send_message("Successfully checked in!", ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red)
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Handle requests to leave the check-in list.
        
        Args:
            interaction: Discord interaction
            button: The leave button
        """
        # Check if user is in the checked-in list using the same robust ID comparison
        user_id = str(interaction.user.id)
        is_checked_in = False
        user_index = -1
        
        for idx, user in enumerate(self.checked_in_users):
            # Handle both real Discord users and dummy members
            existing_id = getattr(user, 'id', None)
            if existing_id is None:
                # For dummy members, might be stored as attribute
                existing_id = getattr(user, 'discord_id', None)
            
            # Convert to string for comparison to be safe
            if str(existing_id) == user_id:
                is_checked_in = True
                user_index = idx
                break
        
        if not is_checked_in:
            await interaction.response.send_message("You're not checked in!", ephemeral=True)
            return
        
        # Remove user from checked-in list
        if user_index >= 0:
            self.checked_in_users.pop(user_index)
        else:
            # Fallback to original method if index wasn't found
            self.checked_in_users = [user for user in self.checked_in_users
                                   if str(getattr(user, 'id', getattr(user, 'discord_id', None))) != user_id]
        # Also remove from volunteers if they were in that list
        # Check volunteer status using the same ID comparison logic
        volunteer_ids = [str(getattr(v, 'id', getattr(v, 'discord_id', None))) for v in self.volunteers]
        if user_id in volunteer_ids:
            self.volunteers = [volunteer for volunteer in self.volunteers if volunteer.id != interaction.user.id]
        
        await self.update_embed(interaction)
        await interaction.response.send_message("You've left the check-in list.", ephemeral=True)
    
    @discord.ui.button(label="Volunteer", style=discord.ButtonStyle.blurple)
    async def volunteer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Handle requests to volunteer to be cut from games first.
        
        Args:
            interaction: Discord interaction
            button: The volunteer button
        """
        # Check if user is checked in - use the same robust ID comparison
        user_id = str(interaction.user.id)
        is_checked_in = False
        user_obj = None
        
        for user in self.checked_in_users:
            # Handle both real Discord users and dummy members
            existing_id = getattr(user, 'id', None)
            if existing_id is None:
                # For dummy members, might be stored as attribute
                existing_id = getattr(user, 'discord_id', None)
            
            # Convert to string for comparison to be safe
            if str(existing_id) == user_id:
                is_checked_in = True
                user_obj = user
                break
        
        if not is_checked_in:
            await interaction.response.send_message("You're not checked in! Please check in first.", ephemeral=True)
            return
            
        # Check if already volunteered - use the same robust ID comparison
        volunteer_ids = [str(getattr(v, 'id', getattr(v, 'discord_id', None))) for v in self.volunteers]
        if user_id in volunteer_ids:
            # Remove from volunteers
            self.volunteers = [volunteer for volunteer in self.volunteers
                              if str(getattr(volunteer, 'id', getattr(volunteer, 'discord_id', None))) != user_id]
            await interaction.response.send_message("You are no longer volunteering to be cut first.", ephemeral=True)
        else:
            # Add to volunteers
            if user_obj:
                self.volunteers.append(user_obj)
            await interaction.response.send_message("You have volunteered to be cut first if needed.", ephemeral=True)
        
        await self.update_embed(interaction)

# Start Game and Cancel Game buttons are removed from check-in UI.
# They are now only available in the admin channel's Global Controls

    async def update_embed(self, interaction: discord.Interaction):
        """
        Update the check-in embed with current player list.
        
        Args:
            interaction: Discord interaction
        """
        # Store channel and message ID for reference by GlobalPhase1View
        if self.channel is None:
            self.channel = interaction.channel
        
        if self.message_id is None and interaction.message:
            self.message_id = interaction.message.id
        
        embed = discord.Embed(
            title="Game Check-in",
            description="Click the buttons below to check in for the game!",
            color=discord.Color.blue()
        )
        
        # Add the list of checked-in users
        user_list = []
        for i, user in enumerate(self.checked_in_users):
            volunteer_status = " (Volunteer)" if user in self.volunteers else ""
            user_list.append(f"{i+1}. {user.mention}{volunteer_status}")
        
        if user_list:
            embed.add_field(
                name=f"Checked-in Players ({len(self.checked_in_users)})",
                value="\n".join(user_list),
                inline=False
            )
        else:
            embed.add_field(
                name="Checked-in Players (0)",
                value="No players checked in yet",
                inline=False
            )
        
        embed.set_footer(text="A minimum of 10 players is required to start a game")
        await interaction.message.edit(embed=embed)

    async def disable_all_buttons(self, message=None, reason="This check-in has been closed."):
        """
        Disable all buttons and update the check-in message.
        
        Args:
            message: The message to update (if None, will try to fetch from channel)
            reason: The reason to display for disabling
        """
        # Disable all buttons
        for child in self.children:
            child.disabled = True
        
        # If no message provided, try to fetch it
        if not message and self.channel and self.message_id:
            try:
                message = await self.channel.fetch_message(self.message_id)
            except Exception as e:
                print(f"Error fetching check-in message: {e}")
                return False
        
        # If we have a message, update it
        if message:
            try:
                embed = message.embeds[0]
                embed.title = "Game Check-in (Closed)"
                embed.description = reason
                embed.color = discord.Color.dark_gray()
                
                await message.edit(embed=embed, view=self)
                return True
            except Exception as e:
                print(f"Error updating check-in message: {e}")
                return False
        
        return False


class DummyMember:
    """A simplified mock of a Discord member for testing purposes."""
    def __init__(self, id):
        """
        Initialize a dummy member.
        
        Args:
            id: Discord ID of the member
        """
        self.id = id
        self.mention = f"<@{id}>"