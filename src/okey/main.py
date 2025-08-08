import json
import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
import argparse
import uvicorn

app = FastAPI()

with open(os.path.join(os.path.dirname(__file__), "statistics", "playerStats.json"), "r", encoding="utf-8") as f:
    players = json.load(f)

def find_player_by_slug(slug):
    for player in players:
        name = player.get("name", "")
        if name and slug == name.lower().replace(" ", ""):
            return player
    return None

def main():
    parser = argparse.ArgumentParser(description="Run the FastAPI server for player stats")
    parser.add_argument("--host", default="127.0.0.1", help="Host to run the server on")
    parser.add_argument("--port", type=int, default=8000, help="Port to run the server on")
    parser.add_argument("-e", "--express", action="store_true", help="Run in express mode with minimal output")
    args = parser.parse_args()
    uvicorn.run("main:app", host=args.host, port=args.port, reload=True)


@app.get("/players")
def get_players(team: str = Query(None, description="Filter by team")):
    if team:
        filtered = [p for p in players if p.get("team", "").lower() == team.lower()]
        return filtered
    return players

@app.get("/players/{slug}")
def get_player(slug: str):
    player = find_player_by_slug(slug)
    if player:
        return player
    raise HTTPException(status_code=404, detail="Player not found")

@app.get("/teams")
def get_teams():
    teams = sorted(set(p.get("team") for p in players if p.get("team")))
    return {"teams": teams}



if __name__ == "__main__":
    main()

