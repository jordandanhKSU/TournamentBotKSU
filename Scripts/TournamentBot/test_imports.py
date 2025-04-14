"""
Test script to verify all imports are working correctly.
"""
import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('TournamentBot')

# Print the Python path for debugging
print("\nPython Path:")
for path in sys.path:
    print(f"  - {path}")

# Set up the path to ensure we can import our modules
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if base_dir not in sys.path:
    sys.path.insert(0, base_dir)
    print(f"\nAdded {base_dir} to Python path")

# Test imports
print("\nTesting imports:")

try:
    print("Importing databaseManager...", end="")
    import databaseManager
    print(" SUCCESS")
except ImportError as e:
    print(f" FAILED: {e}")

try:
    print("Importing Matchmaking...", end="")
    import Matchmaking
    print(" SUCCESS")
except ImportError as e:
    print(f" FAILED: {e}")

try:
    print("Importing TournamentBot modules...")
    
    print("  - utils.helpers...", end="")
    from Scripts.TournamentBot.utils import helpers
    print(" SUCCESS")
    
    print("  - game.game_state...", end="")
    from Scripts.TournamentBot.game.game_state import GlobalGameState
    print(" SUCCESS")
    
    print("  - commands.admin_commands...", end="")
    from Scripts.TournamentBot.commands import admin_commands
    print(" SUCCESS")
    
    print("  - commands.player_commands...", end="")
    from Scripts.TournamentBot.commands import player_commands
    print(" SUCCESS")
    
    print("  - ui.check_in...", end="")
    from Scripts.TournamentBot.ui import check_in
    print(" SUCCESS")
    
    print("  - ui.game_control...", end="")
    from Scripts.TournamentBot.ui import game_control
    print(" SUCCESS")
    
    print("  - ui.role_preference...", end="")
    from Scripts.TournamentBot.ui import role_preference
    print(" SUCCESS")
    
except ImportError as e:
    print(f" FAILED: {e}")

print("\nAll tests completed")