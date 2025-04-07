"""
Command handlers for TournamentBot.

This module contains the Discord slash commands for the TournamentBot,
organized into administrative and player-facing commands.
"""

def register_all_commands(bot, guild):
    """
    Register all commands with the bot.
    
    Args:
        bot: Discord bot instance
        guild: Guild to register commands in
    """
    # Import inline to avoid circular imports
    from .admin_commands import setup_admin_commands
    from .player_commands import setup_player_commands
    
    setup_admin_commands(bot, guild)
    setup_player_commands(bot, guild)
