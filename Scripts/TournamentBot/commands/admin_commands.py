"""
Admin commands for TournamentBot.

This module contains commands that are intended for admin use, including
channel configuration, check-in management, and game administration.
"""
import discord
from discord import app_commands
import os
import sys
from typing import List, Optional
from dotenv import find_dotenv, set_key

# First add the parent directory (TournamentBot) to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Then add the Scripts directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import from local package using relative paths
from ..utils import helpers
from ..ui.check_in import StartGameView

import databaseManager

def setup_admin_commands(bot, MY_GUILD):
    """
    Set up admin commands for the bot.
    
    Args:
        bot: Discord bot instance
        MY_GUILD: Guild to register commands in
    """
    
    @bot.tree.command(
        name="createadminchannel",
        description="Set the current channel as the admin channel for game management",
        guild=MY_GUILD
    )
    async def create_admin_channel(interaction: discord.Interaction):
        """Sets the current channel as the admin channel for tournament management."""
        # Check if user has admin permissions
        if not helpers.has_admin_permission(interaction.user):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return
            
        channel_id = str(interaction.channel.id)
        os.environ["ADMIN_CHANNEL"] = channel_id
        dotenv_path = find_dotenv()
        set_key(dotenv_path, "ADMIN_CHANNEL", channel_id)
        await interaction.response.send_message(
            f"Admin channel set to {interaction.channel.mention}.",
            ephemeral=True
        )

    @bot.tree.command(
        name="checkin",
        description="Start a check-in process for a game",
        guild=MY_GUILD
    )
    async def checkin(interaction: discord.Interaction):
        """Command to start a check-in process for a game."""
        # Check if user has admin permissions
        if not helpers.has_admin_permission(interaction.user):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Permission Error",
                    description="You don't have permission to use this command.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return
        
        # Check if command is run in admin channel
        admin_channel_id = os.getenv("ADMIN_CHANNEL")
        if admin_channel_id and str(interaction.channel.id) == admin_channel_id:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Invalid Channel",
                    description="Check-in commands cannot be run in the admin channel.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return
            
        # Import the global variable
        import Scripts.TournamentBot.main as main_module
        
        # Check if there is an existing check-in active
        if main_module.current_checkin_view is not None:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Check-in Already Active",
                    description="There is already an active check-in session. Please complete or cancel it before starting a new one.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        # Verify admin channel
        admin_channel_id = os.getenv("ADMIN_CHANNEL")
        if not admin_channel_id:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Configuration Error",
                    description="Admin channel not set. Please run the createAdminChannel command first.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return
            
        admin_channel = interaction.guild.get_channel(int(admin_channel_id))
        if not admin_channel:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Configuration Error",
                    description="Admin channel not found. Please run the createAdminChannel command again.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return
        
        # Create the check-in embed
        embed = discord.Embed(
            title="Game Check-in",
            description="Click the buttons below to check in for the game!",
            color=helpers.COLOR_BLUE
        )
        
        embed.add_field(
            name="Checked-in Players (0)",
            value="No players checked in yet",
            inline=False
        )
        
        embed.set_footer(text="A minimum of 10 players is required to start a game")
        
        # Create the check-in view and store it in the global variable
        view = StartGameView(interaction.user.id)
        main_module.current_checkin_view = view
        
        # Send the check-in view to the current channel
        await interaction.response.send_message(embed=embed, view=view)
        
        # Store the channel where check-in is happening
        view.channel = interaction.channel
        
        # Create and send Phase 1 Global Controls to the admin channel
        # Import the necessary view
        from ..ui.game_control import GlobalPhasedControlView
        
        # Create Phase 1 view (Start Game / Cancel Game)
        phase1_view = GlobalPhasedControlView.create_phase1_view()
        
        # Create embed for global controls
        gc_embed = discord.Embed(
            title="Global Controls (Game Setup)",
            description="Click 'Start Game' to begin the game session or 'Cancel Game' to cancel.",
            color=discord.Color.blue()
        )
        
        # Send global controls message to admin channel
        await admin_channel.send(
            embed=gc_embed,
            view=phase1_view
        )

    @bot.tree.command(
        name="force_check_in",
        description="Force check-in users by their ID range (Admin only)",
        guild=MY_GUILD
    )
    async def force_check_in(interaction: discord.Interaction, start_id: int, end_id: int):
        """
        Forcefully check in a range of users by their ID.
        Useful for testing with a small group of fake users.
        
        Args:
            interaction: Discord interaction
            start_id: Starting ID in the range
            end_id: Ending ID in the range
        """
        # Check if user has admin permissions
        if not helpers.has_admin_permission(interaction.user):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Permission Error",
                    description="You don't have permission to use this command.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return
        
        # Check if command is run in admin channel
        admin_channel_id = os.getenv("ADMIN_CHANNEL")
        if admin_channel_id and str(interaction.channel.id) == admin_channel_id:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Invalid Channel",
                    description="Check-in commands cannot be run in the admin channel.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return
            
        # Import the global variable
        import Scripts.TournamentBot.main as main_module
        
        # Check if there is an existing check-in active
        if main_module.current_checkin_view is not None:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="Check-in Already Active",
                    description="There is already an active check-in session. Please complete or cancel it before starting a new one.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return
            
        await interaction.response.defer(ephemeral=True)
        
        # Create a check-in view
        embed = discord.Embed(
            title="Game Check-in (Force)",
            description="Forced check-in is active!",
            color=helpers.COLOR_BLUE
        )
        
        view = StartGameView(interaction.user.id)
        main_module.current_checkin_view = view
        
        # Add dummy members to the check-in list
        from Scripts.TournamentBot.ui.check_in import DummyMember
        for i in range(start_id, end_id + 1):
            view.checked_in_users.append(DummyMember(i))
        
        # Update the embed with the user list
        user_list = []
        for i, user in enumerate(view.checked_in_users):
            user_list.append(f"{i+1}. {user.mention}")
        
        if user_list:
            embed.add_field(
                name=f"Checked-in Players ({len(view.checked_in_users)})",
                value="\n".join(user_list),
                inline=False
            )
        # Send the check-in message
        message = await interaction.channel.send(embed=embed, view=view)
        
        # Store the channel where check-in is happening
        view.channel = interaction.channel
        
        
        # Create and send Phase 1 Global Controls to the admin channel
        # Import the necessary view
        from ..ui.game_control import GlobalPhasedControlView
        
        # Create Phase 1 view (Start Game / Cancel Game)
        phase1_view = GlobalPhasedControlView.create_phase1_view()
        
        # Create embed for global controls
        gc_embed = discord.Embed(
            title="Global Controls (Game Setup)",
            description="Click 'Start Game' to begin the game session or 'Cancel Game' to cancel.",
            color=discord.Color.blue()
        )
        
        # Send global controls message to admin channel
        admin_channel = interaction.guild.get_channel(int(admin_channel_id))
        await admin_channel.send(
            embed=gc_embed,
            view=phase1_view
        )
        
        await interaction.followup.send(
            embed=discord.Embed(
                title="Force Check-in Complete",
                description=f"Force-checked in {len(view.checked_in_users)} users.",
                color=helpers.COLOR_GREEN
            ),
            ephemeral=True
        )
    
    @bot.tree.command(
        name="toxicity",
        description="Update the toxicity points of a user based on their Discord ID",
        guild=MY_GUILD
    )
    async def update_toxicity_command(interaction: discord.Interaction, discord_id: str):
        """
        Updates toxicity points for a player based on their Discord ID.
        
        Args:
            interaction: Discord interaction
            discord_id: Discord ID of the player to update toxicity for
        """
        # Check if user has admin permissions
        if not helpers.has_admin_permission(interaction.user):
            await interaction.response.send_message(
                "You don't have permission to use this command.",
                ephemeral=True
            )
            return
            
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