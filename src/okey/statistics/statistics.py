import os
import json
import io
from PIL import Image
import ascii_magic

# Chemin vers dossier images
IMAGES_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "images"))

# Chemin vers JSON joueurs
PLAYERS_JSON_PATH = os.path.join(os.path.dirname(__file__), "playerStats.json")

def load_player_filenames():
    """Charge playerStats.json et crée un dict slug -> filename"""
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
    """Affiche l'image ASCII du joueur donné par son slug"""
    slug_to_filename = load_player_filenames()

    if player_slug not in slug_to_filename:
        print(f"[❌] Joueur introuvable dans la liste JSON : {player_slug}")
        return

    file_name = slug_to_filename[player_slug]
    file_path = os.path.join(IMAGES_FOLDER, file_name)

    if not os.path.exists(file_path):
        print(f"[❌] Image introuvable pour le joueur '{player_slug}' : {file_path}")
        return

    try:
        # Force 60x60 pixels
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
        print(f"[⚠] Erreur avec l'image {file_name} : {e}")

if __name__ == "__main__":
    # Exemple d'utilisation
    print_player_ascii("lanehutson")
