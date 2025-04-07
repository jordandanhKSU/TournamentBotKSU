# Import Structure Guide for TournamentBot

This guide explains the import strategy used in the refactored TournamentBot codebase.

## Import Strategy

We've implemented a simplified, robust import strategy to avoid issues:

1. **Absolute Imports in Main Module**: The main entry point uses absolute imports with explicit paths:
   ```python
   from Scripts.TournamentBot.commands.admin_commands import setup_admin_commands
   from Scripts.TournamentBot.commands.player_commands import setup_player_commands
   from Scripts.TournamentBot.game.game_state import GlobalGameState
   ```

2. **Relative Imports in Submodules**: Submodules use relative imports to avoid path issues:
   ```python
   from ..utils import helpers
   from ..game.game_state import GlobalGameState
   ```

3. **Inline Imports for Circularity Prevention**: When circular imports might occur, we use inline imports:
   ```python
   def get_game_state():
       from .game_state import GlobalGameState
       return GlobalGameState.get_instance()
   ```

## Path Configuration

We set up Python's path in two ways:

1. **In Code**: Each module sets up the Python path:
   ```python
   # Add the parent directory (Scripts) to path
   sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
   ```

2. **Environment Variable**: The run_refactored.bat script sets PYTHONPATH to include the project root:
   ```batch
   set PYTHONPATH=%PYTHONPATH%;%CD%
   ```

## __init__.py Files

Each package directory contains an `__init__.py` file that:
1. Marks the directory as a Python package
2. Provides documentation about the package
3. Optionally exports key components for easier importing

## Common Import Issues

### 1. Null Bytes Error

If you see this error:
```
SyntaxError: source code string cannot contain null bytes
```

This occurs when Python files contain null characters (0x00). Our run_refactored.bat script detects these issues and helps fix them.

Solutions:
- Run the enhanced batch file which detects null bytes
- Recreate any affected files from scratch
- Use a hex editor to remove null bytes (typically shown as 00)

### 2. Module Not Found Errors

If you see this error:
```
ModuleNotFoundError: No module named 'Scripts.TournamentBot'
```

Ensure PYTHONPATH includes the project root:
```batch
set PYTHONPATH=%PYTHONPATH%;C:\path\to\TournamentBotKSU
```

### 3. Circular Imports

If you encounter circular import errors, use one of these strategies:
- Move the import inside a function
- Use import statements at the point of use
- Restructure your code to eliminate the circularity

## Import Examples

### Main Module (main.py)

```python
# Add the parent directory (Scripts) to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Absolute imports with explicit paths
from Scripts.TournamentBot.commands.admin_commands import setup_admin_commands
from Scripts.TournamentBot.commands.player_commands import setup_player_commands
from Scripts.TournamentBot.game.game_state import GlobalGameState

# Import parent modules
import databaseManager
import Matchmaking
```

### Submodule (game/game_state.py)

```python
# Add parent directories to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Relative imports from the package
from ..utils import helpers

# Parent directory imports
import databaseManager
import Matchmaking
```

## Run Script

Our enhanced run_refactored.bat:
1. Sets PYTHONPATH correctly
2. Checks for null bytes in Python files
3. Verifies dependencies are installed
4. Provides detailed error handling and troubleshooting