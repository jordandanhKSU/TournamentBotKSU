import random
import math

rank_weight = 1.0
tier_weight = 5.0
role_weight = .6
win_rate_weight = .1

# 1 = role prio on, 0 = role prio off
role_prio = 1

ranks = ["iron", "bronze", "silver", "gold", "plat", "emerald", "diamond", "master", "grandmaster", "challenger"]
roles = ["Top", "Jungle", "Mid", "Bot", "Supp"]


rank_tiers = {r: len(ranks) - i for i, r in enumerate(ranks)}

explored = 0

# Player object that stores information
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
        role_factor = 5/(self.get_assigned_role_pref())
        prowess = (((5 - self.tier) * tier_weight) + (self.win_rate * win_rate_weight) + (role_factor * role_weight))
        return round(prowess, 2)

    def get_tier(self):
        return self.tier
    
    def get_assigned_role_pref(self):
        return self.role_pref[self.assigned_role]
        
# Matchmaking Algo
def matchmaking(players):
    global role_prio
    role_prio = 1
    best_teams, min_team_diff = explore_teams(players)
    
    # Assign players to final roles
    team1, team2 = best_teams[0], best_teams[1]
    for i in range(5):
        team1[i].set_assigned_role(i)
        team2[i].set_assigned_role(i)
    
    print("\nFinal Best Teams:")
    print_team(best_teams[0], "Team 1")
    print_team(best_teams[1], "Team 2")
    print(f"Final Team Prowess Difference: {min_team_diff}")
    print(explored)

def explore_teams(players):
    min_team_diff = math.inf
    visited = set()
    explored = 0
    best_teams = []
    while(min_team_diff > 20 and explored < 50):
        random.shuffle(players)
        team1, team2 = players[:5], players[5:]
        curr_teams, curr_team_diff = explore(team1, team2, visited)
        if curr_team_diff < min_team_diff:
            min_team_diff = curr_team_diff
            best_teams = curr_teams
        explored += 1
    return best_teams, min_team_diff

def explore(team1, team2, visited):
    global explored
    explored += 1

    # Assign roles
    for i in range(5):
        team1[i].set_assigned_role(i)
        team2[i].set_assigned_role(i)


    min_team_diff = fitness(team1, team2)
    best_teams = (team1[:], team2[:])

    # Tracks different configs of teams
    teams = tuple(team1 + team2)
    if teams in visited:
        return best_teams, min_team_diff
    visited.add(teams)

    # Find role with highest diff
    # role_diffs = [abs(team1[i].calc_prowess() - team2[i].calc_prowess()) for i in range(5)]
    # print(role_diffs)
    
    # swap lane with every other player on same team
    for i in range(5):
        for j in range(i+1, 5):
            if i == j:
                continue  # Skip the same role

            new_team1, new_team2 = team1, team2
            new_team1[j], new_team1[i] = new_team1[i], new_team1[j]

            new_diff = fitness(new_team1, team2)
            
            if new_diff < min_team_diff:
                min_team_diff = new_diff
                best_teams = (new_team1[:], new_team2[:])

                # Recursively explore 
                best_teams, min_team_diff = explore(new_team1, new_team2, visited)
            
            new_team2[j], new_team2[i] = new_team2[i], new_team2[j]
            
            new_diff = fitness(team1, new_team2)
            
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
            

            new_diff = fitness(new_team1, new_team2)

            if new_diff < min_team_diff:
                min_team_diff = new_diff
                best_teams = (new_team1[:], new_team2[:])
                best_teams, min_team_diff = explore(new_team1, new_team2, visited)
            
            new_team2[j], new_team1[i] = new_team1[i], new_team2[j]
            new_diff = fitness(new_team1, new_team2)

            if new_diff < min_team_diff:
                min_team_diff = new_diff
                best_teams = (new_team1[:], new_team2[:])
                best_teams, min_team_diff = explore(new_team1, new_team2, visited)
            
    return best_teams, min_team_diff



def fitness(team1, team2):
    global role_prio
    diff = 0
    for x in range(5):
        diff += abs(team1[x].calc_prowess() - team2[x].calc_prowess())
    
    if role_prio == 1:
        for x in range(5):
            diff += team1[x].get_assigned_role_pref() + team2[x].get_assigned_role_pref()
    return diff

def print_team(team, name):
    print(f"\n{name}:")
    for player in team:
        print(f"{player.user_id}, {player.rank}, {player.role_pref}, {roles[player.assigned_role]}, {player.calc_prowess()}")

player_list = list()

role_pref = [1, 2, 3, 4, 5]

# Testing to generate players
for x in range(10):
    random.shuffle(role_pref)
    player_list.append(Player("p"+str(x+1), random.choice(ranks), role_pref[:], random.uniform(0.0, 1.0)))

# Run the matchmaking
matchmaking(player_list)






