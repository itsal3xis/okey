import os
import json
import requests

# Chemin absolu vers le JSON à partir de ce fichier
JSON_FILE = os.path.join(
    os.path.dirname(__file__),  # /src/okey/collector
    "..",                       # remonte à /src/okey
    "statistics",               # va dans statistics
    "playerStats.json"          # fichier
)

# Normalise le chemin
JSON_FILE = os.path.abspath(JSON_FILE)

OUTPUT_FOLDER = os.path.join(os.path.dirname(__file__), "..", "images")
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

with open(JSON_FILE, "r", encoding="utf-8") as f:
    players = json.load(f)

for player in players:
    name = player.get("name")
    img_url = player.get("headshot")

    if not name or not img_url:
        print(f"[⚠] Joueur sans nom ou image : {player}")
        continue

    try:
        response = requests.get(img_url, stream=True, timeout=10)
        response.raise_for_status()

        safe_name = name.lower().replace(" ", "_").replace("-", "_")
        file_path = os.path.join(OUTPUT_FOLDER, f"{safe_name}.png")

        with open(file_path, "wb") as img_file:
            for chunk in response.iter_content(1024):
                img_file.write(chunk)

        print(f"[✔] {name} → {file_path}")

    except Exception as e:
        print(f"[❌] Erreur pour {name} ({img_url}): {e}")
