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


# Helper function to check for duplicate players
def is_duplicate_player(checked_in_users, user_id):
    """Check if a user is already in the checked-in list."""
    for user in checked_in_users:
        if str(getattr(user, 'id', user.id)) == str(user_id):
            return True
    return False


# ===== Sitting Out Players UI =====

class SittingOutButton(discord.ui.Button):
    """Button representing a player who is sitting out."""
    def __init__(self, player_name: str, index: int):
        super().__init__(label=player_name, style=discord.ButtonStyle.secondary)
        self.player_index = index

    async def callback(self, interaction: discord.Interaction):
        global_game_state = GlobalGameState.get_instance()
        await global_game_state.handle_selection(interaction, None, "sitting_out", self.player_index, self.label)


class SittingOutView(discord.ui.View):
    """View for displaying sitting out players."""
    def __init__(self, global_state: GlobalGameState):
        super().__init__(timeout=None)
        self.global_state = global_state
        
        # Add buttons for each sitting out player
        if self.global_state.sitting_out:
            for i, player in enumerate(self.global_state.sitting_out):
                button = SittingOutButton(player.username, i)
                self.add_item(button)


# ===== Game Player Buttons =====

class GamePlayerButton(discord.ui.Button):
    """Button representing a player in a game."""
    def __init__(self, game_index: int, team: str, player_index: int, player_name: str):
        style = discord.ButtonStyle.primary if team.lower() == "blue" else discord.ButtonStyle.danger
        super().__init__(label=player_name, style=style)
        self.game_index = game_index
        self.team = team
        self.player_index = player_index

    async def callback(self, interaction: discord.Interaction):
        global_game_state = GlobalGameState.get_instance()
        await global_game_state.handle_selection(
            interaction, 
            self.game_index, 
            self.team, 
            self.player_index, 
            self.label
        )


# ===== MVP Voting Controls =====

class EndMVPVoteButton(discord.ui.Button):
    """Button to end MVP voting for a game."""
    def __init__(self, game_index: int):
        super().__init__(label="End MVP Vote", style=discord.ButtonStyle.success)
        self.game_index = game_index
    
    async def callback(self, interaction: discord.Interaction):
        game_state = GlobalGameState.get_instance()
        
        if not game_state.mvp_voting_active.get(self.game_index, False):
            await interaction.response.send_message(
                f"No active MVP voting for Game {self.game_index+1}!",
                ephemeral=True
            )
            return
        
        try:
            await game_state.end_mvp_voting(interaction, self.game_index)
            
            # Update game message with final results
            game_message = game_state.game_messages.get(self.game_index)
            if game_message:
                # Remove all MVP control buttons after voting ends
                embed = game_message.embeds[0]
                await game_message.edit(embed=embed, view=None)
        except discord.errors.InteractionResponded:
            # If interaction already responded, just let the end_mvp_voting handle it
            pass


class CancelMVPVoteButton(discord.ui.Button):
    """Button to cancel MVP voting for a game."""
    def __init__(self, game_index: int):
        super().__init__(label="Cancel MVP Vote", style=discord.ButtonStyle.danger)
        self.game_index = game_index
    
    async def callback(self, interaction: discord.Interaction):
        game_state = GlobalGameState.get_instance()
        
        if not game_state.mvp_voting_active.get(self.game_index, False):
            await interaction.response.send_message(
                f"No active MVP voting for Game {self.game_index+1}!",
                ephemeral=True
            )
            return
        
        try:
            await game_state.cancel_mvp_voting(interaction, self.game_index)
            
            # Update game message with cancelled status
            game_message = game_state.game_messages.get(self.game_index)
            if game_message:
                # Remove all MVP control buttons after voting is cancelled
                embed = game_message.embeds[0]
                await game_message.edit(embed=embed, view=None)
        except discord.errors.InteractionResponded:
            # If interaction already responded, just let the cancel_mvp_voting handle it
            pass


class SkipMVPButton(discord.ui.Button):
    """Button to skip MVP voting for a game."""
    def __init__(self, game_index: int):
        super().__init__(label="Skip MVP Vote", style=discord.ButtonStyle.secondary, custom_id=f"skip_mvp_{game_index}")
        self.game_index = game_index
    
    async def callback(self, interaction: discord.Interaction):
        game_state = GlobalGameState.get_instance()
        
        # Check if MVP voting is already active or completed
        if game_state.mvp_voting_active.get(self.game_index, False):
            await interaction.response.send_message(
                f"MVP voting for Game {self.game_index+1} is already in progress. Please end or cancel it first.",
                ephemeral=True
            )
            return
            
        # Mark this game as not needing MVP voting
        if self.game_index not in game_state.mvp_voting_active:
            game_state.mvp_voting_active[self.game_index] = False
        
        # Get the game result and update the database
        result = game_state.game_results.get(self.game_index, None)
        if result:
            # Store match data in database with NULL MVP
            await databaseManager.store_match_data(game_state.games[self.game_index], result, None)
            
            # Update all player statistics
            await databaseManager.update_all_player_stats(game_state.games[self.game_index], result, None)
        else:
            print(f"Error: No game result found for game {self.game_index}")
        
        # Remove the MVP buttons but keep the game result
        game_message = game_state.game_messages.get(self.game_index)
        if game_message:
            # Keep the existing embed which contains the Result field
            embed = game_message.embeds[0]
            # Create an empty view - this creates clean UI with no buttons
            empty_view = discord.ui.View()
            await game_message.edit(embed=embed, view=empty_view)
        
        await interaction.response.send_message(
            f"MVP voting for Game {self.game_index+1} has been skipped. Match data has been saved.",
            ephemeral=True
        )


class GameMVPControlView(discord.ui.View):
    """View for controlling MVP voting for a specific game."""
    def __init__(self, game_index: int, is_voting_active: bool = False):
        super().__init__(timeout=None)
        self.game_index = game_index
        
        if not is_voting_active:
            # If voting is not active, show the Start Vote and Skip buttons
            self.add_item(MVPVoteButton(game_index))
            self.add_item(SkipMVPButton(game_index))
        else:
            # If voting is active, show End and Cancel buttons
            self.add_item(EndMVPVoteButton(game_index))
            self.add_item(CancelMVPVoteButton(game_index))


# ===== Game Result and MVP Buttons =====

class MVPVoteButton(discord.ui.Button):
    """Button to start MVP voting for a game after winner is declared."""
    def __init__(self, game_index: int, blue_team=None, red_team=None):
        super().__init__(label="Vote for MVP", style=discord.ButtonStyle.secondary)
        self.game_index = game_index
        # Store teams for backward compatibility
        self.blue_team = blue_team
        self.red_team = red_team
    
    async def callback(self, interaction: discord.Interaction):
        game_state = GlobalGameState.get_instance()
        
        # Check if voting is already active for this game
        if game_state.mvp_voting_active.get(self.game_index, False):
            await interaction.response.send_message(
                f"MVP voting for Game {self.game_index+1} is already active!",
                ephemeral=True
            )
            return
        
        # Get the blue and red teams from the game state
        game = game_state.games[self.game_index]
        blue_team = game["blue"]
        red_team = game["red"]
            
        # Start MVP voting
        await game_state.start_mvp_voting(interaction, self.game_index)
        
        # Update this game's message with new controls while preserving result
        game_message = game_state.game_messages.get(self.game_index)
        if game_message:
            # Get the existing embed which may contain the result
            embed = game_message.embeds[0]
            # Update with End/Cancel buttons
            mvp_control_view = GameMVPControlView(self.game_index, True)
            await game_message.edit(embed=embed, view=mvp_control_view)
        
        # Just defer the interaction - no confirmation message needed
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.InteractionResponded):
            # Interaction may have timed out or already been responded to
            pass


class BlueWinButton(discord.ui.Button):
    """Button to declare Blue team as the winner."""
    def __init__(self, game_index: int, blue_team: list, red_team: list):
        super().__init__(label="Blue Team Win", style=discord.ButtonStyle.primary)
        self.game_index = game_index
        self.blue_team = blue_team
        self.red_team = red_team

    async def callback(self, interaction: discord.Interaction):
        game_state = GlobalGameState.get_instance()
        
        embed = interaction.message.embeds[0]
        embed.add_field(name="Result", value="🟦 Blue Team Wins!", inline=False)
        
        # Store the game result for later database update
        game_state.game_results[self.game_index] = "blue"
        game_state.games[self.game_index]["result"] = "blue"
            
        # Create a new view with MVP controls directly under this game
        mvp_control_view = GameMVPControlView(self.game_index, False)
        
        # Update the message with the new view while preserving the result
        await interaction.message.edit(embed=embed, view=mvp_control_view)
        # Store the message reference for future updates
        game_state.game_messages[self.game_index] = interaction.message
        game_state.message_references[f"game_control_{self.game_index}"] = interaction.message
        game_state.game_messages[self.game_index] = interaction.message
        
        # Update database with win data
        try:
            # Update winner stats
            winners = self.blue_team
            await databaseManager.update_wins(winners)
            
            # Update loser stats (only games played since winners get that in update_wins)
            for player in self.red_team:
                await databaseManager.update_games_played(player.discord_id)
        except Exception as e:
            print(f"Error updating database: {e}")
        
        # Just defer instead of sending a confirmation message
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.InteractionResponded):
            # Interaction may have timed out or already been responded to
            pass


class RedWinButton(discord.ui.Button):
    """Button to declare Red team as the winner."""
    def __init__(self, game_index: int, blue_team: list, red_team: list):
        super().__init__(label="Red Team Win", style=discord.ButtonStyle.danger)
        self.game_index = game_index
        self.blue_team = blue_team
        self.red_team = red_team

    async def callback(self, interaction: discord.Interaction):
        game_state = GlobalGameState.get_instance()
        
        embed = interaction.message.embeds[0]
        embed.add_field(name="Result", value="🟥 Red Team Wins!", inline=False)
        
        # Store the game result for later database update
        game_state.game_results[self.game_index] = "red"
        game_state.games[self.game_index]["result"] = "red"
            
        # Create a new view with MVP controls directly under this game
        mvp_control_view = GameMVPControlView(self.game_index, False)
        
        # Update the message with the new view while preserving the result
        await interaction.message.edit(embed=embed, view=mvp_control_view)
        # Store the message reference for future updates
        game_state.game_messages[self.game_index] = interaction.message
        game_state.message_references[f"game_control_{self.game_index}"] = interaction.message
        game_state.game_messages[self.game_index] = interaction.message
        
        # Update database with win data
        try:
            # Update winner stats
            winners = self.red_team
            await databaseManager.update_wins(winners)
            
            # Update loser stats (only games played since winners get that in update_wins)
            for player in self.blue_team:
                await databaseManager.update_games_played(player.discord_id)
        except Exception as e:
            print(f"Error updating database: {e}")
        
        # Just defer instead of sending a confirmation message
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.InteractionResponded):
            # Interaction may have timed out or already been responded to
            pass


class GameControlView(discord.ui.View):
    """View for controlling a specific game."""
    def __init__(self, global_state: GlobalGameState, game_index: int):
        super().__init__(timeout=None)
        self.global_state = global_state
        self.game_index = game_index
        
        # Add player buttons for swap mode
        if not self.global_state.finalized and self.global_state.swap_mode:
            blue_team = self.global_state.games[game_index]["blue"]
            for i, player in enumerate(blue_team):
                button = GamePlayerButton(game_index, "blue", i, player.username)
                button.row = 0
                self.add_item(button)
            
            red_team = self.global_state.games[game_index]["red"]
            for i, player in enumerate(red_team):
                button = GamePlayerButton(game_index, "red", i, player.username)
                button.row = 1
                self.add_item(button)
        
        # Add win declaration buttons when games are finalized
        if self.global_state.finalized:
            blue_team = self.global_state.games[self.game_index]["blue"]
            red_team = self.global_state.games[self.game_index]["red"]
            
            # Only add buttons if no result is recorded yet
            if not self.global_state.games[self.game_index].get("result"):
                blue_win = BlueWinButton(self.game_index, blue_team, red_team)
                blue_win.row = 2
                self.add_item(blue_win)
                
                red_win = RedWinButton(self.game_index, blue_team, red_team)
                red_win.row = 2
                self.add_item(red_win)

class MVPVotingView(discord.ui.View):
    """View for players to cast their MVP votes."""
    def __init__(self, global_state, game_index, players, winning_team):
        super().__init__(timeout=None)
        self.global_state = global_state
        self.game_index = game_index
        self.winning_team = winning_team  # Either "blue" or "red"
        
        # Add a button for each player on the winning team
        for i, player in enumerate(players):
            # Determine row placement (5 buttons per row)
            row = i // 5
            # Set button style based on winning team
            is_blue_team = (winning_team == "blue")
            self.add_item(PlayerMVPButton(game_index, player, is_blue_team, row, winning_team))


class PlayerMVPButton(discord.ui.Button):
    """Button for voting for a specific player as MVP."""
    def __init__(self, game_index, player, is_blue_team, row=0, winning_team=None):
        # Set button style based on winning team
        button_style = discord.ButtonStyle.primary if is_blue_team else discord.ButtonStyle.danger
        
        super().__init__(
            label=player.username,
            style=button_style,  # Apply team color
            row=row
        )
        self.game_index = game_index
        self.player = player
        self.winning_team = winning_team
    
    async def callback(self, interaction: discord.Interaction):
        game_state = GlobalGameState.get_instance()
        
        # Verify voter is on the winning team
        voter_id = str(interaction.user.id)
        game = game_state.games[self.game_index]
        winning_team_players = game[self.winning_team]
        
        voter_on_winning_team = False
        for player in winning_team_players:
            if player.discord_id == voter_id:
                voter_on_winning_team = True
                break
        
        if not voter_on_winning_team:
            await interaction.response.send_message(
                f"Only members of the winning {self.winning_team.capitalize()} team can vote for MVP.",
                ephemeral=True
            )
            return
        
        # Prevent voting for self
        if self.player.discord_id == voter_id:
            await interaction.response.send_message(
                "You cannot vote for yourself!",
                ephemeral=True
            )
            return
        
        # Register vote
        if self.game_index not in game_state.mvp_votes:
            game_state.mvp_votes[self.game_index] = {}
        
        # Check if already voted
        if voter_id in game_state.mvp_votes[self.game_index]:
            previous_vote = game_state.mvp_votes[self.game_index][voter_id]
            previous_player = None
            for p in winning_team_players:
                if p.discord_id == previous_vote:
                    previous_player = p
                    break
            
            await interaction.response.send_message(
                f"You've changed your vote from {previous_player.username if previous_player else 'someone else'} to {self.player.username}.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"You've voted for {self.player.username} as MVP!",
                ephemeral=True
            )
        
        # Store the vote
        game_state.mvp_votes[self.game_index][voter_id] = self.player.discord_id
        # Admin tracking functionality removed


class ConfirmNextGameView(discord.ui.View):
    """Confirmation view for skipping active MVP voting."""
    def __init__(self, global_control_view):
        super().__init__(timeout=None)
        self.global_control_view = global_control_view
    
    @discord.ui.button(label="Yes, Skip Voting", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        game_state = GlobalGameState.get_instance()
        
        # Cancel all active MVP votes in any game
        for game_index, is_active in list(game_state.mvp_voting_active.items()):
            if is_active:
                await game_state.cancel_mvp_voting(
                    interaction,
                    game_index,
                    silent=True
                )
        
        # Fade out all game controls
        await self.global_control_view.fade_all_game_controls()
        
        # Fade out the buttons on the global controls message
        if game_state.global_controls_message:
            gc_embed = discord.Embed(
                title="Global Controls (Preparing New Game)",
                description="MVP voting has been skipped. Preparing for the next game.",
                color=discord.Color.dark_gold()
            )
            # Disable all buttons to create a fade effect
            disabled_view = GlobalControlView()
            for child in disabled_view.children:
                child.disabled = True
            await game_state.global_controls_message.edit(embed=gc_embed, view=disabled_view)
        
        await interaction.response.send_message(
            "Preparing for the next game. Use /checkin to start a new check-in session.",
            ephemeral=True
        )
        
        # Delete the confirmation message
        await interaction.message.delete()
    
    @discord.ui.button(label="No, Keep Voting", style=discord.ButtonStyle.secondary)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Continuing with MVP voting.", ephemeral=True)
        await interaction.message.delete()


class GlobalPhasedControlView:
    """Factory for creating the appropriate phase view for global controls."""
    @staticmethod
    def create_phase1_view(game_state=None):
        """Create the Phase 1 view (Start Game / Cancel Game)."""
        return GlobalPhase1View(game_state)
    
    @staticmethod
    def create_phase2_view(game_state=None):
        """Create the Phase 2 view (Swap / Finalize Games)."""
        return GlobalPhase2View(game_state)
    
    @staticmethod
    def create_phase3_view(game_state=None):
        """Create the Phase 3 view (Next Game / Cancel Games)."""
        return GlobalPhase3View(game_state)

class GlobalPhase1View(discord.ui.View):
    """Phase 1 global controls (Start Game / Cancel Game)."""
    def __init__(self, global_state=None):
        super().__init__(timeout=None)
        self.global_state = global_state or GlobalGameState.get_instance()
        
        # Add the Start Game button
        start_game_button = discord.ui.Button(
            label="Start Game",
            style=discord.ButtonStyle.success,
            row=0
        )
        start_game_button.callback = self.start_game_callback
        self.add_item(start_game_button)
        
        # Add the Cancel Game button
        cancel_game_button = discord.ui.Button(
            label="Cancel Game",
            style=discord.ButtonStyle.danger,
            row=0
        )
        cancel_game_button.callback = self.cancel_game_callback
        self.add_item(cancel_game_button)
    
    async def start_game_callback(self, interaction: discord.Interaction):
        """Create the games and transition to Phase 2 (Swap and Finalize Games)."""
        # Import needed modules
        import Scripts.TournamentBot.main as main_module
        import Matchmaking
        import random
        from ..game.game_state import GlobalGameState
        
        await interaction.response.defer(ephemeral=True)
        
        # Check if there's an active check-in
        if not main_module.current_checkin_view:
            # Try direct import as a fallback
            import Scripts.TournamentBot.main as main_module_direct
            if main_module_direct.current_checkin_view:
                # Use the direct reference instead
                print(f"Found check-in view via direct import: {id(main_module_direct.current_checkin_view)}")
                main_module.current_checkin_view = main_module_direct.current_checkin_view
            else:
                print(f"ERROR: No active check-in session found. current_checkin_view is None")
                print(f"Module loaded as: {main_module.__name__}")
                await interaction.followup.send(
                    "Error: No active check-in session found. Please create a new check-in first.",
                    ephemeral=True
                )
                return
            
        # If we get here, we have an active check-in
        print(f"Found active check-in: {id(main_module.current_checkin_view)}")
            
        # Get the current checkin view
        view = main_module.current_checkin_view
        
        # Build a list of Player objects from the check-in list
        players = []
        for user in view.checked_in_users:
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
        # Disable the check-in buttons using the new method
        await view.disable_all_buttons(reason="This check-in has been closed. Games are being created.")

        # Get list of volunteers who are playing (they have player objects)
        volunteer_players = []
        for volunteer in view.volunteers:
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
        
        # Reset the game state singleton to avoid conflicts
        GlobalGameState.reset_instance()
        
        # Get a new game state instance
        game_state = GlobalGameState.get_instance()
        
        # Initialize the game state with teams and sitting-out players
        public_channel = None
        for guild in interaction.client.guilds:
            for channel in guild.channels:
                if hasattr(view, 'channel') and view.channel and channel.id == view.channel.id:
                    public_channel = channel
                    break
        
        await game_state.initialize_games(games, cut_players, public_channel)
        game_state.admin_channel = interaction.channel
        
        # Create game control messages for each game
        from ..ui.game_control import GameControlView
        
        # Clear any existing messages
        game_state.message_references = {}
        game_state.game_messages = {}
        
        # Send game control messages to admin channel
        for i in range(len(games)):
            embed = game_state.generate_embed(i)
            view = GameControlView(game_state, i)
            message = await interaction.channel.send(embed=embed, view=view)
            game_state.message_references[f"game_control_{i}"] = message
            game_state.game_messages[i] = message
        
        # Send sitting out message
        if cut_players:
            from ..ui.game_control import SittingOutView
            
            embed = game_state.generate_sitting_out_embed()
            # Only create view if swap mode is enabled and games aren't finalized
            if game_state.swap_mode and not game_state.finalized:
                view = SittingOutView(game_state)
                message = await interaction.channel.send(embed=embed, view=view)
            else:
                # Initially send with no buttons since swap mode is disabled by default
                message = await interaction.channel.send(embed=embed)
            
            game_state.message_references["sitting_out"] = message
            game_state.sitting_out_message = message
        
        # Create Phase 2 view (Swap / Finalize Games)
        phase2_view = GlobalPhasedControlView.create_phase2_view(game_state)
        
        # Update the embed with Phase 2 info
        gc_embed = discord.Embed(
            title="Global Controls (Team Balancing)",
            description="Use swap mode to balance teams, then finalize to start the games",
            color=discord.Color.blue()
        )
        
        # Update the message with the new view
        await interaction.message.edit(embed=gc_embed, view=phase2_view)
        
        # Store message reference for global controls
        game_state.message_references["global_control"] = interaction.message
        game_state.global_controls_message = interaction.message
        
        await interaction.followup.send(
            "Games have been created! You can now use Swap to adjust teams and then Finalize Games when ready.",
            ephemeral=True
        )
    
    async def cancel_game_callback(self, interaction: discord.Interaction):
        """Cancel the current game session."""
        # Import needed module
        import Scripts.TournamentBot.main as main_module
        
        # Reset the game state
        GlobalGameState.reset_instance()
        
        # Disable buttons in check-in view if it exists
        if main_module.current_checkin_view:
            view = main_module.current_checkin_view
            
            # Disable the check-in buttons using the new method
            await view.disable_all_buttons(reason="The check-in has been cancelled by the administrator.")
            
            # Reset the global check-in view
            main_module.current_checkin_view = None
        
        # Create empty embed to show the game was cancelled
        gc_embed = discord.Embed(
            title="Global Controls (Game Cancelled)",
            description="The game session has been cancelled.",
            color=discord.Color.dark_red()
        )
        
        # Create empty view
        empty_view = discord.ui.View()
        
        # Update the message
        await interaction.message.edit(embed=gc_embed, view=empty_view)
        
        await interaction.response.send_message(
            "Game session cancelled. You can use /checkin to start a new session.",
            ephemeral=True
        )

class GlobalPhase2View(discord.ui.View):
    """Phase 2 global controls (Swap / Finalize Games)."""
    def __init__(self, global_state=None):
        super().__init__(timeout=None)
        self.global_state = global_state or GlobalGameState.get_instance()
    
    @discord.ui.button(label="Swap", style=discord.ButtonStyle.secondary, row=0)
    async def swap_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle swap mode for player rearrangement."""
        if self.global_state is None:
            await interaction.response.send_message("No game in progress.", ephemeral=True)
            return
        
        await self.global_state.toggle_swap_mode(interaction)
        button.label = "Stop Swapping" if self.global_state.swap_mode else "Swap"
        await interaction.message.edit(view=self)
    
    @discord.ui.button(label="Finalize Games", style=discord.ButtonStyle.primary, row=0)
    async def finalize_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Finalize games and enable win declaration."""
        self.global_state.finalized = True
        
        # Update participation points for sitting-out players
        if self.global_state.sitting_out:
            sit_out_log = ["Updating participation for sitting-out players:"]
            for player in self.global_state.sitting_out:
                try:
                    # Award participation points to sitting-out player
                    result = await databaseManager.update_points(player.discord_id)
                    sit_out_log.append(result)
                except Exception as e:
                    error_msg = f"Error updating points for {player.username} ({player.discord_id}): {str(e)}"
                    sit_out_log.append(error_msg)
                    print(error_msg)  # Log error for debugging
            
            # Print results for server-side logging
            print("\n".join(sit_out_log))
                    # Send individual game embeds to the public channel
        
        # Update all game messages with win buttons
        await self.global_state.update_all_messages()

        # Send Finalized Games to the public channel
        if self.global_state.public_channel:
            for i in range(len(self.global_state.games)):
                embed = self.global_state.generate_embed(i)
                await self.global_state.public_channel.send(embed=embed)
        else:
            print("Warning: public_channel is None, cannot send game embeds to public channel")

        # Transition to Phase 3 (Next Game / Cancel Games)
        gc_embed = discord.Embed(
            title="Global Controls (Game Results)",
            description="Games have been finalized. Select winners for each game, conduct MVP voting, then use Next Game when finished.",
            color=discord.Color.gold()
        )
        
        # Create Phase 3 view
        phase3_view = GlobalPhasedControlView.create_phase3_view(self.global_state)
        
        # Update the message with the new view
        await interaction.message.edit(embed=gc_embed, view=phase3_view)
        
        # Just defer instead of sending a confirmation message
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.InteractionResponded):
            # Interaction may have timed out or already been responded to
            pass

class GlobalPhase3View(discord.ui.View):
    """Phase 3 global controls (Next Game / Cancel Games)."""
    def __init__(self, global_state=None):
        super().__init__(timeout=None)
        self.global_state = global_state or GlobalGameState.get_instance()
        
        # Add the Next Game button
        next_game_button = discord.ui.Button(
            label="Next Game",
            style=discord.ButtonStyle.success,
            row=0
        )
        next_game_button.callback = self.next_game_callback
        self.add_item(next_game_button)
        
        # Add the Cancel Games button
        cancel_games_button = discord.ui.Button(
            label="End/Cancel Games",
            style=discord.ButtonStyle.danger,
            row=0
        )
        cancel_games_button.callback = self.cancel_games_callback
        self.add_item(cancel_games_button)
    
    async def fade_all_game_controls(self):
        """Disable all interactive buttons in game messages to create a fade effect."""
        game_state = GlobalGameState.get_instance()
        
        # Create empty views to replace the functional ones
        for i in range(len(game_state.games)):
            key = f"game_control_{i}"
            if key in game_state.message_references:
                message = game_state.message_references[key]
                try:
                    # Create a completely empty view instead of using game control buttons
                    empty_view = discord.ui.View()
                    
                    # Update the message with no functional buttons
                    await message.edit(view=empty_view)
                except Exception as e:
                    print(f"Failed to disable controls for Game {i+1}: {e}")
        
        # Disable sitting out controls if they exist
        if game_state.sitting_out_message:
            try:
                # Create a disabled sitting out view
                if game_state.swap_mode:
                    disabled_view = SittingOutView(game_state)
                    for child in disabled_view.children:
                        child.disabled = True
                    await game_state.sitting_out_message.edit(view=disabled_view)
                    
            except Exception as e:
                print(f"Failed to disable sitting out controls: {e}")
                
        # MVP admin message controls removed as part of simplification
    
    async def next_game_callback(self, interaction: discord.Interaction):
        """Proceed to next game setup with auto re-check-in."""
        game_state = GlobalGameState.get_instance()
        
        # Debug print to see the current state
        print(f"Next Game clicked - Games: {len(game_state.games)}, Messages: {len(game_state.game_messages)}")
        
        # First acknowledge the interaction to avoid timeout errors
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception as e:
            print(f"Error deferring interaction: {e}")
        
        # Define helper functions to check game state correctly
        def has_result(game_index):
            """Check if a game has a winner declared."""
            # Check both message_references and game_messages for backward compatibility
            game_message = None
            key = f"game_control_{game_index}"
            if key in game_state.message_references:
                game_message = game_state.message_references[key]
            elif game_index in game_state.game_messages:
                game_message = game_state.game_messages[game_index]
                
            if not game_message:
                return False
                
            return any(field.name == "Result" for field in game_message.embeds[0].fields)
            
        def is_mvp_resolved(game_index):
            """Check if MVP voting has been resolved (either completed or skipped)."""
            if game_index not in game_state.mvp_voting_active:
                return False  # Not addressed at all
                
            return game_state.mvp_voting_active[game_index] == False  # Explicitly completed or skipped
        
        # Get list of games that have messages
        games_with_messages = [idx for idx in range(len(game_state.games))
                              if f"game_control_{idx}" in game_state.message_references or idx in game_state.game_messages]
        
        if not games_with_messages:
            await interaction.followup.send(
                "No games found to process. Please restart the tournament.",
                ephemeral=True
            )
            return
            
        # STEP 1: Check if all games have a winner declared
        games_without_result = [idx for idx in games_with_messages if not has_result(idx)]
        
        if games_without_result:
            game_numbers = ", ".join([f"Game {i+1}" for i in games_without_result])
            await interaction.followup.send(
                f"No victor has been decided for {game_numbers}. Cannot proceed to the next game.",
                ephemeral=True
            )
            print(f"Next Game blocked: Games {games_without_result} missing results")
            return
        
        # STEP 2: Check if all games with results have MVP voting addressed
        games_with_pending_mvp = [idx for idx in games_with_messages
                                 if has_result(idx) and not is_mvp_resolved(idx)]
        
        if games_with_pending_mvp:
            game_numbers = ", ".join([f"Game {i+1}" for i in games_with_pending_mvp])
            await interaction.followup.send(
                f"MVP Vote needs to be concluded with an MVP or needs to be explicitly skipped for {game_numbers}.",
                ephemeral=True
            )
            print(f"Next Game blocked: Games {games_with_pending_mvp} have pending MVP voting")
            return
        
        # All conditions met, proceed with next game
        
        # Update the global controls to show processing state
        gc_embed = discord.Embed(
            title="Global Controls (Processing...)",
            description="Starting new game session...",
            color=discord.Color.dark_gold()
        )
        
        # Create disabled view
        disabled_view = GlobalPhase3View(self.global_state)
        for child in disabled_view.children:
            child.disabled = True
        
        # Edit the message immediately to show processing state
        try:
            await interaction.message.edit(embed=gc_embed, view=disabled_view)
        except Exception as e:
            print(f"Error updating global controls: {e}")
            
        # Disable all other game controls
        await self.fade_all_game_controls()
        
        # Create a new check-in session
        previous_players = []
        try:
            if game_state and game_state.public_channel:
                # Get all unique players from all games
                for game in game_state.games:
                    previous_players.extend(game["blue"])
                    previous_players.extend(game["red"])
                
                # Add sitting out players
                if game_state.sitting_out:
                    previous_players.extend(game_state.sitting_out)
                
                # Get the public channel for re-check-in
                public_channel = game_state.public_channel
                
                # Store this before resetting
                stored_public_channel = public_channel
                
                # Reset the game state for a new session
                GlobalGameState.reset_instance()
                
                # Import needed modules
                import Scripts.TournamentBot.main as main_module
                from ..ui.check_in import StartGameView
                
                # Create a new check-in session with the previous players
                if stored_public_channel:
                    # Create the check-in embed
                    embed = discord.Embed(
                        title="Game Check-in (Auto Re-Check-in)",
                        description="New game session started! All players from the previous session have been automatically checked in.",
                        color=discord.Color.blue()
                    )
                    
                    # Create the check-in view
                    # Create a check-in view with duplicate player checks enabled
                    view = StartGameView(interaction.user.id)
                    # Add a flag to tell the view it was auto-created
                    view.auto_recheckin = True
                    
                    # Store channel reference for future use
                    view.channel = stored_public_channel
                    
                    # Debug print
                    print(f"Creating new check-in with {len(previous_players)} players in channel {stored_public_channel.id}")
                    
                    # Add all previous players to the checked-in list by retrieving them from the database
                    discord_users = []
                    for player in previous_players:
                        # Only add each player once (by discord_id)
                        discord_id = player.discord_id
                        if any(getattr(du, 'id', du.id) == discord_id for du in discord_users):
                            continue
                        
                        # Get the player info directly from the database using the proper function
                        # This ensures we have the most current information for each player
                        import databaseManager
                        db_player = await databaseManager.get_player_info(discord_id)
                        
                        if db_player:
                            # Create a Discord dummy member with database information
                            from ..ui.check_in import DummyMember
                            dummy = DummyMember(discord_id)
                            dummy.username = db_player.username
                            discord_users.append(dummy)
                            print(f"Successfully retrieved player {db_player.username} (ID: {discord_id}) from database")
                        else:
                            # Fallback if player not found in database (shouldn't happen)
                            print(f"Warning: Player with ID {discord_id} not found in database, using original info")
                            from ..ui.check_in import DummyMember
                            dummy = DummyMember(discord_id)
                            dummy.username = player.username
                            discord_users.append(dummy)
                    
                    # Set the checked in users
                    view.checked_in_users = discord_users
                    print(f"Added {len(discord_users)} users to the new check-in view")
                    
                    # Update the embed with player list
                    user_list = []
                    for i, user in enumerate(view.checked_in_users):
                        user_list.append(f"{i+1}. {getattr(user, 'mention', f'<@{user.id}>')}")
                    
                    if user_list:
                        embed.add_field(
                            name=f"Checked-in Players ({len(view.checked_in_users)})",
                            value="\n".join(user_list[:25]) + (f"\n...and {len(user_list) - 25} more" if len(user_list) > 25 else ""),
                            inline=False
                        )
                    
                    embed.set_footer(text="A minimum of 10 players is required to start a game")
                    
                    try:
                        # Send the check-in message to the original channel
                        message = await stored_public_channel.send(embed=embed, view=view)
                        view.message_id = message.id
                        
                        # Debug print
                        print(f"Created new check-in message with ID: {message.id}")
                        
                        # Make sure to set the view in the global state BEFORE creating the control view
                        import sys
                        import Scripts.TournamentBot.main as main_module_direct
                        main_module_direct.current_checkin_view = view
                        print(f"Set current_checkin_view in main module direct reference: {id(view)}")
                        print(f"Main module path: {sys.modules['Scripts.TournamentBot.main'].__file__}")
                        print(f"Current checkin view is now: {main_module_direct.current_checkin_view is not None}")
                        
                        # Also set it the regular way to be extra safe
                        main_module.current_checkin_view = view
                        
                        # Wait a moment to ensure the variable is properly set
                        await asyncio.sleep(0.5)
                        
                        # Create and send Phase 1 Global Controls to the admin channel
                        from ..ui.game_control import GlobalPhasedControlView
                        
                        # Create Phase 1 view (Start Game / Cancel Game)
                        phase1_view = GlobalPhasedControlView.create_phase1_view()
                        print(f"After phase1_view creation, current_checkin_view is: {main_module_direct.current_checkin_view is not None}")
                        
                        # Create embed for global controls
                        gc_embed = discord.Embed(
                            title="Global Controls (Game Setup)",
                            description="Click 'Start Game' to begin the game session or 'Cancel Game' to cancel.",
                            color=discord.Color.blue()
                        )
                        
                        # Send global controls message to admin channel
                        admin_channel_id = os.getenv("ADMIN_CHANNEL")
                        if admin_channel_id:
                            admin_channel = interaction.client.get_channel(int(admin_channel_id))
                            if admin_channel:
                                admin_message = await admin_channel.send(
                                    embed=gc_embed,
                                    view=phase1_view
                                )
                                print(f"Sent new global controls to admin channel: {admin_channel.id}, message ID: {admin_message.id}")
                                print(f"Current check-in view after sending controls: {main_module.current_checkin_view is not None}")
                                print(f"Sent new global controls to admin channel: {admin_channel.id}")
                        
                        await interaction.followup.send(
                            f"Game session completed! A new check-in has been automatically created with {len(view.checked_in_users)} players.",
                            ephemeral=True
                        )
                    except Exception as e:
                        print(f"Error creating new check-in: {e}")
                        main_module.current_checkin_view = None
                        await interaction.followup.send(
                            f"Error creating new check-in: {str(e)}",
                            ephemeral=True
                        )
                else:
                    # If we can't find the public channel, just reset everything
                    main_module.current_checkin_view = None
                    await interaction.followup.send(
                        "Game session completed. Use /checkin to start a new session (couldn't find public channel).",
                        ephemeral=True
                    )
        except Exception as e:
            # Error handling for the entire process
            print(f"Error in next_game_callback: {e}")
            # Reset to avoid blocking the system
            GlobalGameState.reset_instance()
            import Scripts.TournamentBot.main as main_module
            main_module.current_checkin_view = None
            
            await interaction.followup.send(
                f"An error occurred: {str(e)}. Game state has been reset.",
                ephemeral=True
            )
        # Remove the else clause that was resetting current_checkin_view to None
        # We don't want to clear it if we've already set up a new check-in session
        
        # Fade out the buttons
        gc_embed = discord.Embed(
            title="Global Controls (Game Complete)",
            description="The game session has ended. A new check-in has been created.",
            color=discord.Color.dark_gold()
        )
        
        # Create empty view
        empty_view = discord.ui.View()
        
        # Edit the message
        await interaction.message.edit(embed=gc_embed, view=empty_view)
    
    async def cancel_games_callback(self, interaction: discord.Interaction):
        """Cancelelled Games. Will No Longer Re-Check In"""
        # Get current game state
        game_state = self.global_state
        
        # Disable all game-related buttons in all game messages
        for game_index, message in game_state.game_messages.items():
            if message:
                try:
                    # Keep the embed but remove all buttons
                    embed = message.embeds[0] if message.embeds else None
                    if embed:
                        await message.edit(embed=embed, view=None)
                except Exception as e:
                    print(f"Error disabling buttons for game {game_index+1}: {e}")
        
        # Reset the game state
        GlobalGameState.reset_instance()
        
        # Clear the current check-in view to allow new check-ins
        import Scripts.TournamentBot.main as main_module
        main_module.current_checkin_view = None
        
        # Create empty embed to show the games were cancelled
        gc_embed = discord.Embed(
            title="Global Controls (Games Cancelled)",
            description="All games have been cancelled",
            color=discord.Color.dark_red()
        )
        
        # Create empty view
        empty_view = discord.ui.View()
        
        # Update the message
        await interaction.message.edit(embed=gc_embed, view=empty_view)
        
        await interaction.response.send_message(
            "All games have been cancelled. Use /checkin to start a new session.",
            ephemeral=True
        )

# Maintain backwards compatibility
class GlobalControlView(GlobalPhase3View):
    """Legacy class for backwards compatibility."""
    pass

class GlobalSwapControlView(GlobalPhase2View):
    """Legacy class for backwards compatibility."""
    pass