from openpyxl import load_workbook
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv, find_dotenv
import databaseManager

load_dotenv(find_dotenv())

TOKEN = os.getenv('DISCORD_TOKEN')
SPREADSHEET_PATH = os.path.abspath(os.getenv('SPREADSHEET_PATH'))
DB_PATH = os.getenv('DB_PATH')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

global_game_state = None

class GlobalGameState:
    def __init__(self, games: list):
        self.games = games
        self.game_messages = {}
        self.selected = None
        self.swap_mode = False
        self.finalized = False

    def generate_embed(self, game_index: int) -> discord.Embed:
        game = self.games[game_index]
        embed = discord.Embed(title=f"Game {game_index+1}", color=discord.Color.blue())
        embed.add_field(name="Blue Team", value="\n".join(game["blue"]), inline=True)
        embed.add_field(name="Red Team", value="\n".join(game["red"]), inline=True)
        return embed

    async def update_all_messages(self):
        for game_index, message in self.game_messages.items():
            embed = self.generate_embed(game_index)
            view = GameControlView(self, game_index)
            try:
                await message.edit(embed=embed, view=view)
            except Exception as e:
                print(f"Failed to update message for Game {game_index+1}: {e}")

    async def handle_selection(self, interaction: discord.Interaction, game_index: int, team: str, player_index: int, player_name: str):
        if self.selected is None:
            self.selected = (game_index, team, player_index, player_name)
            await interaction.response.send_message(
                f"Selected **{player_name}** from Game {game_index+1} ({team.capitalize()} Team). Now select another player to swap.",
                ephemeral=True,
            )
        else:
            first_game_index, first_team, first_player_index, first_player_name = self.selected
            if (first_game_index, first_team, first_player_index) == (game_index, team, player_index):
                self.selected = None
                await interaction.response.send_message("Selection cancelled.", ephemeral=True)
                return
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

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await databaseManager.initialize_database()

@bot.command()
async def checkin(ctx):
    embed = discord.Embed(title="📋 Check-In List", color=discord.Color.green())
    embed.add_field(name="Checked-in Users", value="No one has checked in yet.", inline=False)
    await ctx.send(embed=embed, view=StartGameView(ctx.author.id))

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

    async def update_embed(self, interaction: discord.Interaction):
        checked_in_list = [f"{user.mention}" for user in self.checked_in_users]
        embed = interaction.message.embeds[0]
        embed.set_field_at(index=0, name="Checked-in Users", value="\n".join(checked_in_list) or "No one has checked in yet.", inline=False)
        await interaction.message.edit(embed=embed)

    @discord.ui.button(label="Start\nGame", style=discord.ButtonStyle.grey)
    async def start_game_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message("Only the creator can start the game!", ephemeral=True)
            return
        fakeDataBlue = [
            ["Player1", "Player2", "Player3", "Player4", "Player5"],
            ["Player6", "Player7", "Player8", "Player9", "Player10"],
        ]
        fakeDataRed = [
            ["Player11", "Player12", "Player13", "Player14", "Player15"],
            ["Player16", "Player17", "Player18", "Player19", "Player20"],
        ]
        games = []
        for i in range(len(fakeDataBlue)):
            games.append({"blue": fakeDataBlue[i], "red": fakeDataRed[i]})
        global global_game_state
        global_game_state = GlobalGameState(games)
        for i, game in enumerate(games):
            embed = global_game_state.generate_embed(i)
            msg = await interaction.channel.send(embed=embed, view=GameControlView(global_game_state, i))
            global_game_state.game_messages[i] = msg
        gc_embed = discord.Embed(title="Global Controls", description="Toggle swap mode or finalize games.", color=discord.Color.gold())
        await interaction.channel.send(embed=gc_embed, view=GlobalSwapControlView())
        await interaction.response.send_message("Game messages created!", ephemeral=True)

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
    def __init__(self):
        super().__init__(label="Blue Team Win", style=discord.ButtonStyle.primary)
    async def callback(self, interaction: discord.Interaction):
        embed = interaction.message.embeds[0]
        embed.add_field(name="Result", value="Blue Team Wins!", inline=False)
        for child in self.view.children:
            child.disabled = True
        await interaction.message.edit(embed=embed, view=self.view)
        await interaction.response.send_message("Blue Team declared winner.", ephemeral=True)

class RedWinButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Red Team Win", style=discord.ButtonStyle.danger)
    async def callback(self, interaction: discord.Interaction):
        embed = interaction.message.embeds[0]
        embed.add_field(name="Result", value="Red Team Wins!", inline=False)
        for child in self.view.children:
            child.disabled = True
        await interaction.message.edit(embed=embed, view=self.view)
        await interaction.response.send_message("Red Team declared winner.", ephemeral=True)

class GameControlView(discord.ui.View):
    def __init__(self, global_state: GlobalGameState, game_index: int):
        super().__init__(timeout=None)
        self.global_state = global_state
        self.game_index = game_index
        if self.global_state.swap_mode:
            blue_team = self.global_state.games[game_index]["blue"]
            for i, player in enumerate(blue_team):
                button = GamePlayerButton(game_index, "blue", i, player)
                button.row = 0
                self.add_item(button)
            red_team = self.global_state.games[game_index]["red"]
            for i, player in enumerate(red_team):
                button = GamePlayerButton(game_index, "red", i, player)
                button.row = 1
                self.add_item(button)
        if self.global_state.finalized:
            blue_win = BlueWinButton()
            blue_win.row = 2
            self.add_item(blue_win)
            red_win = RedWinButton()
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
