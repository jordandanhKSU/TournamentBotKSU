import random
import math

# Weights for calculating player prowess
rank_weight = 1.0
tier_weight = 5.0
role_weight = 0.6
win_rate_weight = 0.1

# 1 = role prio on, 0 = role prio off
role_prio = 1

ranks = ["iron", "bronze", "silver", "gold", "plat", "emerald", "diamond", "master", "grandmaster", "challenger"]
roles = ["Top", "Jungle", "Mid", "Bot", "Supp"]

rank_tiers = {r: len(ranks) - i for i, r in enumerate(ranks)}

# Original Player class 
class Player:
    def __init__(self, discord_id, username, player_riot_id, participation, wins, mvps,
                 toxicity_points, games_played, win_rate, total_points, tier, rank, role_preference):
        self.discord_id = discord_id
        self.username = username
        self.player_riot_id = player_riot_id
        self.participation = participation
        self.wins = wins
        self.mvps = mvps
        self.toxicity_points = toxicity_points
        self.games_played = games_played
        self.win_rate = win_rate
        self.total_points = total_points
        self.tier = tier
        self.rank = rank
        self.role_preference = role_preference

# Adapter wraps a player and supplies the matchmaking-specific functionality.
class PlayerAdapter:
    def __init__(self, player):
        self.player = player
        # Check that the player has the required attributes.
        if not hasattr(self.player, 'role_preference'):
            raise ValueError(f"Player {getattr(self.player, 'discord_id', 'unknown')} is missing required 'role_preference'")
        if not hasattr(self.player, 'tier'):
            raise ValueError(f"Player {getattr(self.player, 'discord_id', 'unknown')} is missing required 'tier'")
        # Ensure assigned_role exists.
        if not hasattr(self.player, 'assigned_role'):
            self.player.assigned_role = None

    def __getattr__(self, attr):
        # Delegate attribute access to the wrapped player object.
        return getattr(self.player, attr)

    def set_assigned_role(self, assigned_role):
        self.player.assigned_role = assigned_role

    def get_assigned_role_pref(self):
        if self.player.assigned_role is None:
            raise ValueError("assigned_role is not set for player " + str(self.player.discord_id))
        return self.player.role_preference[self.player.assigned_role]

    def get_tier(self):
        return self.player.tier

    def calc_prowess(self):
        win_rate_val = self.win_rate if self.win_rate is not None else 0.0
        role_factor = 5 / self.get_assigned_role_pref()
        prowess = (((5 - self.get_tier()) * tier_weight) +
                   (win_rate_val * win_rate_weight) +
                   (role_factor * role_weight))
        return round(prowess, 2)


def iterative_explore(team1, team2, max_iterations=1000):
    """
    Uses a stack to iteratively explore neighboring configurations.
    Each state is a tuple (team1, team2) where team1 and team2 are lists of 5 PlayerAdapters.
    Returns the best team configuration and its fitness.
    """
    # Ensure that each player in the initial teams has an assigned role.
    for i in range(5):
        team1[i].set_assigned_role(i)
        team2[i].set_assigned_role(i)

    best_teams = (team1[:], team2[:])
    best_fitness = fitness(team1, team2)
    visited = set()
    # Represent state as tuple of discord_ids.
    initial_state_key = tuple(p.discord_id for p in team1 + team2)
    visited.add(initial_state_key)
    stack = [(team1[:], team2[:])]
    iterations = 0

    while stack and iterations < max_iterations:
        current_team1, current_team2 = stack.pop()
        current_fit = fitness(current_team1, current_team2)
        if current_fit < best_fitness:
            best_fitness = current_fit
            best_teams = (current_team1[:], current_team2[:])
        # Generate neighbors by swapping roles within team1.
        for i in range(5):
            for j in range(i+1, 5):
                new_team1 = current_team1[:]
                new_team2 = current_team2[:]  # unchanged
                new_team1[i], new_team1[j] = new_team1[j], new_team1[i]
                state_key = tuple(p.discord_id for p in new_team1 + new_team2)
                if state_key not in visited:
                    visited.add(state_key)
                    new_fit = fitness(new_team1, new_team2)
                    if new_fit < best_fitness:
                        best_fitness = new_fit
                        best_teams = (new_team1[:], new_team2[:])
                    stack.append((new_team1, new_team2))
        # Generate neighbors by swapping roles within team2.
        for i in range(5):
            for j in range(i+1, 5):
                new_team1 = current_team1[:]
                new_team2 = current_team2[:]
                new_team2[i], new_team2[j] = new_team2[j], new_team2[i]
                state_key = tuple(p.discord_id for p in new_team1 + new_team2)
                if state_key not in visited:
                    visited.add(state_key)
                    new_fit = fitness(new_team1, new_team2)
                    if new_fit < best_fitness:
                        best_fitness = new_fit
                        best_teams = (new_team1[:], new_team2[:])
                    stack.append((new_team1, new_team2))
        # Generate neighbors by swapping players between teams.
        for i in range(5):
            for j in range(5):
                new_team1 = current_team1[:]
                new_team2 = current_team2[:]
                new_team1[i], new_team2[j] = new_team2[j], new_team1[i]
                state_key = tuple(p.discord_id for p in new_team1 + new_team2)
                if state_key not in visited:
                    visited.add(state_key)
                    new_fit = fitness(new_team1, new_team2)
                    if new_fit < best_fitness:
                        best_fitness = new_fit
                        best_teams = (new_team1[:], new_team2[:])
                    stack.append((new_team1, new_team2))
        iterations += 1

    return best_teams, best_fitness

def explore_teams(players):
    # Assume players is a list of 10 PlayerAdapters.
    team1, team2 = players[:5], players[5:]
    # Use the iterative approach to search for a better configuration.
    return iterative_explore(team1, team2)

def fitness(team1, team2):
    global role_prio
    diff = 0
    # Sum differences in calculated prowess for corresponding roles.
    for x in range(5):
        diff += abs(team1[x].calc_prowess() - team2[x].calc_prowess())
    # Add penalty based on role preferences if role priority is enabled.
    if role_prio == 1:
        for x in range(5):
            diff += team1[x].get_assigned_role_pref() + team2[x].get_assigned_role_pref()
    return diff

def print_team(team, name):
    print(f"\n{name}:")
    for player in team:
        role = roles[player.assigned_role] if player.assigned_role is not None else "Unassigned"
        print(f"{player.discord_id} ({player.username}), {player.rank}, Pref: {player.role_preference}, Role: {role}, Prowess: {player.calc_prowess()}")

def matchmaking(players):
    """
    Runs matchmaking on a list of 10 players (wrapped as PlayerAdapters).
    Returns a tuple (blue_team, red_team), each being a list of 5 players.
    """
    global role_prio
    role_prio = 1
    best_teams, min_team_diff = explore_teams(players)

    # Assign final roles based on index position.
    blue_team, red_team = best_teams[0], best_teams[1]
    for i in range(5):
        blue_team[i].set_assigned_role(i)
        red_team[i].set_assigned_role(i)

    print("\nFinal Best Teams:")
    print_team(blue_team, "Blue Team")
    print_team(red_team, "Red Team")
    print(f"Final Team Prowess Difference: {min_team_diff}")

    return blue_team, red_team

def matchmaking_multiple(players):
    """
    Sorts players by tier, splits them into chunks of 10, runs matchmaking on each chunk,
    and returns two lists: one list of blue teams and one list of red teams.
    """
    # Sort players by tier (ascending order)
    sorted_players = sorted(players, key=lambda p: p.tier)
    
    blue_teams = []
    red_teams = []
    # Process in chunks of 10.
    for i in range(0, len(sorted_players), 10):
        chunk = sorted_players[i:i+10]
        if len(chunk) != 10:
            raise ValueError("Player list size must be a multiple of 10")
        # Wrap each player in the chunk (if not already wrapped)
        adapted_chunk = [p if isinstance(p, PlayerAdapter) else PlayerAdapter(p) for p in chunk]
        blue, red = matchmaking(adapted_chunk)
        blue_teams.append(blue)
        red_teams.append(red)
    return blue_teams, red_teams

# --- Testing with sample players ---
player_list = []

# Create 50 players
for x in range(50):
    role_pref = [1, 2, 3, 4, 5]
    random.shuffle(role_pref)
    discord_id = f"p{x+1}"
    username = f"user{x+1}"
    player_riot_id = f"riot{x+1}"
    participation = random.randint(1, 100)
    wins = random.randint(0, 50)
    mvps = random.randint(0, 10)
    toxicity_points = random.uniform(0, 10)
    games_played = random.randint(10, 100)
    win_rate = random.uniform(0.0, 1.0)
    total_points = random.randint(0, 1000)
    rank = random.choice(ranks)
    # Assign a tier based on rank.
    if rank in ["iron", "bronze", "silver"]:
        tier = 4
    elif rank in ["gold", "plat"]:
        tier = 3
    elif rank in ["emerald", "diamond", "master"]:
        tier = 2
    elif rank in ["grandmaster", "challenger"]:
        tier = 1
    else:
        tier = 4
    role_preference = role_pref[:]  # make a copy
    player_list.append(
        Player(discord_id, username, player_riot_id, participation, wins, mvps,
               toxicity_points, games_played, win_rate, total_points, tier, rank, role_preference)
    )

def main():
    # Wrap all players in a PlayerAdapter.
    adapted_players = [PlayerAdapter(p) for p in player_list]

    # Run matchmaking on the full list.
    blue_teams, red_teams = matchmaking_multiple(adapted_players)

    # blue_teams and red_teams now hold the matched teams from each chunk.
    print("\n--- Summary of Matched Teams ---")
    for i, (blue, red) in enumerate(zip(blue_teams, red_teams)):
        print(f"\nMatch {i+1}:")
        print_team(blue, "Blue Team")
        print_team(red, "Red Team")

if __name__ == '__main__':
    main()
