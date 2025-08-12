import json
import argparse
import os
import math 
import random


with open(os.path.join(os.path.dirname(__file__), "statistics", "playerStats.json"), "r", encoding="utf-8") as f:
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
    parser.add_argument("-e", "--express", action="store_true", help="Run in express mode with minimal output")
    args = parser.parse_args()


if __name__ == "__main__":
    main()

