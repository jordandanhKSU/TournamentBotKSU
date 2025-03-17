import random
import os
import asyncio
from openpyxl import load_workbook
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv, find_dotenv, set_key
import databaseManager
import Matchmaking

# ========== Configuration and Initialization ==========

load_dotenv(find_dotenv())

TOKEN = os.getenv('DISCORD_TOKEN')
SPREADSHEET_PATH = os.path.abspath(os.getenv('SPREADSHEET_PATH'))
DB_PATH = os.getenv('DB_PATH')
DISCORD_GUILD_ID = int(os.getenv('DISCORD_GUILD_ID'))
MY_GUILD = discord.Object(id=DISCORD_GUILD_ID)

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
global_game_state = None
current_checkin_view = None


# ========== Bot Event Handlers ==========

@bot.event
async def on_ready():
    """Handler for when the bot is ready and connected to Discord."""
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await databaseManager.initialize_database()
    
    # Sync commands with the guild
    bot.tree.copy_global_to(guild=MY_GUILD)
    await bot.tree.sync(guild=MY_GUILD)
    
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")


# ========== Admin Commands ==========

@bot.tree.command(
    name="createadminchannel",
    description="Set the admin channel for game management",
    guild=MY_GUILD
)
async def create_admin_channel(interaction: discord.Interaction):
    """Sets the current channel as the admin channel for tournament management."""
    channel_id = str(interaction.channel.id)
    os.environ["ADMIN_CHANNEL"] = channel_id
    dotenv_path = find_dotenv()
    set_key(dotenv_path, "ADMIN_CHANNEL", channel_id)
    await interaction.response.send_message(
        f"Admin channel set to {interaction.channel.mention}.",
        ephemeral=True
    )


# ========== Player Stats and Management ==========

@bot.tree.command(
    name="stats", 
    description="Display player statistics", 
    guild=MY_GUILD
)
async def stats(interaction: discord.Interaction, discord_id: str):
    """Displays statistics for a player based on their Discord ID."""
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
        color=discord.Color.blue()
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
    name="toxicity",
    description="Update the toxicity points of a user based on their Discord ID",
    guild=MY_GUILD
)
async def update_toxicity_command(interaction: discord.Interaction, discord_id: str):
    """Updates toxicity points for a player based on their Discord ID."""
    success = await databaseManager.update_toxicity_by_id(discord_id)
    
    if success:
        await interaction.response.send_message(
            f"Toxicity points updated for Discord ID: {discord_id}",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"Failed to update toxicity for Discord ID: {discord_id}. User not found.",
            ephemeral=True
        )


@bot.tree.command(
    name="unlink",
    description="Unlink your Riot ID from your Discord account",
    guild=MY_GUILD
)
async def unlink_riot_id_command(interaction: discord.Interaction):
    """Unlinks the user's Riot ID from their Discord account."""
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
    """Links the user's Discord account with their Riot ID."""
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


# ========== Role Preference System ==========

class RoleSelect(discord.ui.Select):
    """Dropdown select for selecting role preference (1-5)."""
    def __init__(self, role_name: str, index: int):
        options = [discord.SelectOption(label=str(i), value=str(i)) for i in range(1, 6)]
        super().__init__(
            placeholder=f"Select preference for {role_name}",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=role_name
        )
        self.role_name = role_name
        self.order = index
        self.value = None

    async def callback(self, interaction: discord.Interaction):
        self.value = self.values[0]
        await interaction.response.defer()


class RolePreferenceView(discord.ui.View):
    """View containing all role preference selects."""
    def __init__(self):
        super().__init__(timeout=None)
        self.roles = ["Top", "Jungle", "Mid", "Bot", "Support"]
        for index, role in enumerate(self.roles):
            self.add_item(RoleSelect(role, index))


class SubmitButton(discord.ui.Button):
    """Button for submitting role preferences."""
    def __init__(self, dropdown_msg, dropdown_view):
        super().__init__(label="Submit", style=discord.ButtonStyle.green)
        self.dropdown_msg = dropdown_msg
        self.dropdown_view = dropdown_view

    async def callback(self, interaction: discord.Interaction):
        try:
            # Check if all roles have preferences selected
            for child in self.dropdown_view.children:
                if isinstance(child, RoleSelect) and child.value is None:
                    await interaction.response.send_message(
                        "Please select a preference for all roles before submitting.",
                        ephemeral=True
                    )
                    return

            # Get the sorted preferences
            sorted_selects = sorted(
                [child for child in self.dropdown_view.children if isinstance(child, RoleSelect)],
                key=lambda x: x.order
            )
            result = "".join(select.value for select in sorted_selects)

            # Update the original message with the result
            original_embed = self.dropdown_msg.embeds[0]
            new_embed = discord.Embed(
                title=original_embed.title,
                color=original_embed.color
            )
            new_embed.add_field(name="Result", value=result, inline=False)

            # Disable all dropdown selects
            for child in self.dropdown_view.children:
                child.disabled = True
            await self.dropdown_msg.edit(embed=new_embed, view=self.dropdown_view)

            # Save the role preference to the database
            await databaseManager.set_role_preference(str(interaction.user.id), result)
            
            # Disable the submit button
            self.disabled = True
            await interaction.response.edit_message(view=self.view)
            await interaction.followup.send("Preferences submitted and saved!", ephemeral=True)

        except Exception as e:
            print(f"Error in submit callback: {e}")
            await interaction.response.send_message(
                "An error occurred while submitting preferences. Please try again.",
                ephemeral=True
            )


class SubmitPreferenceView(discord.ui.View):
    """View containing the submit button for role preferences."""
    def __init__(self, dropdown_msg, dropdown_view):
        super().__init__(timeout=None)
        self.dropdown_msg = dropdown_msg
        self.dropdown_view = dropdown_view
        self.add_item(SubmitButton(dropdown_msg, dropdown_view))


@bot.tree.command(
    name="rolepreference",
    description="Set your role preferences",
    guild=MY_GUILD
)
async def role_preference(interaction: discord.Interaction):
    """Command to set role preferences for matchmaking."""
    embed = discord.Embed(
        title="Role Preference",
        description="Please select your role preference for each role.\n1 being most desirable\n5 being least desirable.",
        color=discord.Color.blue()
    )
    dropdown_view = RolePreferenceView()
    
    await interaction.response.send_message(
        embed=embed,
        view=dropdown_view,
        ephemeral=True
    )
    dropdown_msg = await interaction.original_response()

    submit_embed = discord.Embed(
        title="Submit Your Preferences",
        description="Once done, click submit below:",
        color=discord.Color.green()
    )
    submit_view = SubmitPreferenceView(dropdown_msg, dropdown_view)
    await interaction.followup.send(
        embed=submit_embed,
        view=submit_view,
        ephemeral=True
    )


# ========== Check-In System ==========

class DummyMember:
    """A simplified mock of a Discord member for testing purposes."""
    def __init__(self, id):
        self.id = id
        self.mention = f"<@{id}>"


class StartGameView(discord.ui.View):
    """View for the check-in and game start process."""
    def __init__(self, creator_id: int):
        super().__init__(timeout=None)
        self.creator_id = creator_id
        self.checked_in_users = []
        self.volunteers = []  # Track users who volunteer to be removed first

    @discord.ui.button(label="Check In", style=discord.ButtonStyle.green)
    async def check_in_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handle check-in requests from users."""
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
        """Handle requests to leave the check-in list."""
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
        """Handle requests to volunteer to be cut from games first."""
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
        """Handle game start process initiated by the creator."""
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
        
        global global_game_state
        # Pass the cut players as the sitting-out players and store the public channel
        global_game_state = GlobalGameState(games, cut_players, interaction.channel)

        # Find the admin channel
        admin_channel_id = os.getenv("ADMIN_CHANNEL")
        if not admin_channel_id:
            await interaction.followup.send(
                "Admin channel not set. Please run the createAdminChannel command first.",
                ephemeral=True
            )
            return
        
        admin_channel = bot.get_channel(int(admin_channel_id))
        if admin_channel is None:
            await interaction.followup.send(
                "Admin channel could not be found. Ensure the bot has access to that channel.",
                ephemeral=True
            )
            return

        # Send embeds for all games to the admin channel
        for game_index in range(len(global_game_state.games)):
            embed = global_game_state.generate_embed(game_index)
            msg = await admin_channel.send(embed=embed, view=GameControlView(global_game_state, game_index))
            global_game_state.game_messages[game_index] = msg

        # Send a separate embed for sitting-out players
        sitting_out_embed = global_game_state.generate_sitting_out_embed()
        sitting_out_msg = await admin_channel.send(embed=sitting_out_embed)
        global_game_state.sitting_out_message = sitting_out_msg

        # Send a separate Global Controls embed with swap and finalize buttons
        gc_embed = discord.Embed(
            title="Global Controls",
            description="Toggle swap mode or finalize games.",
            color=discord.Color.gold()
        )
        # Store the global controls message reference for persistence
        gc_message = await admin_channel.send(embed=gc_embed, view=GlobalSwapControlView())
        global_game_state.global_controls_message = gc_message

        try:
            await interaction.followup.send(
                f"Game messages created in the admin channel! {len(cut_players)} players were removed.",
                ephemeral=True
            )
        except discord.errors.NotFound:
            print("Failed to send followup message: Unknown Webhook")
        
    @discord.ui.button(label="Cancel\nGame", style=discord.ButtonStyle.danger, row=1)
    async def cancel_checkin_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Cancel the current check-in session completely."""
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message("Only the creator can cancel the check-in!", ephemeral=True)
            return
            
        # Apply fade transition effect by disabling all buttons
        for child in self.children:
            child.disabled = True
        
        await interaction.message.edit(view=self)
        
        # Reset the global check-in view
        global current_checkin_view
        current_checkin_view = None
        
        # Add a cancelled message to the embed
        embed = interaction.message.embeds[0]
        embed.title = "📋 Check-In Cancelled"
        embed.color = discord.Color.dark_gray()
        embed.clear_fields()
        embed.add_field(name="Status", value="This check-in session has been cancelled.", inline=False)
        
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message("Game check-in session has been cancelled.", ephemeral=True)

    async def update_embed(self, interaction: discord.Interaction):
        """Update the check-in embed with the current list of users."""
        embed = interaction.message.embeds[0]
        if not self.checked_in_users:
            checkin_text = "No one has checked in yet."
        else:
            mentions = [user.mention for user in self.checked_in_users]
            rows = [" ".join(mentions[i:i+5]) for i in range(0, len(mentions), 5)]
            checkin_text = "\n".join(rows)
        
        embed.clear_fields()
        embed.add_field(name="Checked-in Users", value=checkin_text, inline=False)
        
        # Add volunteers section if there are any
        if self.volunteers:
            volunteer_mentions = [volunteer.mention for volunteer in self.volunteers]
            volunteer_rows = [" ".join(volunteer_mentions[i:i+5]) for i in range(0, len(volunteer_mentions), 5)]
            volunteer_text = "\n".join(volunteer_rows)
            embed.add_field(name="Volunteers to be Cut First", value=volunteer_text, inline=False)
        
        await interaction.message.edit(embed=embed)


@bot.tree.command(
    name="checkin",
    description="Start a check-in session for players",
    guild=MY_GUILD
)
async def checkin(interaction: discord.Interaction):
    """Command to start a check-in session for tournament players."""
    # Prevent check-in in admin channel
    admin_channel_id = os.getenv("ADMIN_CHANNEL")
    if admin_channel_id and str(interaction.channel.id) == admin_channel_id:
        await interaction.response.send_message(
            "Check-in cannot be started in the admin channel. Please use a public channel instead.",
            ephemeral=True
        )
        return
        
    global current_checkin_view  # Use the global variable
    embed = discord.Embed(title="📋 Check-In List", color=discord.Color.green())
    embed.add_field(name="Checked-in Users", value="No one has checked in yet.", inline=False)
    current_checkin_view = StartGameView(interaction.user.id)
    await interaction.response.send_message(
        embed=embed,
        view=current_checkin_view,
        ephemeral=False
    )


@bot.tree.command(
    name="forcecheckin",
    description="Force check in players by ID range",
    guild=MY_GUILD
)
async def force_check_in(interaction: discord.Interaction, start_id: int, end_id: int):
    """Command to force check-in players by their Discord ID range (for testing)."""
    global current_checkin_view
    if current_checkin_view is None:
        await interaction.response.send_message("No active check-in session. Run /checkin first.", ephemeral=True)
        return
    
    if start_id > end_id:
        await interaction.response.send_message(
            "Invalid range: start_id must be less than or equal to end_id.", 
            ephemeral=True
        )
        return

    count = 0
    for i in range(start_id, end_id + 1):
        dummy = DummyMember(i)
        # Avoid duplicates
        if any(member.id == dummy.id for member in current_checkin_view.checked_in_users):
            continue
        current_checkin_view.checked_in_users.append(dummy)
        count += 1

    try:
        await current_checkin_view.update_embed(interaction)
    except Exception as e:
        print(f"Failed to update embed: {e}")

    await interaction.response.send_message(f"Forced check in for {count} players.", ephemeral=True)


# ========== Game Management System ==========
class GlobalGameState:
    """Manages the global state of all games in the tournament."""
    def __init__(self, games: list, sitting_out: list = None, public_channel=None):
        self.games = games
        self.game_messages = {}
        self.selected = None
        self.swap_mode = False
        self.finalized = False
        # Store sitting out players
        self.sitting_out = sitting_out if sitting_out is not None else []
        self.sitting_out_message = None  # Message for sitting out players
        
        # Store the public channel where check-in happened
        self.public_channel = public_channel
        
        # Store the global controls message for persistence
        self.global_controls_message = None
        
        # MVP Voting State Management
        self.mvp_voting_active = {}  # {game_index: bool}
        self.mvp_votes = {}  # {game_index: {voter_id: voted_for_id}}
        self.mvp_vote_messages = {}  # {game_index: message}
        self.mvp_admin_messages = {}  # {game_index: message}
        self.current_voting_game = None  # Currently active voting game index
        
        # Game result tracking for database updates
        self.game_results = {}  # {game_index: 'blue' or 'red'}
        self.current_voting_game = None  # Currently active voting game index

    def generate_embed(self, game_index: int) -> discord.Embed:
        """Generate an embed for a specific game."""
        game = self.games[game_index]
        blue_team_str = "\n".join(player.username for player in game["blue"])
        red_team_str = "\n".join(player.username for player in game["red"])
        embed = discord.Embed(title=f"Game {game_index+1}", color=discord.Color.blue())
        embed.add_field(name="Blue Team", value=blue_team_str, inline=True)
        embed.add_field(name="Red Team", value=red_team_str, inline=True)
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
        for game_index, message in self.game_messages.items():
            embed = self.generate_embed(game_index)
            view = GameControlView(self, game_index)
            try:
                await message.edit(embed=embed, view=view)
            except Exception as e:
                print(f"Failed to update message for Game {game_index+1}: {e}")
        
        if self.sitting_out_message:
            sitting_out_embed = self.generate_sitting_out_embed()
            try:
                # Create a new view for sitting out players if swap mode is enabled and games aren't finalized
                if self.swap_mode and not self.finalized:
                    view = SittingOutView(self)
                    await self.sitting_out_message.edit(embed=sitting_out_embed, view=view)
                else:
                    # Remove buttons when swap mode is off or games are finalized
                    await self.sitting_out_message.edit(embed=sitting_out_embed, view=None)
            except Exception as e:
                print(f"Failed to update sitting out message: {e}")
    
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
        
        # Get game players
        game = self.games[game_index]
        all_players = game["blue"] + game["red"]
        
        # Create voting embed for players
        voting_embed = discord.Embed(
            title=f"MVP Voting - Game {game_index+1}",
            description="Vote for the Most Valuable Player in your game!\nYou can only vote once, and you cannot vote for yourself.",
            color=discord.Color.gold()
        )
        
        # Generate player mentions
        player_mentions = " ".join([f"<@{player.discord_id}>" for player in all_players])
        
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
            voting_msg = await public_channel.send(
                embed=voting_embed,
                view=MVPVotingView(self, game_index, all_players)
            )
            # Mention players in a separate message that can be deleted later
            mention_msg = await public_channel.send(f"🏆 **Game {game_index+1} MVP Voting:** {player_mentions}")
            self.mvp_vote_messages[game_index] = voting_msg
        except Exception as e:
            print(f"Error sending voting message to public channel: {e}")
            await interaction.response.send_message(
                f"Error sending voting message: {str(e)}",
                ephemeral=True
            )
            return
        
        # Create admin tracking embed
        admin_embed = discord.Embed(
            title=f"MVP Vote Admin Panel - Game {game_index+1}",
            description="Current voting status:",
            color=discord.Color.dark_gold()
        )
        
        # Add player fields with 0 votes
        for player in all_players:
            admin_embed.add_field(
                name=player.username,
                value="0 votes",
                inline=True
            )
        
        # Add non-voters field
        non_voters = "\n".join([player.username for player in all_players])
        admin_embed.add_field(
            name="Players who haven't voted:",
            value=non_voters if non_voters else "All players have voted!",
            inline=False
        )
        
        # Send admin tracking embed
        admin_channel_id = os.getenv("ADMIN_CHANNEL")
        admin_channel = interaction.client.get_channel(int(admin_channel_id))
        
        admin_msg = await admin_channel.send(
            embed=admin_embed
        )
        self.mvp_admin_messages[game_index] = admin_msg
        
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
        
        # Get the game data
        game = self.games[game_index]
        all_players = game["blue"] + game["red"]
        
        # Find the MVP player object
        mvp_player = None
        for player in all_players:
            if player.discord_id == mvp_id:
                mvp_player = player
                break
        
        # Handle results display
        if mvp_player and max_votes > 0:
            # Get the game result
            result = self.game_results.get(game_index, None)
            if result:
                # Store match data in database
                await databaseManager.store_match_data(self.games[game_index], result, mvp_id)
                
                # Update all player statistics in one call
                await databaseManager.update_all_player_stats(self.games[game_index], result, mvp_id)
            else:
                print(f"Error: No game result found for game {game_index}")
            
            # Create results embed
            results_embed = discord.Embed(
                title=f"MVP Results - Game {game_index+1}",
                description=f"🏆 **{mvp_player.username}** has been voted MVP with {max_votes} votes!",
                color=discord.Color.gold()
            )
            
            # Add voting breakdown
            vote_breakdown = ""
            for player in all_players:
                votes = vote_counts.get(player.discord_id, 0)
                vote_breakdown += f"{player.username}: {votes} vote{'s' if votes != 1 else ''}\n"
            
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
            
            # Update admin message
            admin_msg = self.mvp_admin_messages.get(game_index)
            if admin_msg:
                await admin_msg.edit(
                    embed=discord.Embed(
                        title=f"MVP Vote Completed - Game {game_index+1}",
                        description=f"Winner: {mvp_player.username} with {max_votes} votes",
                        color=discord.Color.dark_green()
                    )
                )
            
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
        
        # Update admin message
        admin_msg = self.mvp_admin_messages.get(game_index)
        if admin_msg:
            await admin_msg.edit(
                embed=discord.Embed(
                    title=f"MVP Vote Cancelled - Game {game_index+1}",
                    description="Voting was cancelled by an administrator. Match data saved.",
                    color=discord.Color.dark_red()
                )
            )
        
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

    async def update_mvp_admin_embed(self, game_index: int):
        """Update the admin embed with current voting status."""
        if not self.mvp_voting_active.get(game_index, False):
            return
        
        admin_msg = self.mvp_admin_messages.get(game_index)
        if not admin_msg:
            return
        
        # Get vote counts
        votes = self.mvp_votes.get(game_index, {})
        vote_counts = {}
        
        for voted_id in votes.values():
            vote_counts[voted_id] = vote_counts.get(voted_id, 0) + 1
        
        # Get game players
        game = self.games[game_index]
        all_players = game["blue"] + game["red"]
        
        # Create updated embed
        admin_embed = discord.Embed(
            title=f"MVP Vote Admin Panel - Game {game_index+1}",
            description="Current voting status:",
            color=discord.Color.dark_gold()
        )
        
        # Add player fields with vote counts
        for player in all_players:
            votes_count = vote_counts.get(player.discord_id, 0)
            admin_embed.add_field(
                name=player.username,
                value=f"{votes_count} vote{'s' if votes_count != 1 else ''}",
                inline=True
            )
        
        # Add non-voters field
        voters = set(votes.keys())
        non_voters = []
        
        for player in all_players:
            if player.discord_id not in voters:
                non_voters.append(player.username)
        
        non_voters_text = "\n".join(non_voters) if non_voters else "All players have voted!"
        admin_embed.add_field(
            name="Players who haven't voted:",
            value=non_voters_text,
            inline=False
        )
        
        # Update the embed
        await admin_msg.edit(embed=admin_embed)
        
        # Check if everyone has voted and automatically end voting if needed
        if not non_voters:
            # Create a dummy interaction for ending the vote
            try:
                bot_user = admin_msg.guild.me
                # Use a background task to end the vote to avoid issues with the current interaction
                bot.loop.create_task(self.auto_end_mvp_voting(game_index, admin_msg.channel))
            except Exception as e:
                print(f"Error auto-ending MVP vote: {e}")
    
    async def auto_end_mvp_voting(self, game_index, admin_channel):
        """Automatically end MVP voting when everyone has voted."""
        try:
            # Wait a brief moment to allow for any race conditions
            await asyncio.sleep(1)
            
            # Create a fake interaction for the end_mvp_voting method
            class FakeInteraction:
                def __init__(self, admin_channel, public_channel):
                    self.channel = admin_channel
                    self.client = bot
                
                async def response_send_message(self, content, ephemeral=False):
                    await self.channel.send(f"Auto-end MVP vote: {content}")
            
            fake_interaction = FakeInteraction(admin_channel, self.public_channel)
            fake_interaction.response = fake_interaction
            
            # End the voting
            await self.end_mvp_voting(fake_interaction, game_index)
            
            # Send a message in the admin channel notifying about auto-completion
            await admin_channel.send(
                f"MVP voting for Game {game_index+1} was automatically ended because all players voted."
            )
            
            # Update any existing GlobalControlView
            self.current_voting_game = None
            for message in await admin_channel.history(limit=10).flatten():
                if message.author.id == bot.user.id and len(message.components) > 0:
                    try:
                        # Check if this is the global controls message
                        if "Global Controls" in message.embeds[0].title:
                            # Update the view
                            gc_view = GlobalControlView()
                            await message.edit(view=gc_view)
                            break
                    except:
                        continue
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


class SittingOutButton(discord.ui.Button):
    """Button representing a player who is sitting out."""
    def __init__(self, player_name: str, index: int):
        super().__init__(label=player_name, style=discord.ButtonStyle.secondary)
        self.player_index = index

    async def callback(self, interaction: discord.Interaction):
        global global_game_state
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


class GamePlayerButton(discord.ui.Button):
    """Button representing a player in a game."""
    def __init__(self, game_index: int, team: str, player_index: int, player_name: str):
        style = discord.ButtonStyle.primary if team.lower() == "blue" else discord.ButtonStyle.danger
        super().__init__(label=player_name, style=style)
        self.game_index = game_index
        self.team = team
        self.player_index = player_index

    async def callback(self, interaction: discord.Interaction):
        global global_game_state
        await global_game_state.handle_selection(
            interaction, 
            self.game_index, 
            self.team, 
            self.player_index, 
            self.label
        )


class EndMVPVoteButton(discord.ui.Button):
    """Button to end MVP voting for a game."""
    def __init__(self, game_index: int):
        super().__init__(label="End MVP Vote", style=discord.ButtonStyle.success)
        self.game_index = game_index
    
    async def callback(self, interaction: discord.Interaction):
        global global_game_state
        
        if not global_game_state.mvp_voting_active.get(self.game_index, False):
            await interaction.response.send_message(
                f"No active MVP voting for Game {self.game_index+1}!",
                ephemeral=True
            )
            return
        
        try:
            await global_game_state.end_mvp_voting(interaction, self.game_index)
            
            # Update game message with final results
            game_message = global_game_state.game_messages.get(self.game_index)
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
        global global_game_state
        
        if not global_game_state.mvp_voting_active.get(self.game_index, False):
            await interaction.response.send_message(
                f"No active MVP voting for Game {self.game_index+1}!",
                ephemeral=True
            )
            return
        
        try:
            await global_game_state.cancel_mvp_voting(interaction, self.game_index)
            
            # Update game message with cancelled status
            game_message = global_game_state.game_messages.get(self.game_index)
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
        global global_game_state
        
        # Check if MVP voting is already active or completed
        if global_game_state.mvp_voting_active.get(self.game_index, False):
            await interaction.response.send_message(
                f"MVP voting for Game {self.game_index+1} is already in progress. Please end or cancel it first.",
                ephemeral=True
            )
            return
            
        # Mark this game as not needing MVP voting
        if self.game_index not in global_game_state.mvp_voting_active:
            global_game_state.mvp_voting_active[self.game_index] = False
        
        # Get the game result and update the database
        result = global_game_state.game_results.get(self.game_index, None)
        if result:
            # Store match data in database with NULL MVP
            await databaseManager.store_match_data(global_game_state.games[self.game_index], result, None)
            
            # Update all player statistics
            await databaseManager.update_all_player_stats(global_game_state.games[self.game_index], result, None)
        else:
            print(f"Error: No game result found for game {self.game_index}")
        
        # Remove the MVP buttons but keep the game result
        game_message = global_game_state.game_messages.get(self.game_index)
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
            self.add_item(MVPVoteButton(game_index, None, None))
            self.add_item(SkipMVPButton(game_index))
        else:
            # If voting is active, show End and Cancel buttons
            self.add_item(EndMVPVoteButton(game_index))
            self.add_item(CancelMVPVoteButton(game_index))


class MVPVoteButton(discord.ui.Button):
    """Button to start MVP voting for a game after winner is declared."""
    def __init__(self, game_index: int, blue_team=None, red_team=None):
        super().__init__(label="Vote for MVP", style=discord.ButtonStyle.secondary)
        self.game_index = game_index
        # Store teams for backward compatibility
        self.blue_team = blue_team
        self.red_team = red_team
    
    async def callback(self, interaction: discord.Interaction):
        global global_game_state
        
        # Check if voting is already active for this game
        if global_game_state.mvp_voting_active.get(self.game_index, False):
            await interaction.response.send_message(
                f"MVP voting for Game {self.game_index+1} is already active!",
                ephemeral=True
            )
            return
        
        # Get the blue and red teams from the game state
        game = global_game_state.games[self.game_index]
        blue_team = game["blue"]
        red_team = game["red"]
            
        # Start MVP voting
        await global_game_state.start_mvp_voting(interaction, self.game_index)
        
        # Update this game's message with new controls while preserving result
        game_message = global_game_state.game_messages.get(self.game_index)
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
        global global_game_state
        
        embed = interaction.message.embeds[0]
        embed.add_field(name="Result", value="Blue Team Wins!", inline=False)
        
        # Store the game result for later database update
        global_game_state.game_results[self.game_index] = "blue"
            
        # Create a new view with MVP controls directly under this game
        mvp_control_view = GameMVPControlView(self.game_index, False)
        
        # Update the message with the new view while preserving the result
        await interaction.message.edit(embed=embed, view=mvp_control_view)
        
        # Mark this game as needing MVP voting
        global_game_state.game_messages[self.game_index] = interaction.message
        
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
        global global_game_state
        
        embed = interaction.message.embeds[0]
        embed.add_field(name="Result", value="Red Team Wins!", inline=False)
        
        # Store the game result for later database update
        global_game_state.game_results[self.game_index] = "red"
            
        # Create a new view with MVP controls directly under this game
        mvp_control_view = GameMVPControlView(self.game_index, False)
        
        # Update the message with the new view while preserving the result
        await interaction.message.edit(embed=embed, view=mvp_control_view)
        
        # Make sure game message is properly stored
        global_game_state.game_messages[self.game_index] = interaction.message
        
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
            
            blue_win = BlueWinButton(self.game_index, blue_team, red_team)
            blue_win.row = 2
            self.add_item(blue_win)
            
            red_win = RedWinButton(self.game_index, blue_team, red_team)
            red_win.row = 2
            self.add_item(red_win)


class MVPVotingView(discord.ui.View):
    """View for players to cast their MVP votes."""
    def __init__(self, global_state, game_index, players):
        super().__init__(timeout=None)
        self.global_state = global_state
        self.game_index = game_index
        
        # Get team composition to determine button colors
        game = global_state.games[game_index]
        blue_team_ids = [p.discord_id for p in game["blue"]]
        
        # Add a button for each player
        for i, player in enumerate(players):
            # Determine row placement (5 buttons per row)
            row = i // 5
            # Check if player is on blue team (otherwise they're on red)
            is_blue_team = player.discord_id in blue_team_ids
            self.add_item(PlayerMVPButton(game_index, player, is_blue_team, row))

class PlayerMVPButton(discord.ui.Button):
    """Button for voting for a specific player as MVP."""
    def __init__(self, game_index, player, is_blue_team, row=0):
        # Set button style based on team
        button_style = discord.ButtonStyle.primary if is_blue_team else discord.ButtonStyle.danger
        
        super().__init__(
            label=player.username,
            style=button_style,  # Apply team color
            row=row
        )
        self.game_index = game_index
        self.player = player
    
    async def callback(self, interaction: discord.Interaction):
        global global_game_state
        
        # Verify voter is in the game
        voter_id = str(interaction.user.id)
        game = global_game_state.games[self.game_index]
        all_players = game["blue"] + game["red"]
        
        voter_in_game = False
        for player in all_players:
            if player.discord_id == voter_id:
                voter_in_game = True
                break
        
        if not voter_in_game:
            await interaction.response.send_message(
                "You can only vote in games you participated in.",
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
        if self.game_index not in global_game_state.mvp_votes:
            global_game_state.mvp_votes[self.game_index] = {}
        
        # Check if already voted
        if voter_id in global_game_state.mvp_votes[self.game_index]:
            previous_vote = global_game_state.mvp_votes[self.game_index][voter_id]
            previous_player = None
            for p in all_players:
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
        global_game_state.mvp_votes[self.game_index][voter_id] = self.player.discord_id
        
        # Update admin tracking embed
        await global_game_state.update_mvp_admin_embed(self.game_index)

class GameSelectForMVP(discord.ui.Select):
    """Dropdown to select which game to start MVP voting for."""
    def __init__(self):
        global global_game_state
        
        options = []
        for i, game in enumerate(global_game_state.games):
            # Only show games without active voting
            if not global_game_state.mvp_voting_active.get(i, False):
                options.append(discord.SelectOption(
                    label=f"Game {i+1}",
                    value=str(i),
                    description=f"Blue vs Red"
                ))
        
        super().__init__(
            placeholder="Select a game",
            min_values=1,
            max_values=1,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        global global_game_state
        game_index = int(self.values[0])
        
        # Start MVP voting for the selected game
        await global_game_state.start_mvp_voting(interaction, game_index)
        
        # Remove the selection view
        await interaction.message.delete()
        
        # Update the global controls to show MVP vote management buttons
        for message in await interaction.channel.history(limit=10).flatten():
            if message.author.id == interaction.client.user.id and len(message.components) > 0:
                try:
                    # Check if this is the global controls message
                    if "Global Controls" in message.embeds[0].title:
                        # Update with new view
                        global_view = GlobalControlView()
                        await message.edit(view=global_view)
                        break
                except:
                    continue

class ConfirmNextGameView(discord.ui.View):
    """Confirmation view for skipping active MVP voting."""
    def __init__(self, global_control_view):
        super().__init__(timeout=None)
        self.global_control_view = global_control_view
    
    @discord.ui.button(label="Yes, Skip Voting", style=discord.ButtonStyle.danger)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        global global_game_state
        
        # Cancel all active MVP votes in any game
        for game_index, is_active in list(global_game_state.mvp_voting_active.items()):
            if is_active:
                await global_game_state.cancel_mvp_voting(
                    interaction,
                    game_index,
                    silent=True
                )
        
        # Fade out all game controls
        await self.global_control_view.fade_all_game_controls()
        
        # Fade out the buttons on the global controls message
        if global_game_state.global_controls_message:
            gc_embed = discord.Embed(
                title="Global Controls (Preparing New Game)",
                description="MVP voting has been skipped. Preparing for the next game.",
                color=discord.Color.dark_gold()
            )
            # Disable all buttons to create a fade effect
            disabled_view = GlobalControlView()
            for child in disabled_view.children:
                child.disabled = True
            await global_game_state.global_controls_message.edit(embed=gc_embed, view=disabled_view)
        
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

class GlobalControlView(discord.ui.View):
    """Simplified global controls that only handle game progression."""
    def __init__(self):
        super().__init__(timeout=None)
        
        # Add the Next Game button with green styling
        next_game_button = discord.ui.Button(
            label="Next Game",
            style=discord.ButtonStyle.success,  # Change to green for action buttons
            row=0
        )
        next_game_button.callback = self.next_game_callback
        self.add_item(next_game_button)
    
    async def fade_all_game_controls(self):
        """Disable all interactive buttons in game messages to create a fade effect."""
        global global_game_state
        
        # Create empty views to replace the functional ones
        for game_index, message in global_game_state.game_messages.items():
            try:
                # Create a completely empty view instead of using game control buttons
                empty_view = discord.ui.View()
                
                # Update the message with no functional buttons
                await message.edit(view=empty_view)
            except Exception as e:
                print(f"Failed to disable controls for Game {game_index+1}: {e}")
        
        # Disable sitting out controls if they exist
        if global_game_state.sitting_out_message:
            try:
                # Create a disabled sitting out view
                if global_game_state.swap_mode:
                    disabled_view = SittingOutView(global_game_state)
                    for child in disabled_view.children:
                        child.disabled = True
                    await global_game_state.sitting_out_message.edit(view=disabled_view)
                    
            except Exception as e:
                print(f"Failed to disable sitting out controls: {e}")
                
        # Disable MVP admin message controls
        for game_index, admin_msg in global_game_state.mvp_admin_messages.items():
            if admin_msg:
                try:
                    await admin_msg.edit(view=None)
                except Exception as e:
                    print(f"Failed to disable MVP admin controls for Game {game_index+1}: {e}")
    
    async def next_game_callback(self, interaction: discord.Interaction):
        """Proceed to next game setup with auto re-check-in."""
        global global_game_state, current_checkin_view
        
        # Debug print to see the current state
        print(f"Next Game clicked - Games: {len(global_game_state.games)}, Messages: {len(global_game_state.game_messages)}")
        
        # First acknowledge the interaction to avoid timeout errors
        try:
            await interaction.response.defer(ephemeral=True)
        except Exception as e:
            print(f"Error deferring interaction: {e}")
        
        # Define helper functions to check game state correctly
        def has_result(game_index):
            """Check if a game has a winner declared."""
            game_message = global_game_state.game_messages.get(game_index)
            if not game_message:
                return False
                
            return any(field.name == "Result" for field in game_message.embeds[0].fields)
            
        def is_mvp_resolved(game_index):
            """Check if MVP voting has been resolved (either completed or skipped)."""
            if game_index not in global_game_state.mvp_voting_active:
                return False  # Not addressed at all
                
            return global_game_state.mvp_voting_active[game_index] == False  # Explicitly completed or skipped
        
        # Get list of games that have messages
        games_with_messages = [idx for idx in range(len(global_game_state.games))
                              if global_game_state.game_messages.get(idx)]
        
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
        disabled_view = GlobalControlView()
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
        if global_game_state and global_game_state.public_channel:
            # Get all unique players from all games
            for game in global_game_state.games:
                previous_players.extend(game["blue"])
                previous_players.extend(game["red"])
            
            # Add sitting out players
            if global_game_state.sitting_out:
                previous_players.extend(global_game_state.sitting_out)
            
            # Create a new check-in session in the same channel
            embed = discord.Embed(title="📋 Check-In List", color=discord.Color.green())
            embed.add_field(name="Checked-in Users", value="Automatically re-checking previous players...", inline=False)
            
            # Create a new view for the next game
            current_checkin_view = StartGameView(interaction.user.id)
            
            # Send the new check-in message
            checkin_msg = await global_game_state.public_channel.send(
                embed=embed,
                view=current_checkin_view
            )
            
            # Auto-check in all previous players
            for player in previous_players:
                # Create a DummyMember for each player
                dummy = DummyMember(int(player.discord_id))
                current_checkin_view.checked_in_users.append(dummy)
            
            # Update the check-in message
            if current_checkin_view.checked_in_users:
                mentions = [user.mention for user in current_checkin_view.checked_in_users]
                rows = [" ".join(mentions[i:i+5]) for i in range(0, len(mentions), 5)]
                checkin_text = "\n".join(rows)
            else:
                checkin_text = "No one has checked in yet."
                
            embed.clear_fields()
            embed.add_field(name="Checked-in Users", value=checkin_text, inline=False)
            await checkin_msg.edit(embed=embed)
            
            await interaction.followup.send(
                f"Started a new check-in session with {len(current_checkin_view.checked_in_users)} auto-checked players.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "Preparing for the next game. Use /checkin to start a new check-in session.",
                ephemeral=True
            )
        
        # Fade out the buttons regardless
        gc_embed = discord.Embed(
            title="Global Controls (Game Complete)",
            description="Game session has ended and a new one has been created",
            color=discord.Color.dark_gold()
        )
        # Create empty view
        empty_view = discord.ui.View()
        # Edit the message
        await interaction.message.edit(embed=gc_embed, view=empty_view)

class GlobalSwapControlView(discord.ui.View):
    """View for global controls (swap mode and finalizing)."""
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="Swap", style=discord.ButtonStyle.secondary, row=0)
    async def swap_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Toggle swap mode for player rearrangement."""
        global global_game_state
        if global_game_state is None:
            await interaction.response.send_message("No game in progress.", ephemeral=True)
            return
        
        await global_game_state.toggle_swap_mode(interaction)
        button.label = "Stop Swapping" if global_game_state.swap_mode else "Swap"
        await interaction.message.edit(view=self)
    
    @discord.ui.button(label="Finalize Games", style=discord.ButtonStyle.blurple, row=0)
    async def finalize_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Finalize games and enable win declaration."""
        global global_game_state
        global_game_state.finalized = True
        
        # Update participation points for sitting-out players
        if global_game_state.sitting_out:
            sit_out_log = ["Updating participation for sitting-out players:"]
            for player in global_game_state.sitting_out:
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
        
        await global_game_state.update_all_messages()
        
        # Update the existing global controls with next game functionality
        if global_game_state.global_controls_message:
            gc_embed = discord.Embed(
                title="Global Controls",
                description="Control game progression. Next Game will only occur when all game states are finished and Cancel Games will cancel the results of all games that didn't Vote MVP or Skip to vote MVP",
                color=discord.Color.gold()
            )
            
            # Replace the view with the GlobalControlView containing the Next Game button
            await global_game_state.global_controls_message.edit(embed=gc_embed, view=GlobalControlView())
        
        # Just defer instead of sending a confirmation message
        try:
            await interaction.response.defer()
        except (discord.errors.NotFound, discord.errors.InteractionResponded):
            # Interaction may have timed out or already been responded to
            pass


# ========== Bot Execution ==========

bot.run(TOKEN)
