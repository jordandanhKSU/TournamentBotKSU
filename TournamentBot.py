import discord
from discord.ext import commands
import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

global_game_state = None
class GlobalGameState:
    def __init__(self, games: list):
        self.games = games  
        self.game_messages = {}
        self.selected = None

    def generate_embed(self, game_index: int) -> discord.Embed:
        game = self.games[game_index]
        embed = discord.Embed(title=f"Game {game_index+1}", color=discord.Color.blue())
        embed.add_field(name="Blue Team", value="\n".join(game["blue"]), inline=True)
        embed.add_field(name="Red Team", value="\n".join(game["red"]), inline=True)
        return embed

    async def update_all_messages(self):
        """Update every game message with the current team lists and new views."""
        for game_index, message in self.game_messages.items():
            embed = self.generate_embed(game_index)
            view = GameSwapView(self, game_index)
            try:
                await message.edit(embed=embed, view=view)
            except Exception as e:
                print(f"Failed to update message for Game {game_index+1}: {e}")

    async def handle_selection(
        self,
        interaction: discord.Interaction,
        game_index: int,
        team: str,
        player_index: int,
        player_name: str,
    ):
        """
        Handle a button press from any game.
        If no selection is stored, store this selection.
        If one already exists, swap the two players and update all game messages.
        """
        if self.selected is None:
            self.selected = (game_index, team, player_index, player_name)
            await interaction.response.send_message(
                f"Selected **{player_name}** from Game {game_index+1} ({team} Team). Now select another player to swap.",
                ephemeral=True,
            )
        else:
            first_game_index, first_team, first_player_index, first_player_name = self.selected
            second = (game_index, team, player_index, player_name)
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

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

@bot.command()
async def checkin(ctx):
    """Sends a check-in embed with buttons for checking in, leaving, and starting the game."""
    embed = discord.Embed(
        title="📋 Check-In List", color=discord.Color.green()
    )
    embed.add_field(
        name="Checked-in Users",
        value="No one has checked in yet.",
        inline=False,
    )
    await ctx.send(embed=embed, view=StartGameView(ctx.author.id))

class StartGameView(discord.ui.View):
    def __init__(self, creator_id: int):
        super().__init__(timeout=None)
        self.creator_id = creator_id
        self.checked_in_users = []

    @discord.ui.button(label="Check In", style=discord.ButtonStyle.green)
    async def check_in_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if any(user.id == interaction.user.id for user in self.checked_in_users):
            await interaction.response.send_message("You've already checked in!", ephemeral=True)
            return
        self.checked_in_users.append(interaction.user)
        await self.update_embed(interaction)
        await interaction.response.send_message("Successfully checked in!", ephemeral=True)

    @discord.ui.button(label="Leave", style=discord.ButtonStyle.red)
    async def leave_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if not any(user.id == interaction.user.id for user in self.checked_in_users):
            await interaction.response.send_message("You're not checked in!", ephemeral=True)
            return
        self.checked_in_users = [user for user in self.checked_in_users if user.id != interaction.user.id]
        await self.update_embed(interaction)
        await interaction.response.send_message("You've left the check-in list.", ephemeral=True)

    async def update_embed(self, interaction: discord.Interaction):
        checked_in_list = [f"{user.mention}" for user in self.checked_in_users]
        embed = interaction.message.embeds[0]
        embed.set_field_at(
            index=0,
            name="Checked-in Users",
            value="\n".join(checked_in_list) or "No one has checked in yet.",
            inline=False,
        )
        await interaction.message.edit(embed=embed)

    @discord.ui.button(label="Start\nGame", style=discord.ButtonStyle.grey)
    async def start_game_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
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
            games.append({
                "blue": fakeDataBlue[i],
                "red": fakeDataRed[i],
            })


        global global_game_state
        global_game_state = GlobalGameState(games)

        for i, game in enumerate(games):
            embed = global_game_state.generate_embed(i)
            view = GameSwapView(global_game_state, i)
            msg = await interaction.channel.send(embed=embed, view=view)
            global_game_state.game_messages[i] = msg

        await interaction.response.send_message(
            "Game messages created! You can swap players across games.", ephemeral=True
        )

class GamePlayerButton(discord.ui.Button):
    """
    A button representing a player in a specific game.
    It stores the game index, team, and player index so that the global state
    can be updated correctly when clicked.
    """
    def __init__(self, game_index: int, team: str, player_index: int, label: str):
        super().__init__(label=label, style=discord.ButtonStyle.secondary)
        self.game_index = game_index
        self.team = team
        self.player_index = player_index

    async def callback(self, interaction: discord.Interaction):
        global global_game_state
        await global_game_state.handle_selection(interaction, self.game_index, self.team, self.player_index, self.label)

class StopSwappingButton(discord.ui.Button):
    """
    A button to stop swapping for this game message.
    Disables all buttons on that message.
    """
    def __init__(self):
        super().__init__(label="Stop Swapping", style=discord.ButtonStyle.danger)

    async def callback(self, interaction: discord.Interaction):
        for child in self.view.children:
            child.disabled = True
        await interaction.response.edit_message(view=self.view)
        await interaction.followup.send("Swapping session ended for this game.", ephemeral=True)

class GameSwapView(discord.ui.View):
    """
    A view attached to an individual game message.
    It creates a button for each player (for both teams) using the global state,
    plus a Stop Swapping button.
    """
    def __init__(self, global_state: GlobalGameState, game_index: int):
        super().__init__(timeout=None)
        self.global_state = global_state
        self.game_index = game_index
        game = self.global_state.games[game_index]
        for i, player in enumerate(game["blue"]):
            self.add_item(GamePlayerButton(game_index, "blue", i, player))
        for i, player in enumerate(game["red"]):
            self.add_item(GamePlayerButton(game_index, "red", i, player))
        self.add_item(StopSwappingButton())

bot.run(TOKEN)
