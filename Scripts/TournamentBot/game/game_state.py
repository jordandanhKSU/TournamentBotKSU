"""
Game state management for the TournamentBot.

This module provides classes for managing game state, including game creation,
team assignment, MVP voting, and result tracking.
"""
import discord
import asyncio
import random
from typing import List, Dict, Any, Optional, Tuple, Union, Set, Callable
import sys
import os

# First add the parent directory (TournamentBot) to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Then add the Scripts directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import from local package using relative paths
from ..utils import helpers

# Import from parent directory
import databaseManager
import Matchmaking

class GlobalGameState:
    """
    Manages the global state of all games in the tournament.
    
    This class is implemented as a singleton to ensure only one instance exists.
    It handles game creation, team management, MVP voting, and results tracking.
    """
    _instance = None
    
    @classmethod
    def get_instance(cls) -> 'GlobalGameState':
        """
        Get or create the singleton instance of the GlobalGameState.
        
        Returns:
            The GlobalGameState instance
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls) -> None:
        """
        Reset the singleton instance.
        Useful for testing or when a fresh state is needed.
        """
        cls._instance = None
    
    def __init__(self, games: list = None, sitting_out: list = None, public_channel=None):
        """Initialize a new GlobalGameState."""
        # Core game data
        self.games = games if games is not None else []
        self.sitting_out = sitting_out if sitting_out is not None else []
        self.public_channel = public_channel
        self.admin_channel = None
        
        # UI message references
        self.message_references = {}
        self.game_messages = {}
        self.sitting_out_message = None  # Message for sitting out players
        self.global_controls_message = None  # Store the global controls message
        
        # Game and voting status
        self.game_results = {}  # Maps game index to "blue" or "red"
        self.mvp_voting_active = {}  # Maps game index to voting status
        self.mvp_votes = {}  # Maps game index to {voter_id: voted_for_id}
        self.mvp_vote_messages = {}  # {game_index: message}
        self.mvp_admin_messages = {}  # {game_index: message}
        self.current_voting_game = None  # Currently active voting game index
        
        # State flags
        self.swap_mode = False
        self.finalized = False
        self.selected = None  # Tuple of (game_index, team, player_index, player_name)
        
        # Auto-end voting timers
        self.mvp_voting_timers = {}
    
    def is_initialized(self) -> bool:
        """Check if the game state has been initialized with games."""
        return len(self.games) > 0
    
    async def initialize_games(self, games: List[Dict[str, Any]], sitting_out: List[Any], public_channel: discord.TextChannel) -> None:
        """
        Initialize the games state with pre-created teams.
        
        Args:
            games: List of game dictionaries with 'blue' and 'red' teams
            sitting_out: List of players sitting out
            public_channel: Channel to post public updates
        """
        self.games = games
        self.sitting_out = sitting_out if sitting_out is not None else []
        self.public_channel = public_channel
        
        # Reset message references
        self.message_references = {}
        self.game_messages = {}
        self.sitting_out_message = None
        self.mvp_admin_messages = {}
        self.mvp_vote_messages = {}
        self.message_references = {}
        self.game_messages = {}
        self.sitting_out_message = None
        self.global_controls_message = None
        self.game_results = {}
        self.mvp_voting_active = {}
        self.mvp_votes = {}
        self.mvp_vote_messages = {}
        self.mvp_admin_messages = {}
        self.swap_mode = False
        self.finalized = False
        self.selected = None
        self.current_voting_game = None
        
        # Store the games directly since matchmaking was already done
        self.games = games
        
        # Initialize voting state for each game
        for i in range(len(games)):
            self.mvp_voting_active[i] = False
            self.mvp_votes[i] = {}
    
    def _format_team_data(self, players: list) -> tuple:
        """
        Format data for exactly 5 players.
        
        Returns a tuple of three newline-delimited strings:
        - col1: Emoji, bolded primary role and username.
        - col2: Combined Tier and Rank (with bolded labels) in the format:
                **Tier**: {tier} | **Rank**: {rank}
        - col3: Role Preference list with each role preceded by its emoji and the role bolded.
        """
        primary_roles = helpers.ROLE_NAMES  # ["Top", "Jun", "Mid", "Bot", "Sup"]
        col1_lines = []
        col2_lines = []
        col3_lines = []
        
        for i, player in enumerate(players):
            primary_role = primary_roles[i]
            emoji = helpers.ROLE_EMOJIS.get(primary_role, "")
            col1_lines.append(f"{emoji} **{primary_role}**: {player.username}")
            
            # Combined tier and rank column.
            col2_lines.append(f"**Tier**: {player.tier} | **Rank**: {player.rank}")
            
            # Format role preferences with each role's emoji and bold the role.
            role_prefs = player.get_priority_role_preference()
            if role_prefs:
                formatted_prefs = ", ".join(
                    f"{helpers.ROLE_EMOJIS.get(role, '')} **{role}**" for role in role_prefs
                )
            else:
                formatted_prefs = "None"
            col3_lines.append(formatted_prefs)
            
        return (
            "\n".join(col1_lines),
            "\n".join(col2_lines),
            "\n".join(col3_lines)
        )

    def generate_embed(self, game_index: int) -> discord.Embed:
        """
        Generate an embed for a specific game that takes up more horizontal space.
        
        For each team (Blue and Red) there will be 3 inline fields arranged as:
        1. Field: [Team] Primary Role (with emoji) & Username.
        2. Field: Combined Tier and Rank.
        3. Field: Role Preference (each role bolded with its emoji).
        """
        if game_index >= len(self.games):
            return discord.Embed(
                title="Error", 
                description="Game not found",
                color=discord.Color.red()
            )
        
        game = self.games[game_index]
        embed = discord.Embed(title=f"Game {game_index+1}", color=discord.Color.blue())
        
        # Blue Team fields
        blue_col1, blue_col2, blue_col3 = self._format_team_data(game["blue"])
        embed.add_field(name="Blue Team", value=blue_col1, inline=True)
        embed.add_field(name="Tier and Rank", value=blue_col2, inline=True)
        embed.add_field(name="Role Preference", value=blue_col3, inline=True)
        
        # Red Team fields
        red_col1, red_col2, red_col3 = self._format_team_data(game["red"])
        embed.add_field(name="Red Team", value=red_col1, inline=True)
        embed.add_field(name="Tier and Rank", value=red_col2, inline=True)
        embed.add_field(name="Role Preference", value=red_col3, inline=True)
        
        # If the game has a result, add it to the embed.
        if game.get("result"):
            result_text = f"{game['result'].capitalize()} Team Wins!"
            embed.add_field(name="Result", value=result_text, inline=False)
        
        return embed
    
    def generate_sitting_out_embed(self) -> discord.Embed:
        """Generate an embed for players sitting out."""
        embed = discord.Embed(title="Sitting Out", color=discord.Color.dark_gray())
        if self.sitting_out:
            sitting_out_str = "\n".join(player.username for player in self.sitting_out)
        else:
            sitting_out_str = "None"
        embed.add_field(name="Players Sitting Out", value=sitting_out_str, inline=False)
        return embed
    
    async def update_all_messages(self):
        """Update all game embeds and sitting out embed."""
        # Update game control messages
        for i in range(len(self.games)):
            key = f"game_control_{i}"
            if key in self.message_references:
                message = self.message_references[key]
                embed = self.generate_embed(i)
                
                # Import here to avoid circular imports
                from ..ui.game_control import GameControlView
                view = GameControlView(self, i)
                
                try:
                    await message.edit(embed=embed, view=view)
                except Exception as e:
                    print(f"Failed to update message for Game {i+1}: {e}")
        
        # Update sitting out message
        if "sitting_out" in self.message_references:
            message = self.message_references["sitting_out"]
            sitting_out_embed = self.generate_sitting_out_embed()
            try:
                # Import here to avoid circular imports
                from ..ui.game_control import SittingOutView
                
                # Create a new view for sitting out players if swap mode is enabled and games aren't finalized
                if self.swap_mode and not self.finalized:
                    view = SittingOutView(self)
                    await message.edit(embed=sitting_out_embed, view=view)
                else:
                    # Remove buttons when swap mode is off or games are finalized
                    await message.edit(embed=sitting_out_embed, view=None)
            except Exception as e:
                print(f"Failed to update sitting out message: {e}")
                
        # Admin tracking functionality removed
    
    async def start_mvp_voting(self, interaction: discord.Interaction, game_index: int):
        """Start MVP voting for a specific game."""
        # Verify game exists and isn't already voting
        if game_index >= len(self.games):
            await interaction.response.send_message(
                f"Invalid game index: {game_index}",
                ephemeral=True
            )
            return
        
        if self.mvp_voting_active.get(game_index, False):
            await interaction.response.send_message(
                f"MVP voting for Game {game_index+1} is already active!",
                ephemeral=True
            )
            return
        
        # Mark this game as actively voting
        self.mvp_voting_active[game_index] = True
        self.current_voting_game = game_index
        self.mvp_votes[game_index] = {}
        
        # Get game players and winning team
        game = self.games[game_index]
        result = self.game_results.get(game_index)
        
        if not result:
            await interaction.response.send_message(
                f"Error: No result found for Game {game_index+1}. Please declare a winner first.",
                ephemeral=True
            )
            return
        
        # Get only winning team players for MVP voting
        winning_players = game[result]  # Either "blue" or "red" team players
        
        # Create voting embed for players
        voting_embed = discord.Embed(
            title=f"MVP Voting - Game {game_index+1}",
            description=f"Vote for the Most Valuable Player from the winning {result.capitalize()} team!\nOnly {result.capitalize()} team members can vote, and you cannot vote for yourself.",
            color=discord.Color.gold() if result == "blue" else discord.Color.red()
        )
        
        # Generate player mentions for winning team only
        player_mentions = " ".join([f"<@{player.discord_id}>" for player in winning_players])
        
        # Get the public channel where check-in happened
        public_channel = self.public_channel
        if not public_channel:
            await interaction.response.send_message(
                "Error: Could not find the public channel for voting. Please restart the game.",
                ephemeral=True
            )
            return
        
        # Send voting embed to the public channel
        try:
            # Import here to avoid circular imports
            from ..ui.game_control import MVPVotingView
            
            # Create MVP voting view with only winning team players
            voting_view = MVPVotingView(self, game_index, winning_players, result)
            voting_msg = await public_channel.send(
                embed=voting_embed,
                view=voting_view
            )
            # Mention winning team players in a separate message that can be deleted later
            mention_msg = await public_channel.send(f"🏆 **Game {game_index+1} MVP Voting:** {player_mentions}")
            self.mvp_vote_messages[game_index] = voting_msg
        except Exception as e:
            print(f"Error sending voting message to public channel: {e}")
            await interaction.response.send_message(
                f"Error sending voting message: {str(e)}",
                ephemeral=True
            )
            return
        # Admin tracking functionality removed to simplify MVP voting
        # Reference removed as part of admin functionality simplification
        
        # No confirmation message needed - just defer
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.InteractionResponded):
            # Interaction may have timed out or already been responded to
            pass

    async def end_mvp_voting(self, interaction: discord.Interaction, game_index: int):
        """End MVP voting and tally results."""
        if not self.mvp_voting_active.get(game_index, False):
            await interaction.response.send_message(
                f"No active MVP voting for Game {game_index+1}!",
                ephemeral=True
            )
            return
        
        # Get the winning team
        result = self.game_results.get(game_index)
        if not result:
            await interaction.response.send_message(
                f"Error: No result found for Game {game_index+1}.",
                ephemeral=True
            )
            return
            
        # Tally votes
        votes = self.mvp_votes.get(game_index, {})
        vote_counts = {}
        
        for voted_id in votes.values():
            vote_counts[voted_id] = vote_counts.get(voted_id, 0) + 1
        
        # Find player with most votes
        mvp_id = None
        max_votes = 0
        
        for player_id, count in vote_counts.items():
            if count > max_votes:
                max_votes = count
                mvp_id = player_id
        
        # Handle ties by random selection
        tied_players = [pid for pid, count in vote_counts.items() if count == max_votes]
        if len(tied_players) > 1:
            mvp_id = random.choice(tied_players)
        
        # Get the game data - only consider winning team players for MVP
        game = self.games[game_index]
        winning_players = game[result]
        
        # Find the MVP player object
        mvp_player = None
        for player in winning_players:
            if player.discord_id == mvp_id:
                mvp_player = player
                break
        
        # Handle results display
        if mvp_player and max_votes > 0:
            # Store match data in database
            await databaseManager.store_match_data(self.games[game_index], result, mvp_id)
            
            # Update all player statistics in one call
            await databaseManager.update_all_player_stats(self.games[game_index], result, mvp_id)
            
            # Nothing here - we moved the results_embed creation below
            
            # Get winning team color
            winner_color = discord.Color.blue() if result == "blue" else discord.Color.red()
            
            # Add voting breakdown
            vote_breakdown = ""
            for player in winning_players:  # Only show winning team players
                votes = vote_counts.get(player.discord_id, 0)
                vote_breakdown += f"{player.username}: {votes} vote{'s' if votes != 1 else ''}\n"
            
            # Update embed with winning team color
            results_embed = discord.Embed(
                title=f"MVP Results - Game {game_index+1}",
                description=f"🏆 **{mvp_player.username}** has been voted MVP with {max_votes} votes!",
                color=winner_color
            )
            
            results_embed.add_field(
                name="Voting Breakdown",
                value=vote_breakdown,
                inline=False
            )
            
            # Update the voting message
            voting_msg = self.mvp_vote_messages.get(game_index)
            if voting_msg:
                await voting_msg.edit(
                    embed=results_embed,
                    view=None
                )
            
            # Admin message update functionality removed
            
            # No confirmation message needed - just defer
            try:
                await interaction.response.defer()
            except (discord.errors.NotFound, discord.errors.InteractionResponded):
                # Interaction may have timed out or already been responded to
                pass
        else:
            # No votes or tie case
            no_votes_embed = discord.Embed(
                title=f"MVP Voting Ended - Game {game_index+1}",
                description="No MVP was selected as there were no votes or there was a tie.",
                color=discord.Color.dark_gray()
            )
            
            voting_msg = self.mvp_vote_messages.get(game_index)
            if voting_msg:
                await voting_msg.edit(
                    embed=no_votes_embed,
                    view=None
                )
            
            # No confirmation message needed - just defer
            try:
                await interaction.response.defer()
            except (discord.errors.NotFound, discord.errors.InteractionResponded):
                # Interaction may have timed out or already been responded to
                pass
        
        # Clean up voting state
        self.mvp_voting_active[game_index] = False
        self.current_voting_game = None

    async def cancel_mvp_voting(self, interaction: discord.Interaction, game_index: int, silent=False):
        """Cancel MVP voting without tallying results."""
        if not self.mvp_voting_active.get(game_index, False):
            if not silent:
                await interaction.response.send_message(
                    f"No active MVP voting for Game {game_index+1}!",
                    ephemeral=True
                )
            return
        
        # Get the game result and update the database
        result = self.game_results.get(game_index, None)
        if result:
            # Since MVP voting was canceled, we treat it like skipping MVP
            # Store match data in database with NULL MVP
            await databaseManager.store_match_data(self.games[game_index], result, None)
            
            # Update all player statistics
            await databaseManager.update_all_player_stats(self.games[game_index], result, None)
        else:
            print(f"Error: No game result found for game {game_index}")
        
        # Create cancellation embed
        cancel_embed = discord.Embed(
            title=f"MVP Voting Cancelled - Game {game_index+1}",
            description="The administrator has cancelled MVP voting for this game.",
            color=discord.Color.dark_gray()
        )
        
        # Update the voting message
        voting_msg = self.mvp_vote_messages.get(game_index)
        if voting_msg:
            await voting_msg.edit(
                embed=cancel_embed,
                view=None
            )
        
        # Admin message update functionality removed
        
        # Clean up voting state
        self.mvp_voting_active[game_index] = False
        self.current_voting_game = None
        
        if not silent:
            # No confirmation message needed - just defer
            try:
                await interaction.response.defer()
            except (discord.errors.NotFound, discord.errors.InteractionResponded):
                # Interaction may have timed out or already been responded to
                pass

    # Method removed as part of simplifying MVP voting functionality
    
    async def auto_end_mvp_voting(self, game_index, admin_channel):
        """Automatically end MVP voting when everyone has voted."""
        try:
            # Wait a brief moment to allow for any race conditions
            await asyncio.sleep(1)
            
            # Create a simplified fake interaction for the end_mvp_voting method
            class FakeInteraction:
                def __init__(self, channel):
                    self.channel = channel
                    self.client = channel.guild.me._state._get_client()
                
                async def response_send_message(self, content, ephemeral=False):
                    pass  # No messages needed
            
            fake_interaction = FakeInteraction(self.public_channel)
            fake_interaction.response = fake_interaction
            
            # End the voting
            await self.end_mvp_voting(fake_interaction, game_index)
            
        except Exception as e:
            print(f"Error in auto_end_mvp_voting: {e}")

    async def handle_selection(self, interaction: discord.Interaction, game_index: int, team: str, player_index: int, player_name: str):
        """Handle player selection for swapping."""
        if self.selected is None:
            self.selected = (game_index, team, player_index, player_name)
            await interaction.response.send_message(
                f"Selected **{player_name}** from " +
                (f"Game {game_index+1} ({team.capitalize()} Team)." if team != "sitting_out" else "Sitting Out.") +
                " Now select another player to swap.",
                ephemeral=True,
            )
        else:
            first_game_index, first_team, first_player_index, first_player_name = self.selected
            if first_team == team and first_game_index == game_index:
                if team == "sitting_out":
                    temp = self.sitting_out[first_player_index]
                    self.sitting_out[first_player_index] = self.sitting_out[player_index]
                    self.sitting_out[player_index] = temp
                else:
                    temp = self.games[first_game_index][first_team][first_player_index]
                    self.games[first_game_index][first_team][first_player_index] = self.games[game_index][team][player_index]
                    self.games[game_index][team][player_index] = temp
            else:
                if first_team == "sitting_out":
                    temp = self.sitting_out[first_player_index]
                    self.sitting_out[first_player_index] = self.games[game_index][team][player_index]
                    self.games[game_index][team][player_index] = temp
                elif team == "sitting_out":
                    temp = self.games[first_game_index][first_team][first_player_index]
                    self.games[first_game_index][first_team][first_player_index] = self.sitting_out[player_index]
                    self.sitting_out[player_index] = temp
                else:
                    temp = self.games[first_game_index][first_team][first_player_index]
                    self.games[first_game_index][first_team][first_player_index] = self.games[game_index][team][player_index]
                    self.games[game_index][team][player_index] = temp

            self.selected = None
            await self.update_all_messages()
            try:
                await interaction.response.send_message("Players swapped!", ephemeral=True)
            except (discord.errors.NotFound, discord.errors.InteractionResponded):
                # Interaction may have timed out or already been responded to
                pass

    async def toggle_swap_mode(self, interaction: discord.Interaction):
        """Toggle swap mode for player manipulation."""
        self.swap_mode = not self.swap_mode
        if not self.swap_mode:
            self.selected = None
        await self.update_all_messages()
        mode_str = "enabled (names revealed)" if self.swap_mode else "disabled (names hidden)"
        await interaction.response.send_message(f"Swap mode {mode_str}.", ephemeral=True)