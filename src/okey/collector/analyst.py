import json

with open("src/nhlfantasy/logic/statistics/playerStats.json", "r") as f:
    players = json.load(f)


def player_stats(player_name):
    """
    Return the stats for a specific player, including last 5 games if available
    """
    for player in players:
        if player.get("name") == player_name and player.get("position") != "G":
            return {
                "team": player.get("team"),
                "position": player.get("position"),
                "gamesPlayed": player.get("gamesPlayed"),
                "goals": player.get("goals"),
                "assists": player.get("assists"),
                "points": player.get("points"),
                "plusMinus": player.get("plusMinus"),
                "shots": player.get("shots"),
                "pim": player.get("pim"),
                "powerPlayGoals": player.get("powerPlayGoals"),
                "powerPlayPoints": player.get("powerPlayPoints"),
                "shorthandedGoals": player.get("shorthandedGoals"),
                "shorthandedPoints": player.get("shorthandedPoints"),
                "gameWinningGoals": player.get("gameWinningGoals"),
                "otGoals": player.get("otGoals"),
                "shootingPctg": player.get("shootingPctg"),
                
                "last5Games": player.get("last5Games", []),
                
                "careerGamesPlayed": player.get("careerGamesPlayed"),
                "careerGoals": player.get("careerGoals"),
                "careerAssists": player.get("careerAssists"),
                "careerPoints": player.get("careerPoints"),

                #This season playoff stats
                "playoffGamesPlayed": player.get("playoffGamesPlayed"),
                "playoffGoals": player.get("playoffGoals"),
                "playoffAssists": player.get("playoffAssists"),
                "playoffPoints": player.get("playoffPoints"),
            }
    return None

def player_points(player_name):
    """
    Return the fantasy points for a specific player
    """
    
    player_stats = player_stats(player_name)

    if player_stats is None:
        return None
    
    if player_stats.get("position") == "G":
        pass
    points = player_stats.get("points", 0)
    goals = player_stats.get("goals", 0)
    assists = player_stats.get("assists", 0)
    plus_minus = player_stats.get("plusMinus", 0)
    shots = player_stats.get("shots", 0)
    pim = player_stats.get("pim", 0)
    power_play_goals = player_stats.get("powerPlayGoals", 0)
    power_play_points = player_stats.get("powerPlayPoints", 0)
    shorthanded_goals = player_stats.get("shorthandedGoals", 0)
    shorthanded_points = player_stats.get("shorthandedPoints", 0)
    game_winning_goals = player_stats.get("gameWinningGoals", 0)
    ot_goals = player_stats.get("otGoals", 0)
    shooting_pctg = player_stats.get("shootingPctg", 0)
    career_points = player_stats.get("careerPoints", 0)
    career_goals = player_stats.get("careerGoals", 0)
    career_assists = player_stats.get("careerAssists", 0)
    career_games_played = player_stats.get("careerGamesPlayed", 0)
    playoff_points = player_stats.get("playoffPoints", 0)
    playoff_goals = player_stats.get("playoffGoals", 0)
    playoff_assists = player_stats.get("playoffAssists", 0)
    playoff_games_played = player_stats.get("playoffGamesPlayed", 0)
    last_5_games = player_stats.get("last5Games", [])


    





