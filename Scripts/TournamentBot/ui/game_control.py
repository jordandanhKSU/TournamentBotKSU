"""
Game control UI components for TournamentBot.

This module provides the UI elements for game control, including game
management, MVP voting, team swapping, and game progression.
"""
import discord
import asyncio
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


# ===== Sitting Out Players UI =====

class SittingOutButton(discord.ui.Button):
    """Button for displaying sitting out players."""
    def __init__(self):
        """Initialize sitting out button."""
        super().__init__(
            label="Sitting Out Players",
            style=discord.ButtonStyle.secondary,
            disabled=True
        )


class SittingOutView(discord.ui.View):
    """View for displaying sitting out players."""
    def __init__(self, global_state: GlobalGameState):
        """
        Initialize the sitting out view.
        
        Args:
            global_state: Global game state instance
        """
        super().__init__(timeout=None)
        self.global_state = global_state
        self.add_item(SittingOutButton())


# ===== Game Player Buttons =====

class GamePlayerButton(discord.ui.Button):
    """Button representing a player in a game."""
    def __init__(self, game_index: int, team: str, player_index: int, player_name: str):
        """
        Initialize a game player button.
        
        Args:
            game_index: Index of the game
            team: Team name ("blue" or "red")
            player_index: Index of the player in the team
            player_name: Name of the player
        """
        super().__init__(
            label=player_name,
            style=discord.ButtonStyle.primary if team == "blue" else discord.ButtonStyle.danger,
            row=player_index
        )
        self.game_index = game_index
        self.team = team
        self.player_index = player_index
        self.player_name = player_name

    async def callback(self, interaction: discord.Interaction):
        """
        Handle button click for player selection.
        
        Args:
            interaction: Discord interaction
        """
        game_state = GlobalGameState.get_instance()
        await game_state.handle_selection(
            interaction, self.game_index, self.team, self.player_index, self.player_name
        )


# ===== MVP Voting Controls =====

class EndMVPVoteButton(discord.ui.Button):
    """Button to end MVP voting for a game."""
    def __init__(self, game_index: int):
        """
        Initialize end MVP vote button.
        
        Args:
            game_index: Index of the game
        """
        super().__init__(
            label="End Voting",
            style=discord.ButtonStyle.primary
        )
        self.game_index = game_index

    async def callback(self, interaction: discord.Interaction):
        """
        Handle button click to end MVP voting.
        
        Args:
            interaction: Discord interaction
        """
        game_state = GlobalGameState.get_instance()
        
        # Only admins can end voting
        if not helpers.has_admin_permission(interaction.user):
            await interaction.response.send_message(
                "Only administrators can end MVP voting.",
                ephemeral=True
            )
            return
        
        await game_state.end_mvp_voting(interaction, self.game_index)


class CancelMVPVoteButton(discord.ui.Button):
    """Button to cancel MVP voting for a game."""
    def __init__(self, game_index: int):
        """
        Initialize cancel MVP vote button.
        
        Args:
            game_index: Index of the game
        """
        super().__init__(
            label="Cancel Voting",
            style=discord.ButtonStyle.danger
        )
        self.game_index = game_index

    async def callback(self, interaction: discord.Interaction):
        """
        Handle button click to cancel MVP voting.
        
        Args:
            interaction: Discord interaction
        """
        game_state = GlobalGameState.get_instance()
        
        # Only admins can cancel voting
        if not helpers.has_admin_permission(interaction.user):
            await interaction.response.send_message(
                "Only administrators can cancel MVP voting.",
                ephemeral=True
            )
            return
        
        await game_state.cancel_mvp_voting(interaction, self.game_index)


class SkipMVPButton(discord.ui.Button):
    """Button to skip MVP voting for a game."""
    def __init__(self, game_index: int):
        """
        Initialize skip MVP button.
        
        Args:
            game_index: Index of the game
        """
        super().__init__(
            label="Skip MVP",
            style=discord.ButtonStyle.secondary
        )
        self.game_index = game_index

    async def callback(self, interaction: discord.Interaction):
        """
        Handle button click to skip MVP voting.
        
        Args:
            interaction: Discord interaction
        """
        game_state = GlobalGameState.get_instance()
        
        # Only admins can skip MVP voting
        if not helpers.has_admin_permission(interaction.user):
            embed = discord.Embed(
                title="Permission Error",
                description="Only administrators can skip MVP voting.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Get the game data
        if self.game_index >= len(game_state.games):
            embed = discord.Embed(
                title="Error",
                description="Invalid game index.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        game_data = game_state.games[self.game_index]
        if not game_data.get("result"):
            embed = discord.Embed(
                title="Error",
                description="Cannot skip MVP voting until a winner is declared.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Mark the MVP as NULL and update the UI
        game_data["mvp"] = None
        await game_state.update_all_messages()
        
        # Store match data in database without MVP
        try:
            result = game_data["result"]
            await databaseManager.store_match_data(game_data, result)
            await databaseManager.update_all_player_stats(game_data, result)
            
            # Success embed
            embed = discord.Embed(
                title="MVP Skipped",
                description=f"Skipped MVP for Game {self.game_index + 1}. Results recorded.",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
            # Check if all games have results and MVP voting completed or skipped
            all_resolved = True
            for i in range(len(game_state.games)):
                game_data = game_state.games[i]
                if not game_data.get("result") or (not game_data.get("mvp") and game_state.mvp_voting_active.get(i, False)):
                    all_resolved = False
                    break
            
            # If all games resolved, update the global control view to show Next Game button
            if all_resolved:
                # Get the global control message if it exists
                if "global_control" in game_state.message_references:
                    global_message = game_state.message_references["global_control"]
                    global_view = GlobalControlView(game_state)
                    global_embed = discord.Embed(
                        title="Global Game Controls",
                        description="All games complete. You can now proceed to the next game.",
                        color=discord.Color.blue()
                    )
                    await global_message.edit(embed=global_embed, view=global_view)
                    
        except Exception as e:
            error_embed = discord.Embed(
                title="Error",
                description=f"Error recording results: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=error_embed, ephemeral=True)


class GameMVPControlView(discord.ui.View):
    """View for controlling MVP voting for a specific game."""
    def __init__(self, game_index: int, is_voting_active: bool = False):
        """
        Initialize game MVP control view.
        
        Args:
            game_index: Index of the game
            is_voting_active: Whether MVP voting is active
        """
        super().__init__(timeout=None)
        
        if is_voting_active:
            self.add_item(EndMVPVoteButton(game_index))
            self.add_item(CancelMVPVoteButton(game_index))
        else:
            # When voting is not active, add the Skip MVP button
            # Only if there's a game result but no MVP
            game_state = GlobalGameState.get_instance()
            if game_index < len(game_state.games):
                game_data = game_state.games[game_index]
                if game_data.get("result") and not game_data.get("mvp"):
                    self.add_item(SkipMVPButton(game_index))


# ===== Game Result and MVP Buttons =====

class MVPVoteButton(discord.ui.Button):
    """Button to start MVP voting for a game after winner is declared."""
    def __init__(self, game_index: int, blue_team=None, red_team=None):
        """
        Initialize MVP vote button.
        
        Args:
            game_index: Index of the game
            blue_team: Blue team players
            red_team: Red team players
        """
        super().__init__(
            label="Start MVP Voting",
            style=discord.ButtonStyle.primary
        )
        self.game_index = game_index
        self.blue_team = blue_team
        self.red_team = red_team

    async def callback(self, interaction: discord.Interaction):
        """
        Handle button click to start MVP voting.
        
        Args:
            interaction: Discord interaction
        """
        # Only admins can start MVP voting
        if not helpers.has_admin_permission(interaction.user):
            embed = discord.Embed(
                title="Permission Error",
                description="Only administrators can start MVP voting.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        game_state = GlobalGameState.get_instance()
        await game_state.start_mvp_voting(interaction, self.game_index)
        
        # Disable the current view
        for child in self.view.children:
            child.disabled = True
        await interaction.message.edit(view=self.view)
        
        # Check if all games have results and MVP voting completed or skipped
        all_resolved = True
        for i in range(len(game_state.games)):
            game_data = game_state.games[i]
            if not game_data.get("result") or (not game_data.get("mvp") and game_state.mvp_voting_active.get(i, False)):
                all_resolved = False
                break
        
        # If all games resolved, update the global control view to show Next Game button
        if all_resolved:
            # Get the global control message if it exists
            if "global_control" in game_state.message_references:
                global_message = game_state.message_references["global_control"]
                global_view = GlobalControlView(game_state)
                global_embed = discord.Embed(
                    title="Global Game Controls",
                    description="All games complete. You can now proceed to the next game.",
                    color=discord.Color.blue()
                )
                await global_message.edit(embed=global_embed, view=global_view)


class BlueWinButton(discord.ui.Button):
    """Button to declare Blue team as the winner."""
    def __init__(self, game_index: int, blue_team: list, red_team: list):
        """
        Initialize blue win button.
        
        Args:
            game_index: Index of the game
            blue_team: Blue team players
            red_team: Red team players
        """
        super().__init__(
            label="Blue Team Won",
            style=discord.ButtonStyle.primary
        )
        self.game_index = game_index
        self.blue_team = blue_team
        self.red_team = red_team

    async def callback(self, interaction: discord.Interaction):
        """
        Handle button click to declare Blue team as winner.
        
        Args:
            interaction: Discord interaction
        """
        # Only admins can declare winner
        if not helpers.has_admin_permission(interaction.user):
            embed = discord.Embed(
                title="Permission Error",
                description="Only administrators can declare a winner.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        game_state = GlobalGameState.get_instance()
        
        # Update game result
        if self.game_index < len(game_state.games):
            game_state.games[self.game_index]["result"] = "blue"
            game_state.game_results[self.game_index] = "blue"
            
            # Update the winner in the database
            try:
                winners = self.blue_team
                await databaseManager.update_wins(winners)
                
                # Only update games played for non-winners since update_wins updates it for winners
                for player in self.red_team:
                    await databaseManager.update_games_played(player.discord_id)
            except Exception as e:
                print(f"Error updating database: {e}")
        
        # Update the message with new embed
        embed = game_state.generate_embed(self.game_index)
        
        # Create new view with MVP voting and Skip MVP buttons
        mvp_view = discord.ui.View(timeout=None)
        mvp_view.add_item(MVPVoteButton(self.game_index, self.blue_team, self.red_team))
        mvp_view.add_item(SkipMVPButton(self.game_index))
        
        await interaction.message.edit(embed=embed, view=mvp_view)
        
        # Create a success embed instead of raw message
        success_embed = discord.Embed(
            title="Game Result Recorded",
            description=f"Blue Team has been marked as the winner for Game {self.game_index + 1}.",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=success_embed, ephemeral=True)


class RedWinButton(discord.ui.Button):
    """Button to declare Red team as the winner."""
    def __init__(self, game_index: int, blue_team: list, red_team: list):
        """
        Initialize red win button.
        
        Args:
            game_index: Index of the game
            blue_team: Blue team players
            red_team: Red team players
        """
        super().__init__(
            label="Red Team Won",
            style=discord.ButtonStyle.danger
        )
        self.game_index = game_index
        self.blue_team = blue_team
        self.red_team = red_team

    async def callback(self, interaction: discord.Interaction):
        """
        Handle button click to declare Red team as winner.
        
        Args:
            interaction: Discord interaction
        """
        # Only admins can declare winner
        if not helpers.has_admin_permission(interaction.user):
            embed = discord.Embed(
                title="Permission Error",
                description="Only administrators can declare a winner.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        game_state = GlobalGameState.get_instance()
        
        # Update game result
        if self.game_index < len(game_state.games):
            game_state.games[self.game_index]["result"] = "red"
            game_state.game_results[self.game_index] = "red"
            
            # Update the winner in the database
            try:
                winners = self.red_team
                await databaseManager.update_wins(winners)
                
                # Only update games played for non-winners since update_wins updates it for winners
                for player in self.blue_team:
                    await databaseManager.update_games_played(player.discord_id)
            except Exception as e:
                print(f"Error updating database: {e}")
        
        # Update the message with new embed
        embed = game_state.generate_embed(self.game_index)
        
        # Create new view with MVP voting and Skip MVP buttons
        mvp_view = discord.ui.View(timeout=None)
        mvp_view.add_item(MVPVoteButton(self.game_index, self.blue_team, self.red_team))
        mvp_view.add_item(SkipMVPButton(self.game_index))
        
        await interaction.message.edit(embed=embed, view=mvp_view)
        
        # Create a success embed instead of raw message
        success_embed = discord.Embed(
            title="Game Result Recorded",
            description=f"Red Team has been marked as the winner for Game {self.game_index + 1}.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=success_embed, ephemeral=True)


class GameControlView(discord.ui.View):
    """View for controlling a specific game."""
    def __init__(self, global_state: GlobalGameState, game_index: int, show_players: bool = False):
        """
        Initialize game control view.
        
        Args:
            global_state: Global game state instance
            game_index: Index of the game
            show_players: Whether to show player buttons for swapping
        """
        super().__init__(timeout=None)
        self.global_state = global_state
        self.game_index = game_index
        self.show_players = show_players
        
        if game_index < len(global_state.games):
            game_data = global_state.games[game_index]
            blue_team = game_data.get("blue", [])
            red_team = game_data.get("red", [])
            
            # If there's no result yet, add winner buttons
            if not game_data.get("result"):
                self.add_item(BlueWinButton(game_index, blue_team, red_team))
                self.add_item(RedWinButton(game_index, blue_team, red_team))
            else:
                # If there is a result but no MVP, add MVP voting and skip MVP buttons
                if not game_data.get("mvp"):
                    self.add_item(MVPVoteButton(game_index, blue_team, red_team))
                    self.add_item(SkipMVPButton(game_index))
            
            # Only add player buttons if swap mode is active and show_players is true
            if not self.show_players or not self.global_state.swap_mode:
                return
                
            # Add player buttons for team swapping - Blue team top row, Red team bottom row
            selected_player = self.global_state.selected_player1
            
            # Blue team on top row
            for i, player in enumerate(blue_team):
                player_name = getattr(player, "username", "Unknown")
                # Check if this player is selected for swapping
                is_selected = (
                    game_state.swap_mode and
                    selected_player is not None and
                    selected_player[0] == game_index and
                    selected_player[1] == "blue" and
                    selected_player[2] == i
                )
                
                # Add role information to player name if available
                role_index = getattr(player, "assigned_role", None)
                display_name = player_name
                if role_index is not None and 0 <= role_index < len(helpers.ROLE_NAMES):
                    role_name = helpers.ROLE_NAMES[role_index]
                    emoji = helpers.ROLE_EMOJIS.get(role_name, "")
                    display_name = f"{emoji} {player_name}"
                
                # Create the button with highlighting if selected
                button = GamePlayerButton(game_index, "blue", i, display_name)
                if is_selected:
                    button.label = f"✓ {button.label}"
                self.add_item(button)
            
            # Red team on bottom row
            for i, player in enumerate(red_team):
                player_name = getattr(player, "username", "Unknown")
                # Check if this player is selected for swapping
                is_selected = (
                    game_state.swap_mode and
                    selected_player is not None and
                    selected_player[0] == game_index and
                    selected_player[1] == "red" and
                    selected_player[2] == i
                )
                
                # Add role information to player name if available
                role_index = getattr(player, "assigned_role", None)
                display_name = player_name
                if role_index is not None and 0 <= role_index < len(helpers.ROLE_NAMES):
                    role_name = helpers.ROLE_NAMES[role_index]
                    emoji = helpers.ROLE_EMOJIS.get(role_name, "")
                    display_name = f"{emoji} {player_name}"
                
                # Create the button with highlighting if selected
                button = GamePlayerButton(game_index, "red", i, display_name)
                if is_selected:
                    button.label = f"✓ {button.label}"
                self.add_item(button)


# ===== MVP Voting UI =====

class MVPVotingView(discord.ui.View):
    """View for players to cast their MVP votes."""
    def __init__(self, global_state, game_index, players):
        """
        Initialize MVP voting view.
        
        Args:
            global_state: Global game state instance
            game_index: Index of the game
            players: List of players in the game
        """
        super().__init__(timeout=None)
        self.global_state = global_state
        self.game_index = game_index
        
        # Add player buttons for each team
        game_data = global_state.games[game_index]
        
        # Put all blue team buttons on row 0
        blue_team = game_data.get("blue", [])
        for i, player in enumerate(blue_team):
            player_name = getattr(player, "username", "Unknown")
            self.add_item(PlayerMVPButton(game_index, player, True, 0))
        
        # Put all red team buttons on row 1
        red_team = game_data.get("red", [])
        for i, player in enumerate(red_team):
            player_name = getattr(player, "username", "Unknown")
            self.add_item(PlayerMVPButton(game_index, player, False, 1))


class PlayerMVPButton(discord.ui.Button):
    """Button for voting for a specific player as MVP."""
    def __init__(self, game_index, player, is_blue_team, row=0):
        """
        Initialize player MVP button.
        
        Args:
            game_index: Index of the game
            player: Player object
            is_blue_team: Whether this player is on the blue team
            row: Button row in the view
        """
        self.player = player
        self.game_index = game_index
        player_name = getattr(player, "username", "Unknown")
        
        role_index = getattr(player, "assigned_role", None)
        if role_index is not None and 0 <= role_index < len(helpers.ROLE_NAMES):
            role_name = helpers.ROLE_NAMES[role_index]
            emoji = helpers.ROLE_EMOJIS.get(role_name, "")
            label = f"{emoji} {player_name}"
        else:
            label = player_name
        
        super().__init__(
            label=label,
            style=discord.ButtonStyle.primary if is_blue_team else discord.ButtonStyle.danger,
            row=row
        )

    async def callback(self, interaction: discord.Interaction):
        """
        Handle button click to vote for a player as MVP.
        
        Args:
            interaction: Discord interaction
        """
        game_state = GlobalGameState.get_instance()
        
        # Check if voting is active
        if not game_state.mvp_voting_active.get(self.game_index, False):
            await interaction.response.send_message(
                "MVP voting is no longer active for this game.",
                ephemeral=True
            )
            return
        
        # Check if user is in the game
        in_game = False
        voter_id = str(interaction.user.id)
        for team in ["blue", "red"]:
            for player in game_state.games[self.game_index][team]:
                if getattr(player, "discord_id", None) == voter_id:
                    in_game = True
                    break
        
        if not in_game:
            await interaction.response.send_message(
                "Only players in this game can vote for MVP.",
                ephemeral=True
            )
            return
        
        # Check if voting for self
        voted_player_id = getattr(self.player, "discord_id", None)
        if voted_player_id == voter_id:
            await interaction.response.send_message(
                "You cannot vote for yourself as MVP.",
                ephemeral=True
            )
            return
        
        # Check if already voted
        if voter_id in game_state.mvp_votes.get(self.game_index, {}):
            old_vote = game_state.mvp_votes[self.game_index][voter_id]
            old_vote_name = "Unknown"
            
            # Find the name of the player they previously voted for
            for team in ["blue", "red"]:
                for player in game_state.games[self.game_index][team]:
                    if getattr(player, "discord_id", None) == old_vote:
                        old_vote_name = getattr(player, "username", "Unknown")
                        break
            
            await interaction.response.send_message(
                f"You have already voted for {old_vote_name}. Your vote cannot be changed.",
                ephemeral=True
            )
            return
        
        # Record the vote
        game_state.mvp_votes[self.game_index][voter_id] = voted_player_id
        
        # Update the admin MVP message
        await game_state.update_mvp_admin_embed(self.game_index)
        
        await interaction.response.send_message(
            f"You voted for {getattr(self.player, 'username', 'Unknown')} as MVP.",
            ephemeral=True
        )


# ===== Game Selection Dropdown =====

class GameSelectForMVP(discord.ui.Select):
    """Dropdown to select which game to start MVP voting for."""
    def __init__(self):
        """Initialize game select dropdown."""
        options = [
            discord.SelectOption(label=f"Game {i+1}", value=str(i))
            for i in range(10)  # Limit to 10 games for now
        ]
        super().__init__(
            placeholder="Select a game to start MVP voting",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        """
        Handle game selection for MVP voting.
        
        Args:
            interaction: Discord interaction
        """
        game_index = int(self.values[0])
        game_state = GlobalGameState.get_instance()
        
        # Check if the game exists
        if game_index >= len(game_state.games):
            await interaction.response.send_message(
                f"Game {game_index + 1} does not exist.",
                ephemeral=True
            )
            return
        
        # Check if there's a result for the game
        game_data = game_state.games[game_index]
        if not game_data.get("result"):
            await interaction.response.send_message(
                f"Cannot start MVP voting for Game {game_index + 1} until a winner is declared.",
                ephemeral=True
            )
            return
        
        # Check if MVP voting is already active
        if game_state.mvp_voting_active.get(game_index, False):
            await interaction.response.send_message(
                f"MVP voting is already active for Game {game_index + 1}.",
                ephemeral=True
            )
            return
        
        # Start MVP voting
        await game_state.start_mvp_voting(interaction, game_index)


# ===== Game Progression Controls =====

class ConfirmNextGameView(discord.ui.View):
    """View for confirming skipping to the next game."""
    def __init__(self, global_state):
        """
        Initialize confirm next game view.
        
        Args:
            global_state: Global game state instance
        """
        super().__init__(timeout=60)  # Auto-timeout after 60 seconds
        self.global_state = global_state

    @discord.ui.button(label="Yes, Skip Voting", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Handle confirmation to skip MVP voting and proceed to next game.
        
        Args:
            interaction: Discord interaction
            button: Confirmation button
        """
        # Disable all buttons
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        
        # Only admins can confirm
        if not helpers.has_admin_permission(interaction.user):
            embed = discord.Embed(
                title="Permission Error",
                description="Only administrators can confirm skipping MVP voting.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Mark all MVP voting as NULL (no MVP awarded)
        for i in range(len(self.global_state.games)):
            if self.global_state.game_results.get(i) and not self.global_state.games[i].get("mvp"):
                self.global_state.games[i]["mvp"] = None
            
            # Cancel any active MVP voting
            if self.global_state.mvp_voting_active.get(i, False):
                await self.global_state.cancel_mvp_voting(interaction, i, silent=True)
        
        # Create the next game setup embed
        next_game_embed = discord.Embed(
            title="Next Game Setup",
            description="Skipping MVP voting and proceeding to next game setup...",
            color=discord.Color.blue()
        )
        await interaction.response.send_message(embed=next_game_embed, ephemeral=True)
        
        # Update the global control view to show the Next Game button
        key = "global_control"
        if key in self.global_state.message_references:
            message = self.global_state.message_references[key]
            global_view = GlobalControlView(self.global_state)
            global_embed = discord.Embed(
                title="Global Game Controls",
                description="All games complete. You can now proceed to the next game.",
                color=discord.Color.blue()
            )
            await message.edit(embed=global_embed, view=global_view)
        
        await self.global_state.fade_all_game_controls()


class GlobalControlView(discord.ui.View):
    """Simplified global controls that only handle game progression."""
    def __init__(self, global_state=None):
        """
        Initialize global control view.
        
        Args:
            global_state: Global game state instance
        """
        super().__init__(timeout=None)
        self.global_state = global_state or GlobalGameState.get_instance()
        
        # Only add the Next Game button if all games have results and MVPs resolved
        all_games_complete = True
        
        # Helper functions for checking game status
        def has_result(game_index):
            return self.global_state.game_results.get(game_index) is not None
        
        def is_mvp_resolved(game_index):
            return (
                self.global_state.games[game_index].get("mvp") is not None or
                not self.global_state.mvp_voting_active.get(game_index, False)
            )
        
        # Check if we should show the next game button
        for i in range(len(self.global_state.games)):
            if not has_result(i) or not is_mvp_resolved(i):
                all_games_complete = False
                break
        
        # Only add the Next Game button if all games are complete
        if not all_games_complete:
            # Remove the Next Game button by clearing all items
            self.clear_items()

    async def fade_all_game_controls(self):
        """Disable all existing game control views."""
        # Disable all game control views
        for i in range(len(self.global_state.games)):
            key = f"game_control_{i}"
            if key in self.global_state.message_references:
                message = self.global_state.message_references[key]
                try:
                    if message.components:  # Only update if there are components
                        for component in message.components:
                            for child in component.children:
                                child.disabled = True
                        await message.edit(view=None)
                except Exception as e:
                    print(f"Error disabling game controls: {e}")
        
        # Disable global controls
        for key in ["global_control", "swap_control"]:
            if key in self.global_state.message_references:
                message = self.global_state.message_references[key]
                try:
                    await message.edit(view=None)
                except Exception as e:
                    print(f"Error disabling global controls: {e}")

    @discord.ui.button(label="Next Game / Re-Check-In", style=discord.ButtonStyle.primary)
    async def next_game_callback(self, interaction: discord.Interaction):
        """
        Proceed to next game setup with auto re-check-in.
        
        Args:
            interaction: Discord interaction
        """
        # Only admins can proceed to next game
        if not helpers.has_admin_permission(interaction.user):
            embed = discord.Embed(
                title="Permission Error",
                description="Only administrators can proceed to next game setup.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Helper functions for checking game status
        def has_result(game_index):
            return self.global_state.game_results.get(game_index) is not None
        
        def is_mvp_resolved(game_index):
            return (
                self.global_state.games[game_index].get("mvp") is not None or
                not self.global_state.mvp_voting_active.get(game_index, False)
            )
        
        # Check if all games have results
        all_games_have_results = all(has_result(i) for i in range(len(self.global_state.games)))
        
        # Check if all games have MVP resolved (either voted, skipped, or not active)
        all_mvp_resolved = all(is_mvp_resolved(i) for i in range(len(self.global_state.games)))
        
        if not all_games_have_results:
            embed = discord.Embed(
                title="Cannot Proceed",
                description="Cannot proceed to next game until all current games have a declared winner.",
                color=discord.Color.red()
            )
            
            # List games without results
            incomplete_games = []
            for i in range(len(self.global_state.games)):
                if not has_result(i):
                    incomplete_games.append(f"Game {i+1}")
            
            if incomplete_games:
                embed.add_field(
                    name="Games Needing Results",
                    value="\n".join(incomplete_games),
                    inline=False
                )
            
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )
            return
        
        if not all_mvp_resolved:
            # Ask for confirmation to skip MVP voting
            confirm_embed = discord.Embed(
                title="Skip MVP Voting?",
                description=(
                    "Some games still have active MVP voting or no MVP declared. "
                    "Would you like to skip MVP voting for these games?"
                ),
                color=discord.Color.gold()
            )
            
            # List games with pending MVP votes
            pending_mvp_games = []
            for i in range(len(self.global_state.games)):
                if not is_mvp_resolved(i):
                    pending_mvp_games.append(f"Game {i+1}")
            
            if pending_mvp_games:
                confirm_embed.add_field(
                    name="Games With Pending MVP Votes",
                    value="\n".join(pending_mvp_games),
                    inline=False
                )
            
            confirm_view = ConfirmNextGameView(self.global_state)
            await interaction.response.send_message(
                embed=confirm_embed,
                view=confirm_view,
                ephemeral=True
            )
            return
        
        # If all games have results and MVP voting is resolved, proceed
        await interaction.response.defer(ephemeral=True)
        
        # Create a new check-in with the same players who were already playing
        all_players = []
        for game in self.global_state.games:
            all_players.extend(game["blue"])
            all_players.extend(game["red"])
        
        if self.global_state.sitting_out:
            all_players.extend(self.global_state.sitting_out)
        
        # Get Discord members corresponding to these players
        member_map = {}
        for player in all_players:
            discord_id = getattr(player, "discord_id", None)
            if discord_id and discord_id not in member_map:
                member = interaction.guild.get_member(int(discord_id))
                if member:
                    member_map[discord_id] = member
                else:
                    # Create a dummy member for testing
                    member_map[discord_id] = DummyMember(int(discord_id))
        
        unique_members = list(member_map.values())
        
        # Create a new check-in view
        from Scripts.TournamentBot.ui.check_in import StartGameView
        new_view = StartGameView(interaction.user.id)
        
        # Auto check-in everyone
        for member in unique_members:
            new_view.checked_in_users.append(member)
        
        # Create the check-in embed
        embed = discord.Embed(
            title="Next Game Check-in",
            description="Auto-checked in all previous players. Click Start Game when ready!",
            color=discord.Color.blue()
        )
        
        user_list = []
        for i, user in enumerate(new_view.checked_in_users):
            user_list.append(f"{i+1}. {user.mention}")
        
        if user_list:
            embed.add_field(
                name=f"Checked-in Players ({len(new_view.checked_in_users)})",
                value="\n".join(user_list),
                inline=False
            )
        
        # Disable this view to prevent multiple re-check-ins
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        
        # Disable all other game controls
        await self.fade_all_game_controls()
        
        # Send the new check-in message
        channel = self.global_state.public_channel
        if channel:
            await channel.send(embed=embed, view=new_view)
        # Use an embed for the followup message instead of raw text
        success_embed = discord.Embed(
            title="New Check-In Created",
            description="Successfully created a new check-in with all previous players auto-checked in.",
            color=discord.Color.green()
        )
        success_embed.add_field(
            name="Next Steps",
            value="Players are ready to be assigned to new teams. Click the Start Game button when ready!",
            inline=False
        )
        
        await interaction.followup.send(
            embed=success_embed,
            ephemeral=True
        )


class GlobalSwapControlView(discord.ui.View):
    """View for global team balancing controls."""
    def __init__(self, global_state=None):
        """
        Initialize global swap control view.
        
        Args:
            global_state: Global game state instance
        """
        super().__init__(timeout=None)
        self.global_state = global_state or GlobalGameState.get_instance()

    @discord.ui.button(label="Swap", style=discord.ButtonStyle.secondary, row=0)
    async def swap_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Toggle player swapping mode.
        
        Args:
            interaction: Discord interaction
            button: Swap button
        """
        # Only admins can toggle swap mode
        if not helpers.has_admin_permission(interaction.user):
            embed = discord.Embed(
                title="Permission Error",
                description="Only administrators can toggle swap mode.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Toggle swap mode in the game state
        await self.global_state.toggle_swap_mode(interaction)
        
        # Toggle button style based on swap mode
        if self.global_state.swap_mode:
            button.style = discord.ButtonStyle.primary
            button.label = "Swap (Active)"
            
            # Update all game controls to show player buttons
            for i in range(len(self.global_state.games)):
                key = f"game_control_{i}"
                if key in self.global_state.message_references:
                    message = self.global_state.message_references[key]
                    game_data = self.global_state.games[i]
                    new_view = GameControlView(self.global_state, i, show_players=True)
                    embed = self.global_state.generate_embed(i)
                    await message.edit(embed=embed, view=new_view)
        else:
            button.style = discord.ButtonStyle.secondary
            button.label = "Swap"
            
            # Update all game controls to hide player buttons
            for i in range(len(self.global_state.games)):
                key = f"game_control_{i}"
                if key in self.global_state.message_references:
                    message = self.global_state.message_references[key]
                    game_data = self.global_state.games[i]
                    new_view = GameControlView(self.global_state, i, show_players=False)
                    embed = self.global_state.generate_embed(i)
                    await message.edit(embed=embed, view=new_view)
        
        # Update the swap control view
        await interaction.message.edit(view=self)

    @discord.ui.button(label="Finalize Games", style=discord.ButtonStyle.blurple, row=0)
    async def finalize_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """
        Finalize games after team swapping.
        
        Args:
            interaction: Discord interaction
            button: Finalize button
        """
        # Only admins can finalize games
        if not helpers.has_admin_permission(interaction.user):
            embed = discord.Embed(
                title="Permission Error",
                description="Only administrators can finalize games.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Turn off swap mode
        self.global_state.swap_mode = False
        self.global_state.selected_player1 = None
        self.global_state.selected_player2 = None
        
        # Create embedded announcement for the public channel
        channel = self.global_state.public_channel
        if channel:
            # Send a proper embed announcement instead of raw text
            finalize_embed = discord.Embed(
                title="🎮 Teams Finalized",
                description="All teams have been finalized. Games will begin shortly.",
                color=discord.Color.green()
            )
            await channel.send(embed=finalize_embed)
            
            # Send game embeds
            for i in range(len(self.global_state.games)):
                embed = self.global_state.generate_embed(i)
                await channel.send(embed=embed)
        
        # Update all game controls to show winner selection buttons but no player buttons
        for i in range(len(self.global_state.games)):
            key = f"game_control_{i}"
            if key in self.global_state.message_references:
                message = self.global_state.message_references[key]
                new_view = GameControlView(self.global_state, i, show_players=False)
                embed = self.global_state.generate_embed(i)
                await message.edit(embed=embed, view=new_view)
        
        # Hide the swap control message rather than disabling it
        # This matches the original implementation's UI flow
        if "swap_control" in self.global_state.message_references:
            message = self.global_state.message_references["swap_control"]
            # Create an embed noting the view is inactive
            embed = discord.Embed(
                title="Team Balancing Complete",
                description="Games have been finalized. Please use the winner selection buttons to record game results.",
                color=discord.Color.blue()
            )
            await message.edit(embed=embed, view=None)
        
        # Create success feedback as an embed
        success_embed = discord.Embed(
            title="Games Finalized",
            description="Games have been finalized and teams announced.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=success_embed, ephemeral=True)


# Import at the bottom to avoid circular imports
from Scripts.TournamentBot.ui.check_in import DummyMember