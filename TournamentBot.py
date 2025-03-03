import random
import os
from openpyxl import load_workbook
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv, find_dotenv, set_key
import databaseManager
import Matchmaking

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

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await databaseManager.initialize_database()
    
    bot.tree.copy_global_to(guild=MY_GUILD)
    await bot.tree.sync(guild=MY_GUILD)
    
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        print(f"Error syncing commands: {e}")

@bot.tree.command(
    name="createadminchannel",
    description="Set the admin channel for game management",
    guild=MY_GUILD
)
async def create_admin_channel(interaction: discord.Interaction):
    channel_id = str(interaction.channel.id)
    os.environ["ADMIN_CHANNEL"] = channel_id
    dotenv_path = find_dotenv()
    set_key(dotenv_path, "ADMIN_CHANNEL", channel_id)
    await interaction.response.send_message(
        f"Admin channel set to {interaction.channel.mention}.",
        ephemeral=True
    )

@bot.tree.command(
    name="rolepreference",
    description="Set your role preferences",
    guild=MY_GUILD
)
async def role_preference(interaction: discord.Interaction):
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

@bot.tree.command(name="stats", 
                description="Display player statistics", 
                guild=MY_GUILD)
async def stats(interaction: discord.Interaction, discord_id: str):
    # Retrieve player information using the provided discord_id
    player = await databaseManager.get_player_info(discord_id)
    
    if not player:
        await interaction.response.send_message(f"No player found with Discord ID: {discord_id}", ephemeral=True)
        return

    # Build the embed with the player's statistics
    embed = discord.Embed(title=f"Statistics for {player.username}", color=discord.Color.blue())
    embed.add_field(name="Discord ID", value=player.discord_id, inline=True)
    embed.add_field(name="Username", value=player.username, inline=True)
    embed.add_field(name="Riot ID", value=player.player_riot_id if player.player_riot_id else "Not linked", inline=True)
    embed.add_field(name="Participation", value=player.participation, inline=True)
    embed.add_field(name="Wins", value=player.wins, inline=True)
    embed.add_field(name="MVPs", value=player.mvps, inline=True)
    embed.add_field(name="Toxicity Points", value=player.toxicity_points, inline=True)
    embed.add_field(name="Games Played", value=player.games_played, inline=True)
    embed.add_field(name="Win Rate", value=f"{player.win_rate:.2f}%" if player.win_rate is not None else "N/A", inline=True)
    embed.add_field(name="Total Points", value=player.total_points, inline=True)
    embed.add_field(name="Player Tier", value=player.tier, inline=True)
    embed.add_field(name="Player Rank", value=player.rank, inline=True)
    
    # Convert role preference list to string (if exists)
    role_pref = "".join(str(x) for x in player.role_preference) if player.role_preference else "None"
    embed.add_field(name="Role Preference", value=role_pref, inline=True)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(
    name="toxicity",
    description="Update the toxicity points of a user based on their Discord ID",
    guild=MY_GUILD
)
async def update_toxicity_command(interaction: discord.Interaction, discord_id: str):
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
    name="checkin",
    description="Start a check-in session for players",
    guild=MY_GUILD
)
async def checkin(interaction: discord.Interaction):
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
    global current_checkin_view
    if current_checkin_view is None:
        await interaction.response.send_message("No active check-in session. Run /checkin first.", ephemeral=True)
        return
    if start_id > end_id:
        await interaction.response.send_message("Invalid range: start_id must be less than or equal to end_id.", ephemeral=True)
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

class RoleSelect(discord.ui.Select):
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
    def __init__(self):
        super().__init__(timeout=None)
        self.roles = ["Top", "Jungle", "Mid", "Bot", "Support"]
        for index, role in enumerate(self.roles):
            self.add_item(RoleSelect(role, index))

class SubmitPreferenceView(discord.ui.View):
    def __init__(self, dropdown_msg, dropdown_view):
        super().__init__(timeout=None)
        self.dropdown_msg = dropdown_msg
        self.dropdown_view = dropdown_view
        self.add_item(SubmitButton(dropdown_msg, dropdown_view))

class SubmitButton(discord.ui.Button):
    def __init__(self, dropdown_msg, dropdown_view):
        super().__init__(label="Submit", style=discord.ButtonStyle.green)
        self.dropdown_msg = dropdown_msg
        self.dropdown_view = dropdown_view

    async def callback(self, interaction: discord.Interaction):
        try:
            for child in self.dropdown_view.children:
                if isinstance(child, RoleSelect) and child.value is None:
                    await interaction.response.send_message(
                        "Please select a preference for all roles before submitting.",
                        ephemeral=True
                    )
                    return

            sorted_selects = sorted(
                [child for child in self.dropdown_view.children if isinstance(child, RoleSelect)],
                key=lambda x: x.order
            )
            result = "".join(select.value for select in sorted_selects)

            # Store `result` in your database here

            original_embed = self.dropdown_msg.embeds[0]
            new_embed = discord.Embed(
                title=original_embed.title,
                color=original_embed.color
            )
            new_embed.add_field(name="Result", value=result, inline=False)

            for child in self.dropdown_view.children:
                child.disabled = True
            await self.dropdown_msg.edit(embed=new_embed, view=self.dropdown_view)

            self.disabled = True
            await interaction.response.edit_message(view=self.view)
            await interaction.followup.send("Preferences submitted!", ephemeral=True)

        except Exception as e:
            print(f"Error in submit callback: {e}")
            await interaction.response.send_message(
                "An error occurred while submitting preferences. Please try again.",
                ephemeral=True
            )

class DummyMember:
    def __init__(self, id):
        self.id = id
        self.mention = f"<@{id}>"

class StartGameView(discord.ui.View):
    def __init__(self, creator_id: int):
        super().__init__(timeout=None)
        self.creator_id = creator_id
        self.checked_in_users = []

    @discord.ui.button(label="Check In", style=discord.ButtonStyle.green)
    async def check_in_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if any(user.id == interaction.user.id for user in self.checked_in_users):
            await interaction.response.send_message("You've already checked in!", ephemeral=True)
            return
        await databaseManager.update_username(interaction.user)
        self.checked_in_users.append(interaction.user)
        await self.update_embed(interaction)
        await interaction.response.send_message("Successfully checked in!", ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red)
    async def leave_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not any(user.id == interaction.user.id for user in self.checked_in_users):
            await interaction.response.send_message("You're not checked in!", ephemeral=True)
            return
        self.checked_in_users = [user for user in self.checked_in_users if user.id != interaction.user.id]
        await self.update_embed(interaction)
        await interaction.response.send_message("You've left the check-in list.", ephemeral=True)

    @discord.ui.button(label="Start\nGame", style=discord.ButtonStyle.grey)
    async def start_game_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message("Only the creator can start the game!", ephemeral=True)
            return

        await interaction.response.defer()

        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        # Build a list of Player objects from the check-in list.
        players = []
        for user in self.checked_in_users:
            player_obj = await databaseManager.get_player_info(str(user.id))
            if player_obj is not None:
                players.append(player_obj)

        if not players:
            await interaction.followup.send("No valid players found in the check-in list!", ephemeral=True)
            return

        # Remove players randomly until count is a multiple of 10.
        cut_players = []
        while len(players) % 10 != 0:
            removed = random.choice(players)
            players.remove(removed)
            cut_players.append(removed)
        
        # Use the matchmaking algorithm to create teams.
        blue_teams, red_teams = Matchmaking.matchmaking_multiple(players)
        games = []
        for i in range(len(blue_teams)):
            games.append({"blue": blue_teams[i], "red": red_teams[i]})
        global global_game_state
        # Pass the cut players as the sitting-out players.
        global_game_state = GlobalGameState(games, cut_players)

        admin_channel_id = os.getenv("ADMIN_CHANNEL")
        if not admin_channel_id:
            await interaction.followup.send("Admin channel not set. Please run the createAdminChannel command first.", ephemeral=True)
            return
        admin_channel = bot.get_channel(int(admin_channel_id))
        if admin_channel is None:
            await interaction.followup.send("Admin channel could not be found. Ensure the bot has access to that channel.", ephemeral=True)
            return

        # Send embeds for all games to the admin channel.
        for game_index in range(len(global_game_state.games)):
            embed = global_game_state.generate_embed(game_index)
            msg = await admin_channel.send(embed=embed, view=GameControlView(global_game_state, game_index))
            global_game_state.game_messages[game_index] = msg

        # Send a separate embed for sitting-out players (without swap/finalize buttons).
        sitting_out_embed = global_game_state.generate_sitting_out_embed()
        sitting_out_msg = await admin_channel.send(embed=sitting_out_embed)
        global_game_state.sitting_out_message = sitting_out_msg

        # Send a separate Global Controls embed with swap and finalize buttons.
        gc_embed = discord.Embed(title="Global Controls", description="Toggle swap mode or finalize games.", color=discord.Color.gold())
        await admin_channel.send(embed=gc_embed, view=GlobalSwapControlView())

        try:
            await interaction.followup.send(f"Game messages created in the admin channel! {len(cut_players)} players were removed.", ephemeral=True)
        except discord.errors.NotFound:
            print("Failed to send followup message: Unknown Webhook")

    async def update_embed(self, interaction: discord.Interaction):
        embed = interaction.message.embeds[0]
        if not self.checked_in_users:
            checkin_text = "No one has checked in yet."
        else:
            mentions = [user.mention for user in self.checked_in_users]
            rows = [" ".join(mentions[i:i+5]) for i in range(0, len(mentions), 5)]
            checkin_text = "\n".join(rows)
        embed.clear_fields()
        embed.add_field(name="Checked-in Users", value=checkin_text, inline=False)
        await interaction.message.edit(embed=embed)

class GlobalGameState:
    def __init__(self, games: list, sitting_out: list = None):
        self.games = games
        self.game_messages = {}
        self.selected = None
        self.swap_mode = False
        self.finalized = False
        # Store sitting out players
        self.sitting_out = sitting_out if sitting_out is not None else []
        self.sitting_out_message = None  # New embed message for sitting out players

    def generate_embed(self, game_index: int) -> discord.Embed:
        game = self.games[game_index]
        blue_team_str = "\n".join(player.username for player in game["blue"])
        red_team_str = "\n".join(player.username for player in game["red"])
        embed = discord.Embed(title=f"Game {game_index+1}", color=discord.Color.blue())
        embed.add_field(name="Blue Team", value=blue_team_str, inline=True)
        embed.add_field(name="Red Team", value=red_team_str, inline=True)
        return embed

    def generate_sitting_out_embed(self) -> discord.Embed:
        embed = discord.Embed(title="Sitting Out", color=discord.Color.dark_gray())
        if self.sitting_out:
            sitting_out_str = "\n".join(player.username for player in self.sitting_out)
        else:
            sitting_out_str = "None"
        embed.add_field(name="Players Sitting Out", value=sitting_out_str, inline=False)
        return embed

    async def update_all_messages(self):
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
                await self.sitting_out_message.edit(embed=sitting_out_embed)
            except Exception as e:
                print(f"Failed to update sitting out message: {e}")

    async def handle_selection(self, interaction: discord.Interaction, game_index: int, team: str, player_index: int, player_name: str):
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
            await interaction.response.send_message("Players swapped!", ephemeral=True)

    async def toggle_swap_mode(self, interaction: discord.Interaction):
        self.swap_mode = not self.swap_mode
        if not self.swap_mode:
            self.selected = None
        await self.update_all_messages()
        mode_str = "enabled (names revealed)" if self.swap_mode else "disabled (names hidden)"
        await interaction.response.send_message(f"Swap mode {mode_str}.", ephemeral=True)

class GamePlayerButton(discord.ui.Button):
    def __init__(self, game_index: int, team: str, player_index: int, player_name: str):
        style = discord.ButtonStyle.primary if team.lower() == "blue" else discord.ButtonStyle.danger
        super().__init__(label=player_name, style=style)
        self.game_index = game_index
        self.team = team
        self.player_index = player_index

    async def callback(self, interaction: discord.Interaction):
        global global_game_state
        await global_game_state.handle_selection(interaction, self.game_index, self.team, self.player_index, self.label)

class BlueWinButton(discord.ui.Button):
    def __init__(self, blue_team: list, red_team: list):
        # Store team members in the button (or view) for later reference
        super().__init__(label="Blue Team Win", style=discord.ButtonStyle.primary)
        self.blue_team = blue_team
        self.red_team = red_team

    async def callback(self, interaction: discord.Interaction):
        embed = interaction.message.embeds[0]
        embed.add_field(name="Result", value="Blue Team Wins!", inline=False)
        # Disable all buttons to prevent multiple submissions
        for child in self.view.children:
            child.disabled = True
        await interaction.message.edit(embed=embed, view=self.view)
        await interaction.response.send_message("Blue Team declared winner.", ephemeral=True)

        # Update the winning team's statistics:
        # Increase wins, games played, and update win rate for winners.
        await databaseManager.update_wins(self.blue_team)

        # For the losing team, only update games played and win rate.
        for member in self.red_team:
            await databaseManager.update_games_played(member)

class RedWinButton(discord.ui.Button):
    def __init__(self, blue_team: list, red_team: list):
        super().__init__(label="Red Team Win", style=discord.ButtonStyle.danger)
        self.blue_team = blue_team
        self.red_team = red_team

    async def callback(self, interaction: discord.Interaction):
        embed = interaction.message.embeds[0]
        embed.add_field(name="Result", value="Red Team Wins!", inline=False)
        for child in self.view.children:
            child.disabled = True
        await interaction.message.edit(embed=embed, view=self.view)
        await interaction.response.send_message("Red Team declared winner.", ephemeral=True)

        # Update the winning team's statistics:
        await databaseManager.update_wins(self.red_team)

        # Update the losing team's statistics:
        for member in self.blue_team:
            await databaseManager.update_games_played(member)


class SittingOutButton(discord.ui.Button):
    def __init__(self, player_name: str, index: int):
        super().__init__(label=player_name, style=discord.ButtonStyle.secondary)
        self.player_index = index

    async def callback(self, interaction: discord.Interaction):
        global global_game_state
        await global_game_state.handle_selection(interaction, None, "sitting_out", self.player_index, self.label)

class GameControlView(discord.ui.View):
    def __init__(self, global_state: GlobalGameState, game_index: int):
        super().__init__(timeout=None)
        self.global_state = global_state
        self.game_index = game_index
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
        if self.global_state.finalized:
            # NEW: Retrieve the teams for the game index.
            blue_team = self.global_state.games[self.game_index]["blue"]
            red_team = self.global_state.games[self.game_index]["red"]
            # Pass the teams to the button constructors.
            blue_win = BlueWinButton(blue_team, red_team)
            blue_win.row = 2
            self.add_item(blue_win)
            red_win = RedWinButton(blue_team, red_team)
            red_win.row = 2
            self.add_item(red_win)
            
class GlobalSwapControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="Swap", style=discord.ButtonStyle.secondary, row=0)
    async def swap_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        global global_game_state
        if global_game_state is None:
            await interaction.response.send_message("No game in progress.", ephemeral=True)
            return
        await global_game_state.toggle_swap_mode(interaction)
        button.label = "Stop Swapping" if global_game_state.swap_mode else "Swap"
        await interaction.message.edit(view=self)
    @discord.ui.button(label="Finalize Games", style=discord.ButtonStyle.success, row=0)
    async def finalize_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        global global_game_state
        global_game_state.finalized = True
        await global_game_state.update_all_messages()
        await interaction.message.delete()
        await interaction.response.send_message("Global controls finalized.", ephemeral=True)
        
bot.run(TOKEN)
