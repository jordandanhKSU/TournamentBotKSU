# TournamentBot Refactored

This is a refactored version of the TournamentBot with improved code organization, readability, and maintainability.

## Directory Structure

```
Scripts/TournamentBot/
├── __init__.py
├── main.py                   # Main entry point
├── commands/                 # Command handlers
│   ├── __init__.py
│   ├── admin_commands.py     # Admin-only commands
│   └── player_commands.py    # Player-facing commands
├── ui/                       # UI components
│   ├── __init__.py
│   ├── check_in.py           # Check-in system UI
│   ├── game_control.py       # Game control and MVP voting UI
│   └── role_preference.py    # Role preference selection UI
├── game/                     # Game state management
│   ├── __init__.py
│   └── game_state.py         # GlobalGameState singleton
└── utils/                    # Utility functions
    ├── __init__.py
    └── helpers.py            # Helper functions and constants
```

## Key Improvements

1. **Modular Organization**: Code is now organized into logical modules based on functionality.
2. **Consistent Patterns**: UI components and command handlers follow consistent patterns.
3. **Improved State Management**: Game state is managed through a singleton class with clear interfaces.
4. **Better Error Handling**: Centralized error handling with helper functions.
5. **Enhanced Documentation**: Comprehensive docstrings and type hints throughout the codebase.
6. **Reduced Code Duplication**: Common functionality extracted to helper functions.

## Running the Bot

Use the `run_refactored.bat` file to start the bot:

```
run_refactored.bat
```

## Usage

The bot still supports all the same commands as before, but with a cleaner implementation:

- `/createadminchannel` - Set the current channel as the admin channel
- `/checkin` - Start a check-in process for a game
- `/stats` - Display player statistics
- `/toxicity` - Update toxicity points for a player
- `/link` - Link Discord account with Riot ID
- `/unlink` - Unlink Riot ID from Discord account
- `/rolepreference` - Set role preferences for matchmaking

## Architecture

### Game State Management

The `GlobalGameState` class in `game_state.py` manages all game-related state, including:

- Game teams and player assignments
- MVP voting status and results
- Message references for UI updates
- Player swapping functionality

This is implemented as a singleton to ensure consistent state access across the application.

### UI Components

UI components are organized by functionality:

- `check_in.py` - Handles player check-in, volunteering, and game starting
- `role_preference.py` - Manages role preference selection and submission
- `game_control.py` - Controls game results, MVP voting, and team swapping

### Command Handlers

Commands are divided into admin and player commands:

- `admin_commands.py` - Commands that require administrative permissions
- `player_commands.py` - Commands available to all players

## Development

To extend or modify the bot:

1. Add new commands to the appropriate commands file
2. Add new UI components to the UI directory
3. Update the game state as needed for new functionality
4. Add helper functions to utils/helpers.py for shared functionality

## Dependencies

The bot requires the same dependencies as the original version:

- discord.py
- python-dotenv
- aiosqlite
- aiohttp
- openpyxl