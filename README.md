KSU eSports Tournament Bot Documentation 

# Installation Guide 

Download the contents of the GitHub repository and locate “.env.template” file and rename it to .env. This allows us to fill several values for the Discord bot to run.  

## Generating the Discord Bot Token 

Open [Discord Developer Portal](https://discord.com/developers/applications) and create a new application. 

Click the “Bot” tab on the left and click “Reset Token”.  

Ignore the warning message and copy the token that was given. Scroll down to “Privileged Gateway Intents” and enable “Server Members Intent” which gives the bot access to the usernames of members in the server. Message Content and Presence can be left disabled unless there are future development plans with the bot.  

Copy and paste the bot token into the .env file. There should be no space between variables and equal signs. 

## Obtaining the Guild Token 

Open the Discord client and make sure “Developer Mode” is on under the “Advanced” settings tab. This allows you to copy Discord user and guild IDs. Right click on the icon of the server you want to use the bot in, then click “Copy Server ID”. Paste the ID into the “GUILD_TOKEN” in the .env file. 

## Declare Spreadsheet and Database Paths 

The template files, “PlayerStats.xlsx” and “main_db.db”, are included in the repository. Unless you want to move your spreadsheet and database files to another folder or rename them, you can leave “SPREADSHEET_PATH” and “DB_PATH” to their defaults. If you want to rename them, make sure to change them in the .env file. 

## Setting Up Riot API Key 

Visit the [Riot Games developer portal](https://developer.riotgames.com/) and make an account. Click “Register Product” and “Register Product” under “Personal API Key”. Agree with the ToS, give a name and description of what you’re using the key for, then submit the request for the key. 

Click your username in the top-right corner, click “Apps” in the drop-down menu, and should see the app listed somewhere in the dark column. Select this, and you will see a “General Info” section containing the status of your registration and an API key beginning with “RGAPI”. Copy this into “RIOT_API_KEY” in the .env file. 

## Install Dependencies 

Install the dependencies by running the following command in the same directory as the bot’s files:
```
pip3 install -r requirements.txt
```
This will download libraries that allow the program to work. 

# Adding the Discord Bot to the Server 

Return to the Discord developer portal link. In the “OAuth2” tab, select “applications.commands” and “bot” under “OAuth2 URL Generator”. Then, set “Bot Permissions” to “Administrator” under General Permissions. 

Make sure Integration Type is set to Guild Install. Copy the generated URL and add the bot to the desired server. 

# How to Run the Bot 
```
run.bat
```

If successful, you should see the bot turning its status to online or confirming that the bot is running. There is some error detection in this run.bat for some most common issue troubleshooting. 

# Configuration 

  .env file allows for bot configuration as to operate the bot it needs the Discord token, .xlsx file name, .db file name, Discord Guild ID, and Riot API Key. 

  The prefix for bot commands can be changed. (default = !) However, the commands be run with the / as the prefix. 

# Admin Permissions 

## Admin Commands 

- /createadminchannel: Set a channel to an admin channel for game management 
- /checkin: Start the check-in process for the tournament games 
- /toxicity [user_id]: Gives a player a toxicity point 

## Admin Privileges 

- Start and Cancel button: allows admins to start or cancel games 
- Swap button: allows the admins to swap players around  
- Finalize Games button: allows the admins to confirm the games with the matchmade teams 
- Start MVP Voting button: allows the admins to start MVP voting which players can pick who the MVP is in a game. 
- Skip MVP button: allows admins to skip MVP voting 
- Next Game / Re-Check-In button: restarts the tournament process 

# How to Use Bot 

## /link and /rolepreference 

Players will be required to link their Riot ID with the /link command and set their role preference with /rolepreference command. If they do not, they cannot check in and will be prompted to do these actions. 

## Check In Process 

Once the player has done both actions, they will be able to participate in the tournament games and can interact with the “Check In” and “Leave” buttons. 

Players can also use the “Volunteer” button to sit out. Players who do volunteer will be rewarded with a participation point. Players will most likely be asked to volunteer to sit out if there are not enough players to create groups of 10. 

Admins can proceed to creating games when there are at least 10 players in the queue with the “Start” button. Admins can also cancel games with the “Cancel” button. 

## Matchmaking Process 

In the admin channel, two teams will be generated per game and will assign players their lane matchup.  

Admins are allowed to use the swap functionality with the “Swap” button which allows the admins to switch players around for any minor errors or factors that the matchmaking algorithm cannot consider. Admins can swap by selecting two player buttons from either team. 

Once the admins are satisfied with the teams, they can use the “Finalize Games” button to start the matches, and it will post an embed to the player channel with the matchmade teams. 

## Post Game Interactions 

If a player were to have bad behavior, admins can use the /toxicity command to give that player a “toxicity” point. 

After a game has been completed, admins can select who won the game. An MVP voting process can start with the “Start MVP Voting” button which allows players to vote for an MVP once per game. MVP winners will be rewarded with an “MVP” point and winners of each game will be rewarded with a “win” point. Admins can choose to skip the MVP voting with the “Skip MVP” button. 

Admins can use the “Next Game / Re-Check-In” button to start the games again or switch out players with the volunteers. 

The tournament process keeps going until the “Cancel” button gets clicked in check-in. 

# Player Permissions 

## Player Commands 

  - /link: Allow players to connect their Riot ID with their Discord account 
  - /unlink: Allow players to disconnect their Riot ID with their Discord account 
  - /stats: Displays player statistics with an embed. 
  - /rolepreference: Allow players to set their role preferences.  

## Player Privileges 

  - Check In Button: Players can interact with this button to be added to a list of players. 
  - Leave Button: Players can interact with this button to leave the list. 
  - Volunteer Button: Players can interact with this button to volunteer to sit out. 
  - MVP voting: Players can vote who they think is the MVP of a game. 

# Matchmaking Algorithm 

First will take in a player list of x size, which will then sort each player in descending order from highest rank. It will then split the list into groups of 10 based on those ranks.  

For each group of 10, the algorithm will first start off with a randomized team, where each player will be assigned to one of the two teams and assigned to a random role. 

The overall "fitness" level will then be calculated for this set of teams. First it will find the overall difference in "prowess" level between the two teams. This is done by finding each player’s prowess and comparing the difference between the two players in a certain role. Then it will find how preferable the role assigned to each player is. These two factors will give an overall fitness score that shows how balanced the teams are and how many players have a preferable role.  

This will then be stored in a key to remember calculated teams.  

The algorithm will then create new teams by swapping the players in the team with other positions. These new teams will also be evaluated on a fitness level. The new team with the highest fitness (lower is better), will then be the new team that will be explored. The cycles continue until a team with a desirable fitness level is returned or it has reached a certain epoch.  

The final best determined team is then returned to be used in the tournament 

# Known Bugs 
  With matchmaking, sometimes the main role is not prioritized. 

  Data from the .db file is not exported correctly. 

  Games Played are getting updated multiple times for some players 

  On a Check In List, the Check In, Leave and Volunteer sometimes do not get disabled when they are no longer needed 

# Left to be Developed 

  - Finish implementation of Docker support 
  - Add support for other games. (Riot Games’ other titles: Valorant or Teamfight Tactics) 
  - Proper command to export data from the database to Google Sheets 

# Potential Issues 
  The matchmaking algorithm has issues balancing with the primary role preferences in mind. The algorithm has trouble prioritizing player role preferences and decides to be optimized for their secondary or tertiary roles. 

  Riot Games API key has problems with not being able to operate under KSU Wi-Fi. 

  Riot Games API key needs to be regenerated every 24 hours.  
