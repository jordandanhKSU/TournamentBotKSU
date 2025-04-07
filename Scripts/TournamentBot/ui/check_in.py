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

    @discord.ui.button(label="Check In", style=discord.ButtonStyle.green)
    async def check_in_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Handle check-in requests from users.
        
        Args:
            interaction: Discord interaction
            button: The check-in button
        """
        if any(user.id == interaction.user.id for user in self.checked_in_users):
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
        if not any(user.id == interaction.user.id for user in self.checked_in_users):
            await interaction.response.send_message("You're not checked in!", ephemeral=True)
            return
        
        self.checked_in_users = [user for user in self.checked_in_users if user.id != interaction.user.id]
        # Also remove from volunteers if they were in that list
        if interaction.user.id in [volunteer.id for volunteer in self.volunteers]:
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
        # Check if user is checked in
        if not any(user.id == interaction.user.id for user in self.checked_in_users):
            await interaction.response.send_message("You're not checked in! Please check in first.", ephemeral=True)
            return
            
        # Check if already volunteered
        if any(volunteer.id == interaction.user.id for volunteer in self.volunteers):
            # Remove from volunteers
            self.volunteers = [volunteer for volunteer in self.volunteers if volunteer.id != interaction.user.id]
            await interaction.response.send_message("You are no longer volunteering to be cut first.", ephemeral=True)
        else:
            # Add to volunteers
            for user in self.checked_in_users:
                if user.id == interaction.user.id:
                    self.volunteers.append(user)
                    break
            await interaction.response.send_message("You have volunteered to be cut first if needed.", ephemeral=True)
        
        await self.update_embed(interaction)

    @discord.ui.button(label="Start\nGame", style=discord.ButtonStyle.green, row=1)
    async def start_game_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Handle game start process initiated by the creator.
        
        Args:
            interaction: Discord interaction
            button: The start game button
        """
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message("Only the creator can start the game!", ephemeral=True)
            return

        await interaction.response.defer()
        
        # Build a list of Player objects from the check-in list
        players = []
        for user in self.checked_in_users:
            player_obj = await databaseManager.get_player_info(str(user.id))
            if player_obj is not None:
                players.append(player_obj)

        if not players:
            await interaction.followup.send("No valid players found in the check-in list!", ephemeral=True)
            return
            
        # Check if we have at least 10 players (minimum required for one game)
        if len(players) < 10:
            await interaction.followup.send(
                f"Not enough players to start a game. You need at least 10 players, but only have {len(players)}.",
                ephemeral=True
            )
            return
            
        # Only disable buttons if we have enough players and are actually starting the game
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        # Get list of volunteers who are playing (they have player objects)
        volunteer_players = []
        for volunteer in self.volunteers:
            for player in players:
                if str(volunteer.id) == player.discord_id:
                    volunteer_players.append(player)
                    break
        
        # Remove players until count is a multiple of 10, prioritizing volunteers
        cut_players = []
        while len(players) % 10 != 0:
            if volunteer_players:
                # Remove a volunteer first if available
                removed = volunteer_players.pop(0)
            else:
                # Otherwise remove a random player
                removed = random.choice(players)
            
            players.remove(removed)
            cut_players.append(removed)
        
        # Use the matchmaking algorithm to create teams
        blue_teams, red_teams = Matchmaking.matchmaking_multiple(players)
        games = []
        for i in range(len(blue_teams)):
            games.append({"blue": blue_teams[i], "red": red_teams[i]})
        
        # Get the game state singleton
        game_state = GlobalGameState.get_instance()
        
        # Initialize the game state with teams and sitting-out players
        await game_state.initialize_games(games, cut_players, interaction.channel)

        # Find the admin channel
        admin_channel_id = os.getenv("ADMIN_CHANNEL")
        if not admin_channel_id:
            await interaction.followup.send(
                "Admin channel not set. Please run the createAdminChannel command first.",
                ephemeral=True
            )
            return
        
        admin_channel = interaction.guild.get_channel(int(admin_channel_id))
        if not admin_channel:
            await interaction.followup.send(
                "Admin channel not found. Please run the createAdminChannel command again.",
                ephemeral=True
            )
            return
            
        game_state.admin_channel = admin_channel
            
        # Create game control messages - use relative imports for consistency
        from ..ui.game_control import GameControlView
        
        # Send game control messages to admin channel
        for i in range(len(games)):
            embed = game_state.generate_embed(i)
            view = GameControlView(game_state, i)
            message = await admin_channel.send(embed=embed, view=view)
            game_state.message_references[f"game_control_{i}"] = message
        
        # Send sitting out message
        if cut_players:
            from ..ui.game_control import SittingOutView
            
            embed = game_state.generate_sitting_out_embed()
            view = SittingOutView(game_state)
            message = await admin_channel.send(embed=embed, view=view)
            game_state.message_references["sitting_out"] = message
        
        # Create global controls for admins
        from ..ui.game_control import GlobalControlView
        from ..ui.game_control import GlobalSwapControlView
        
        # Control for game progression
        global_view = GlobalControlView(game_state)
        message = await admin_channel.send(
            "Global Game Controls:",
            view=global_view
        )
        game_state.message_references["global_control"] = message
        
        # Control for player swapping
        swap_view = GlobalSwapControlView(game_state)
        message = await admin_channel.send(
            "Team Balancing Controls:",
            view=swap_view
        )
        game_state.message_references["swap_control"] = message
        
        # Notify everyone about the game start
        await interaction.channel.send(
            f"✅ **Games have been created!** Check the admin channel for controls and details.\n"
            f"Total Players: {len(players)}\n"
            f"Number of Games: {len(games)}\n"
            f"Players Sitting Out: {len(cut_players)}"
        )
        
        # Send individual game embeds to the public channel
        for i in range(len(games)):
            embed = game_state.generate_embed(i)
            await interaction.channel.send(embed=embed)

    @discord.ui.button(label="Cancel\nGame", style=discord.ButtonStyle.danger, row=1)
    async def cancel_checkin_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Handle cancellation of the check-in process.
        
        Args:
            interaction: Discord interaction
            button: The cancel game button
        """
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message("Only the creator can cancel the game!", ephemeral=True)
            return
        
        # Disable all buttons
        for child in self.children:
            child.disabled = True
        
        # Update the message
        embed = discord.Embed(
            title="Check-in Cancelled",
            description="The check-in has been cancelled by the creator.",
            color=discord.Color.red()
        )
        await interaction.message.edit(embed=embed, view=self)
        
        await interaction.response.send_message("Check-in has been cancelled.", ephemeral=True)

    async def update_embed(self, interaction: discord.Interaction):
        """
        Update the check-in embed with current player list.
        
        Args:
            interaction: Discord interaction
        """
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