import json
import argparse
import os
import math 
import random

import src.okey.statistics.statistics as stats

with open(os.path.join(os.path.dirname(__file__),"src", "okey", "statistics", "playerStats.json"), "r", encoding="utf-8") as f:
    players = json.load(f)

def find_player_by_slug(slug):
    for player in players:
        name = player.get("name", "")
        if name and slug == name.lower().replace(" ", ""):
            return player
    return None


def main():
    parser = argparse.ArgumentParser(description="Players and teams statistics")
    parser.add_argument("-p", "--player", type=str, help="Select a specific player")
    parser.add_argument("-t", "--team", type=str, help="Select a specific team")
    parser.add_argument("-e", "--express", action="store_false", help="Run in express mode with minimal output")
    parser.add_argument("-A", "--ascii", action="store_true", help="Display full ascii art")
    parser.add_argument("-f", "--fivelast", action="store_true", help="View the last 5 games of the player")
    parser.add_argument("-a", "--awards", action="store_true", help="Display player awards")
    args = parser.parse_args()

    if args.player:
        player_slug = args.player.lower().replace(" ", "")
        player = find_player_by_slug(player_slug)
        if not player:
            print(f"[❌] Player '{args.player}' not found.")
            return

        stats.print_player_ascii(player_slug, full_size=args.ascii)
        print("===============================================")

        if args.fivelast == True:
            print(stats.last_5_stats(player_slug))

        if args.awards:
            print(stats.player_awards(player_slug))

    if args.team:
        team_slug = args.team.lower().replace(" ", "")
        team = stats.get_team_by_slug(team_slug)
        
        print("\n")
        

if __name__ == "__main__":
    main()

