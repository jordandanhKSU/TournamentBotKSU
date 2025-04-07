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
    
    def __init__(self):
        """Initialize a new GlobalGameState."""
        # Core game data
        self.games: List[Dict[str, Any]] = []
        self.sitting_out: List[Any] = []
        self.public_channel: Optional[discord.TextChannel] = None
        self.admin_channel: Optional[discord.TextChannel] = None
        
        # UI message references
        self.message_references: Dict[str, discord.Message] = {}
        
        # Game and voting status
        self.game_results: Dict[int, str] = {}  # Maps game index to "blue" or "red"
        self.mvp_voting_active: Dict[int, bool] = {}  # Maps game index to voting status
        self.mvp_votes: Dict[int, Dict[str, str]] = {}  # Maps game index to {voter_id: voted_for_id}
        
        # State flags
        self.swap_mode = False
        self.selected_player1 = None
        self.selected_player2 = None
        self.game_indices = []
        
        # Auto-end voting timers
        self.mvp_voting_timers: Dict[int, asyncio.Task] = {}
    
    def is_initialized(self) -> bool:
        """Check if the game state has been initialized with games."""
        return len(self.games) > 0
    
    async def initialize_games(self, players: List[Any], sitting_out: List[Any], public_channel: discord.TextChannel) -> None:
        """
        Initialize the games from a list of players.
        
        Args:
            players: List of players to create games from
            sitting_out: List of players sitting out
            public_channel: Channel to post public updates
        """
        self.games = []
        self.sitting_out = sitting_out
        self.public_channel = public_channel
        self.message_references = {}
        self.game_results = {}
        self.mvp_voting_active = {}
        self.mvp_votes = {}
        self.swap_mode = False
        self.selected_player1 = None
        self.selected_player2 = None
        
        # Use the matchmaking algorithm to create teams
        blue_teams, red_teams = Matchmaking.matchmaking_multiple(players)
        
        # Create game entries
        for i in range(len(blue_teams)):
            self.games.append({
                "blue": blue_teams[i],
                "red": red_teams[i],
                "mvp_votes": {},
                "result": None,
                "mvp": None
            })
            self.mvp_voting_active[i] = False
            self.mvp_votes[i] = {}
    
    def generate_embed(self, game_index: int) -> discord.Embed:
        """
        Generate an embed for a specific game.
        
        Args:
            game_index: Index of the game
            
        Returns:
            Discord embed with game information
        """
        if game_index >= len(self.games):
            return discord.Embed(
                title="Error", 
                description="Game not found",
                color=discord.Color.red()
            )
        
        return helpers.create_game_embed(self.games[game_index], game_index)
    
    def generate_sitting_out_embed(self) -> discord.Embed:
        """
        Generate an embed for players who are sitting out.
        
        Returns:
            Discord embed with sitting out player information
        """
        return helpers.create_sitting_out_embed(self.sitting_out)
    
    async def update_all_messages(self) -> None:
        """Update all UI messages with current game state."""
        try:
            # Update game control messages
            for i in range(len(self.games)):
                key = f"game_control_{i}"
                if key in self.message_references:
                    message = self.message_references[key]
                    embed = self.generate_embed(i)
                    await message.edit(embed=embed)
            
            # Update sitting out message
            if "sitting_out" in self.message_references:
                message = self.message_references["sitting_out"]
                embed = self.generate_sitting_out_embed()
                await message.edit(embed=embed)
            
            # Update MVP admin messages
            for i in range(len(self.games)):
                key = f"mvp_admin_{i}"
                if key in self.message_references and self.mvp_voting_active.get(i, False):
                    await self.update_mvp_admin_embed(i)
        
        except Exception as e:
            print(f"Error updating messages: {e}")
    
    async def start_mvp_voting(self, interaction: discord.Interaction, game_index: int) -> None:
        """
        Start MVP voting for a specific game.
        
        Args:
            interaction: Discord interaction
            game_index: Index of the game
        """
        if game_index >= len(self.games):
            await helpers.safe_respond(
                interaction,
                content="Invalid game index",
                ephemeral=True
            )
            return
        
        game_data = self.games[game_index]
        if not game_data.get("result"):
            await helpers.safe_respond(
                interaction,
                content="Cannot start MVP voting until a winner is declared",
                ephemeral=True
            )
            return
        
        if self.mvp_voting_active.get(game_index, False):
            await helpers.safe_respond(
                interaction,
                content="MVP voting is already active for this game",
                ephemeral=True
            )
            return
        
        # Set up voting state
        self.mvp_voting_active[game_index] = True
        self.mvp_votes[game_index] = {}
        
        # Get the admin channel
        admin_channel_id = os.getenv("ADMIN_CHANNEL")
        if admin_channel_id:
            admin_channel = interaction.guild.get_channel(int(admin_channel_id))
        else:
            await helpers.safe_respond(
                interaction,
                content="Admin channel not set. Please run the createAdminChannel command first.",
                ephemeral=True
            )
            return
        
        # Create admin control message
        embed = discord.Embed(
            title=f"Game {game_index + 1} - MVP Voting Status",
            description="Voting in progress. Waiting for player votes...",
            color=discord.Color.gold()
        )
        
        from Scripts.TournamentBot.ui.game_control import GameMVPControlView
        admin_view = GameMVPControlView(game_index)
        admin_message = await admin_channel.send(embed=embed, view=admin_view)
        self.message_references[f"mvp_admin_{game_index}"] = admin_message
        
        # Update public message
        winner_team = game_data["result"]  # "blue" or "red"
        players = game_data["blue"] + game_data["red"]
        
        embed = discord.Embed(
            title=f"Game {game_index + 1} - MVP Voting",
            description="Vote for the Most Valuable Player!",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="How to vote",
            value="Each player gets one vote. You cannot vote for yourself.",
            inline=False
        )
        
        # Add fields for each team
        blue_field = ""
        for i, player in enumerate(game_data["blue"]):
            role_name = helpers.ROLE_NAMES[i]
            emoji = helpers.ROLE_EMOJIS.get(role_name, "")
            player_name = getattr(player, "username", "Unknown")
            blue_field += f"{emoji} **{role_name}**: {player_name}\n"
        
        red_field = ""
        for i, player in enumerate(game_data["red"]):
            role_name = helpers.ROLE_NAMES[i]
            emoji = helpers.ROLE_EMOJIS.get(role_name, "")
            player_name = getattr(player, "username", "Unknown")
            red_field += f"{emoji} **{role_name}**: {player_name}\n"
        
        embed.add_field(name="Blue Team", value=blue_field, inline=True)
        embed.add_field(name="Red Team", value=red_field, inline=True)
        
        from Scripts.TournamentBot.ui.game_control import MVPVotingView
        voting_view = MVPVotingView(self, game_index, players)
        
        # Send a new voting message
        message = await self.public_channel.send(embed=embed, view=voting_view)
        self.message_references[f"mvp_voting_{game_index}"] = message
        
        # Set up auto-end timer (5 minutes)
        self.mvp_voting_timers[game_index] = asyncio.create_task(
            self.auto_end_mvp_voting(game_index, admin_channel)
        )
        
        # Notify admin
        await helpers.safe_respond(
            interaction,
            content=f"Started MVP voting for Game {game_index + 1}",
            ephemeral=True
        )
    
    async def end_mvp_voting(self, interaction: discord.Interaction, game_index: int) -> None:
        """
        End MVP voting for a specific game and calculate results.
        
        Args:
            interaction: Discord interaction
            game_index: Index of the game
        """
        if game_index >= len(self.games):
            await helpers.safe_respond(
                interaction,
                content="Invalid game index",
                ephemeral=True
            )
            return
        
        if not self.mvp_voting_active.get(game_index, False):
            await helpers.safe_respond(
                interaction,
                content="MVP voting is not active for this game",
                ephemeral=True
            )
            return
        
        # Cancel the auto-end timer if it exists
        if game_index in self.mvp_voting_timers:
            self.mvp_voting_timers[game_index].cancel()
            del self.mvp_voting_timers[game_index]
        
        # Mark voting as inactive
        self.mvp_voting_active[game_index] = False
        
        # Get votes
        votes = self.mvp_votes.get(game_index, {})
        
        # Count votes
        vote_counts = {}
        for voter_id, voted_for in votes.items():
            vote_counts[voted_for] = vote_counts.get(voted_for, 0) + 1
        
        # Find player with most votes
        mvp_id = None
        max_votes = 0
        
        for player_id, count in vote_counts.items():
            if count > max_votes:
                max_votes = count
                mvp_id = player_id
        
        # If tie, randomly select from tied players
        tied_players = [pid for pid, count in vote_counts.items() if count == max_votes]
        if len(tied_players) > 1:
            mvp_id = random.choice(tied_players)
        
        # Update game data
        if mvp_id:
            self.games[game_index]["mvp"] = mvp_id
            
            # Find the player object for the MVP
            mvp_player = None
            game_data = self.games[game_index]
            
            for team in ["blue", "red"]:
                for player in game_data[team]:
                    if getattr(player, "discord_id", None) == mvp_id:
                        mvp_player = player
                        break
                if mvp_player:
                    break
            
            # Update database
            if mvp_player:
                try:
                    await databaseManager.add_mvp_point(mvp_id)
                    
                    # Store match data in database
                    result = game_data["result"]
                    await databaseManager.store_match_data(game_data, result, mvp_id)
                    
                    # Update player stats
                    await databaseManager.update_all_player_stats(game_data, result, mvp_id)
                except Exception as e:
                    print(f"Error updating database with MVP: {e}")
        
        # Update embeds and UI
        await self.update_all_messages()
        
        # Update MVP voting message
        key = f"mvp_voting_{game_index}"
        if key in self.message_references:
            message = self.message_references[key]
            
            # Create results embed
            embed = discord.Embed(
                title=f"Game {game_index + 1} - MVP Voting Results",
                color=discord.Color.gold()
            )
            
            # Show vote distribution
            vote_list = []
            for player_id, count in vote_counts.items():
                player_name = "Unknown"
                for team in ["blue", "red"]:
                    for player in self.games[game_index][team]:
                        if getattr(player, "discord_id", None) == player_id:
                            player_name = getattr(player, "username", "Unknown")
                            break
                
                vote_list.append(f"**{player_name}**: {count} vote(s)")
            
            vote_summary = "\n".join(vote_list) if vote_list else "No votes were cast"
            embed.add_field(name="Vote Distribution", value=vote_summary, inline=False)
            
            # Show MVP
            if mvp_id:
                mvp_name = "Unknown"
                for team in ["blue", "red"]:
                    for player in self.games[game_index][team]:
                        if getattr(player, "discord_id", None) == mvp_id:
                            mvp_name = getattr(player, "username", "Unknown")
                            break
                
                embed.add_field(name="MVP", value=f"**{mvp_name}** with {max_votes} vote(s)", inline=False)
            else:
                embed.add_field(name="MVP", value="No MVP selected (no votes)", inline=False)
            
            # Disable the voting view
            await message.edit(embed=embed, view=None)
        
        # Update admin message
        await self.update_mvp_admin_embed(game_index)
        
        # Notify admin
        await helpers.safe_respond(
            interaction,
            content=f"Ended MVP voting for Game {game_index + 1}",
            ephemeral=True
        )
    
    async def cancel_mvp_voting(self, interaction: discord.Interaction, game_index: int, silent: bool = False) -> None:
        """
        Cancel MVP voting for a specific game without determining a winner.
        
        Args:
            interaction: Discord interaction
            game_index: Index of the game
            silent: Whether to suppress user notifications
        """
        if game_index >= len(self.games):
            if not silent:
                await helpers.safe_respond(
                    interaction,
                    content="Invalid game index",
                    ephemeral=True
                )
            return
        
        if not self.mvp_voting_active.get(game_index, False):
            if not silent:
                await helpers.safe_respond(
                    interaction,
                    content="MVP voting is not active for this game",
                    ephemeral=True
                )
            return
        
        # Cancel the auto-end timer if it exists
        if game_index in self.mvp_voting_timers:
            self.mvp_voting_timers[game_index].cancel()
            del self.mvp_voting_timers[game_index]
        
        # Mark voting as inactive
        self.mvp_voting_active[game_index] = False
        
        # Clear votes
        self.mvp_votes[game_index] = {}
        
        # Update MVP voting message
        key = f"mvp_voting_{game_index}"
        if key in self.message_references:
            message = self.message_references[key]
            
            # Create cancellation embed
            embed = discord.Embed(
                title=f"Game {game_index + 1} - MVP Voting Cancelled",
                description="MVP voting has been cancelled by an administrator.",
                color=discord.Color.red()
            )
            
            # Disable the voting view
            await message.edit(embed=embed, view=None)
        
        # Update admin message
        await self.update_mvp_admin_embed(game_index)
        
        # Notify admin
        if not silent:
            await helpers.safe_respond(
                interaction,
                content=f"Cancelled MVP voting for Game {game_index + 1}",
                ephemeral=True
            )
    
    async def update_mvp_admin_embed(self, game_index: int) -> None:
        """
        Update the MVP admin control embed.
        
        Args:
            game_index: Index of the game
        """
        key = f"mvp_admin_{game_index}"
        if key not in self.message_references:
            return
        
        message = self.message_references[key]
        
        # Get game data
        game_data = self.games[game_index]
        votes = self.mvp_votes.get(game_index, {})
        
        # Create embed based on voting status
        if self.mvp_voting_active.get(game_index, False):
            embed = discord.Embed(
                title=f"Game {game_index + 1} - MVP Voting Status",
                description="Voting in progress",
                color=discord.Color.gold()
            )
            
            # Show current vote count
            voted_players = set(votes.values())
            total_players = len(game_data["blue"]) + len(game_data["red"])
            embed.add_field(
                name="Vote Count",
                value=f"{len(votes)}/{total_players} players have voted",
                inline=False
            )
            
            # Show who has voted
            voted_ids = list(votes.keys())
            voted_names = []
            
            for team in ["blue", "red"]:
                for player in game_data[team]:
                    player_id = getattr(player, "discord_id", None)
                    player_name = getattr(player, "username", "Unknown")
                    
                    if player_id in voted_ids:
                        voted_names.append(f"✅ {player_name}")
                    else:
                        voted_names.append(f"❌ {player_name}")
            
            embed.add_field(
                name="Player Voting Status",
                value="\n".join(voted_names) or "No players",
                inline=False
            )
            
            # If everyone voted, add button to end voting
            if len(votes) == total_players:
                embed.add_field(
                    name="All votes in!",
                    value="All players have voted. You can end the voting now.",
                    inline=False
                )
        else:
            # Voting is not active
            mvp_id = game_data.get("mvp", None)
            
            if mvp_id:
                embed = discord.Embed(
                    title=f"Game {game_index + 1} - MVP Voting Complete",
                    description="Voting has ended",
                    color=discord.Color.green()
                )
                
                # Find MVP name
                mvp_name = "Unknown"
                for team in ["blue", "red"]:
                    for player in game_data[team]:
                        if getattr(player, "discord_id", None) == mvp_id:
                            mvp_name = getattr(player, "username", "Unknown")
                            break
                
                embed.add_field(name="MVP", value=mvp_name, inline=False)
            else:
                embed = discord.Embed(
                    title=f"Game {game_index + 1} - MVP Voting Cancelled",
                    description="Voting was cancelled or no MVP was selected",
                    color=discord.Color.red()
                )
        
        # Update the message
        from Scripts.TournamentBot.ui.game_control import GameMVPControlView
        admin_view = GameMVPControlView(game_index, self.mvp_voting_active.get(game_index, False))
        await message.edit(embed=embed, view=admin_view)
    
    async def auto_end_mvp_voting(self, game_index: int, admin_channel: discord.TextChannel) -> None:
        """
        Automatically end MVP voting after a timeout period.
        
        Args:
            game_index: Index of the game
            admin_channel: Admin channel for notifications
        """
        # Wait for 5 minutes
        try:
            await asyncio.sleep(300)  # 5 minutes
            
            # Check if voting is still active
            if self.mvp_voting_active.get(game_index, False):
                # Create a fake interaction for end_mvp_voting
                class FakeInteraction:
                    def __init__(self):
                        self.response = FakeResponse()
                    
                    async def followup(self):
                        return None
                
                class FakeResponse:
                    def __init__(self):
                        pass
                    
                    def is_done(self):
                        return True
                    
                    async def send_message(self, *args, **kwargs):
                        pass
                
                fake_interaction = FakeInteraction()
                
                # End the voting
                await self.end_mvp_voting(fake_interaction, game_index)
                
                # Notify admin channel
                await admin_channel.send(
                    f"⏰ MVP voting for Game {game_index + 1} has ended automatically due to timeout."
                )
        except asyncio.CancelledError:
            # Task was cancelled, no need to do anything
            pass
        except Exception as e:
            print(f"Error in auto_end_mvp_voting: {e}")
    
    async def handle_selection(
        self, interaction: discord.Interaction, game_index: int, team: str, player_index: int, player_name: str
    ) -> None:
        """
        Handle player selection for team swapping.
        
        Args:
            interaction: Discord interaction
            game_index: Index of the game
            team: Team name ("blue" or "red")
            player_index: Index of the player in the team
            player_name: Name of the player (for display)
        """
        if not self.swap_mode:
            await helpers.safe_respond(
                interaction,
                content="Player swapping is not active. Use the Swap button to enable swapping mode.",
                ephemeral=True
            )
            return
        
        if game_index >= len(self.games):
            await helpers.safe_respond(
                interaction,
                content="Invalid game index",
                ephemeral=True
            )
            return
        
        # Handle player selection
        if self.selected_player1 is None:
            # Store first selected player
            self.selected_player1 = (game_index, team, player_index)
            await helpers.safe_respond(
                interaction,
                content=f"Selected {player_name}. Now select another player to swap with.",
                ephemeral=True
            )
        else:
            # Store second selected player
            self.selected_player2 = (game_index, team, player_index)
            
            # Get player objects
            game1, team1, idx1 = self.selected_player1
            game2, team2, idx2 = self.selected_player2
            
            # Get player names for confirmation
            player1 = self.games[game1][team1][idx1]
            player2 = self.games[game2][team2][idx2]
            player1_name = getattr(player1, "username", "Unknown")
            player2_name = getattr(player2, "username", "Unknown")
            
            # Perform swap
            self.games[game1][team1][idx1], self.games[game2][team2][idx2] = \
                self.games[game2][team2][idx2], self.games[game1][team1][idx1]
            
            # Reset selection
            self.selected_player1 = None
            self.selected_player2 = None
            
            # Update all messages
            await self.update_all_messages()
            
            await helpers.safe_respond(
                interaction,
                content=f"Swapped {player1_name} with {player2_name}",
                ephemeral=True
            )
    
    async def toggle_swap_mode(self, interaction: discord.Interaction) -> None:
        """
        Toggle player swapping mode.
        
        Args:
            interaction: Discord interaction
        """
        self.swap_mode = not self.swap_mode
        self.selected_player1 = None
        self.selected_player2 = None
        
        await helpers.safe_respond(
            interaction,
            content=f"Player swapping mode is now {'enabled' if self.swap_mode else 'disabled'}",
            ephemeral=True
        )