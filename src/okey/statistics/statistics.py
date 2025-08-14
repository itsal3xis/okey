import os
import json
import io
from PIL import Image
import ascii_magic


IMAGES_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "images"))


PLAYERS_JSON_PATH = os.path.join(os.path.dirname(__file__), "playerStats.json")

def load_player_filenames():
    """Load playerStats.json and create a dict slug -> filename"""
    with open(PLAYERS_JSON_PATH, encoding="utf-8") as f:
        players = json.load(f)

    slug_to_filename = {}
    for p in players:
        full_name = p["name"]
        slug = full_name.replace(" ", "").lower()
        filename = full_name.lower().replace(" ", "_") + ".png"
        slug_to_filename[slug] = filename
    return slug_to_filename

def print_player_ascii(player_slug: str, full_size=False):
    """Return the ASCII art of a player image based on their slug."""
    slug_to_filename = load_player_filenames()

    if player_slug not in slug_to_filename:
        print(f"[❌]Player not found in the json file : {player_slug}")
        return

    file_name = slug_to_filename[player_slug]
    file_path = os.path.join(IMAGES_FOLDER, file_name)

    if not os.path.exists(file_path):
        print(f"[❌] Image not found for the player '{player_slug}' : {file_path}")
        return

    try:

        target_width = 40
        target_height = 15

        if full_size:
            target_width = 100
            target_height = 30

        img = Image.open(file_path)
        img = img.resize((target_width, target_height))

        art = None
        temp_path = None

        # 1) Try directly with PIL.Image
        try:
            art = ascii_magic.from_image(img)
        except Exception:
            art = None

        # 2) If that fails, save to temp file and try file-based methods
        if art is None:
            temp_path = os.path.join(IMAGES_FOLDER, ".tmp_resized_for_ascii.png")
            img.save(temp_path)

            if hasattr(ascii_magic, "from_image_file"):
                art = ascii_magic.from_image_file(temp_path)
            else:
                try:
                    art = ascii_magic.from_image(temp_path)
                except Exception:
                    buffer = io.BytesIO()
                    img.save(buffer, format="PNG")
                    buffer.seek(0)
                    art = ascii_magic.from_image(buffer)

        # 3) Print ASCII art
        try:
            if hasattr(art, "to_terminal"):
                try:
                    art.to_terminal(columns=target_width, width_ratio=1)
                except TypeError:
                    art.to_terminal()
            else:
                try:
                    ascii_magic.to_terminal(art, columns=target_width, width_ratio=1)
                except TypeError:
                    print(str(art))
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    except Exception as e:
        print(f"[⚠] Error with the image {file_name} : {e}")

def last_5_stats(player_slug: str):
    """Return the last 5 stats of a player."""
    with open(PLAYERS_JSON_PATH, encoding="utf-8") as f:
        players = json.load(f)

    for p in players:
        full_name = p["name"]
        slug = full_name.replace(" ", "").lower()
        if slug == player_slug:
            last5 = p.get("last5Games", [])
            if not last5:
                return f"[❌] No last 5 games data available for player '{player_slug}'."
            else:
                stats_lines = [f"Last 5 games stats for {full_name}:"]
                gamesplayed = 0
                points = 0
                goals = 0
                assists = 0
                plusminus = 0
                pims = 0
                shots = 0
                for game in last5:
                    gamesplayed += 1
                    points += game.get("points", 0)
                    goals += game.get("goals", 0)
                    assists += game.get("assists", 0)
                    plusminus += game.get("plusMinus", 0)
                    pims += game.get("pims", 0)
                    shots += game.get("shots", 0)

                    stats_lines.append(
                        f"Game {gamesplayed}: Points: {game.get('points', 0)}, "
                        f"Goals: {game.get('goals', 0)}, Assists: {game.get('assists', 0)}, "
                        f"Plus/Minus: {game.get('plusMinus', 0)}, PIM: {game.get('pims', 0)}, "
                        f"Shots: {game.get('shots', 0)}"
                    )
                return (f"{stats_lines[0]}\n"f"Total Points: {points}, Goals: {goals}, Assists: {assists}, Plus/Minus: {plusminus}, PIM: {pims}, Shots: {shots}")

def player_awards(player_slug: str):
    """Return the awards of a player."""
    with open(PLAYERS_JSON_PATH, encoding="utf-8") as f:
        players = json.load(f)

    for p in players:
        full_name = p["name"]
        slug = full_name.replace(" ", "").lower()
        if slug == player_slug:
            awards = p.get("awards", [])
            if not awards:
                return f"[❌] No awards for '{player_slug}'."
            else:
                award_lines = [f"Awards for {full_name}:"]
                for award in awards:
                    award_lines.append(f"- {award}")
                return "\n".join(award_lines)
    return f"[❌] Player '{player_slug}' not found."