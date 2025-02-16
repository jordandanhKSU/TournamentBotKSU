import random
import math

rank_weight = 1.0
tier_weight = 1.0
role_weight = .5
win_rate_weight = .1

ranks = ["iron", "bronze", "silver", "gold", "plat", "emerald", "diamond"]
roles = ["Top", "Jungle", "Mid", "Bot", "Supp"]

rank_tiers = {r: len(ranks) - i for i, r in enumerate(ranks)}

explored = 0

class Player:
    def __init__(self, user_id, rank, role_pref, win_rate):
        self.user_id = user_id
        self.rank = rank
        self.role_pref = role_pref
        self.win_rate = win_rate
        self.tier = self.settier()
    
    def settier(self):
        if self.rank in ["iron", "bronze", "silver"]:
            return 4
        elif self.rank in ["gold", "plat"]:
            return 3
        elif self.rank in ["emerald", "diamond", "master"]:
            return 2
        elif self.rank in ["grandmaster", "challenger"]:
            return 1
        else:
            return 4
    
    def set_assigned_role(self, assigned_role):
        self.assigned_role = assigned_role
    
    def calc_prowess(self):
        if self.assigned_role in self.role_pref:
            role_factor = 1
        else:
            role_factor = -1
        prowess = (((11 - rank_tiers[self.rank]) * rank_weight) + ((5 - self.tier) * tier_weight) + (self.win_rate * win_rate_weight) + (role_factor * role_weight))
        return round(prowess, 2)
        
# Matchmaking Algo
def matchmaking(players):
    visited = set()
    random.shuffle(players)
    team1, team2 = players[:5], players[5:]
    for i, role in enumerate(roles):
        team1[i].set_assigned_role(role)
        team2[i].set_assigned_role(role)

    

    best_teams, min_team_diff = explore(team1, team2, visited)
    
    print("\nFinal Best Teams:")
    print_team(best_teams[0], "Team 1")
    print_team(best_teams[1], "Team 2")
    print(f"Final Team Prowess Difference: {min_team_diff}")
    print(explored)

def explore(team1, team2, visited):
    global explored
    explored += 1

    # Assign roles
    for i, role in enumerate(roles):
        team1[i].set_assigned_role(role)
        team2[i].set_assigned_role(role)

    min_team_diff = calculate_team_diff(team1, team2)
    best_teams = (team1[:], team2[:])

    # Tracks different configs of teams
    teams = tuple(team1 + team2)
    if teams in visited:
        return best_teams, min_team_diff
    visited.add(teams)

    # Find role with highest diff
    role_diffs = [abs(team1[i].calc_prowess() - team2[i].calc_prowess()) for i in range(5)]
    print(role_diffs)
    
    curr_lowest_diff = math.inf
    # swap lane with every other player on same team
    for i in range(5):
        for j in range(i+1, 5):
            if i == j:
                continue  # Skip the same role

            new_team1, new_team2 = team1, team2
            new_team1[j], new_team1[i] = new_team1[i], new_team1[j]
            new_team2[j], new_team2[i] = new_team2[i], new_team2[j]

            new_diff = calculate_team_diff(new_team1, new_team2)

            if new_diff < curr_lowest_diff:
                curr_lowest_diff = new_diff
            
            if new_diff < min_team_diff:
                min_team_diff = new_diff
                best_teams = (new_team1[:], new_team2[:])

                # Recursively explore 
                best_teams, min_team_diff = explore(new_team1, new_team2, visited)
    
    # swap with different team
    for i in range(5):
        for j in range(i+1, 5):
            new_team1, new_team2 = team1, team2
            new_team1[j], new_team2[i] = new_team2[i], new_team1[j]
            new_team2[j], new_team1[i] = new_team1[i], new_team2[j]

            new_diff = calculate_team_diff(new_team1, new_team2)

            if new_diff < min_team_diff:
                min_team_diff = new_diff
                best_teams = (new_team1[:], new_team2[:])
                best_teams, min_team_diff = explore(new_team1, new_team2, visited)

    return best_teams, min_team_diff



def calculate_team_diff(team1, team2):
    diff = 0
    for x in range(5):
        diff += team1[x].calc_prowess() - team2[x].calc_prowess()
    return abs(diff)

def print_team(team, name):
    print(f"\n{name}:")
    for player in team:
        print(f"{player.user_id}, {player.rank}, {player.role_pref}, {player.assigned_role}, {player.calc_prowess()}")

player_list = list()

for x in range(10):
    player_list.append(Player("p"+str(x+1), random.choice(ranks), random.choices(roles), random.uniform(0.0, 1.0)))

matchmaking(player_list)






