"""
Role preference UI components for TournamentBot.

This module provides the UI elements for setting and submitting role preferences,
including dropdown selects and buttons.
"""
import discord
from typing import List, Dict, Any, Optional, Tuple, Union
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

class RoleSelect(discord.ui.Select):
    """Dropdown select for selecting role preference (1-5)."""
    def __init__(self, role_name: str, index: int):
        """
        Initialize a role select dropdown.
        
        Args:
            role_name: Name of the role
            index: Order of this role in the list
        """
        options = [discord.SelectOption(label=str(i), value=str(i)) for i in range(1, 6)]
        super().__init__(
            placeholder=f"Select preference for {role_name}",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"role_select_{role_name}"
        )
        self.role_name = role_name
        self.order = index
        self.value = None

    async def callback(self, interaction: discord.Interaction):
        """
        Handle select menu interaction.
        
        Args:
            interaction: Discord interaction
        """
        self.value = self.values[0]
        await interaction.response.defer()


class RolePreferenceView(discord.ui.View):
    """View containing all role preference selects."""
    def __init__(self):
        """Initialize the role preference view with selects for each role."""
        super().__init__(timeout=None)
        self.roles = ["Top", "Jungle", "Mid", "Bot", "Support"]
        for index, role in enumerate(self.roles):
            self.add_item(RoleSelect(role, index))


class SubmitButton(discord.ui.Button):
    """Button for submitting role preferences."""
    def __init__(self, dropdown_msg, dropdown_view):
        """
        Initialize the submit button.
        
        Args:
            dropdown_msg: Message containing the dropdown selects
            dropdown_view: View containing the dropdown selects
        """
        super().__init__(label="Submit", style=discord.ButtonStyle.green)
        self.dropdown_msg = dropdown_msg
        self.dropdown_view = dropdown_view

    async def callback(self, interaction: discord.Interaction):
        """
        Handle button click to submit role preferences.
        
        Args:
            interaction: Discord interaction
        """
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
            await helpers.safe_respond(
                interaction,
                content=f"An error occurred while submitting preferences: {str(e)}. Please try again.",
                ephemeral=True
            )


class SubmitPreferenceView(discord.ui.View):
    """View containing the submit button for role preferences."""
    def __init__(self, dropdown_msg, dropdown_view):
        """
        Initialize the submit preference view.
        
        Args:
            dropdown_msg: Message containing the dropdown selects
            dropdown_view: View containing the dropdown selects
        """
        super().__init__(timeout=None)
        self.dropdown_msg = dropdown_msg
        self.dropdown_view = dropdown_view
        self.add_item(SubmitButton(dropdown_msg, dropdown_view))


async def create_role_preference_ui(interaction: discord.Interaction) -> None:
    """
    Create and send the role preference UI.
    
    Args:
        interaction: Discord interaction
    """
    embed = discord.Embed(
        title="Role Preference",
        description="Please select your role preference for each role.\n1 being most desirable\n5 being least desirable.",
        color=helpers.COLOR_BLUE
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
        color=helpers.COLOR_GREEN
    )
    submit_view = SubmitPreferenceView(dropdown_msg, dropdown_view)
    await interaction.followup.send(
        embed=submit_embed,
        view=submit_view,
        ephemeral=True
    )