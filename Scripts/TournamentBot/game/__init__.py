"""
Game state management for TournamentBot.

This module provides the game state management functionality for the TournamentBot,
including team assignment, MVP voting, and game progression.
"""

def get_game_state():
    """
    Get the current game state singleton instance.
    
    Returns:
        The global game state instance
    """
    # Import inline to avoid circular imports
    from .game_state import GlobalGameState
    return GlobalGameState.get_instance()
