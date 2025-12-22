import json
import os
from src.okey.collector.collector import reg_season

# ANSI Colors
RESET = '\033[0m'
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
PURPLE = '\033[95m'
CYAN = '\033[96m'
WHITE = '\033[97m'
BOLD = '\033[1m'

ERROR = "ERROR"
WARNING = "WARNING"
SUCCESS = "SUCCESS"
INFO = "INFO"

ROOT = os.path.dirname(os.path.abspath(__file__))
STAT_DIR = os.path.join(ROOT, "statistics")

TODAY_PATH = os.path.join(STAT_DIR, "todayGames.json")
TEAMS_PATH = os.path.join(STAT_DIR, "teamsStats.json")
PLAYERS_PATH = os.path.join(STAT_DIR, "playerStats.json")
PKG_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMAGES_DIR = os.path.join(PKG_ROOT, "images")

def print_colored(message: str, status: int = INFO, bold: bool = False):
    """Print with color and status code"""
    colors = {
        ERROR: f"{RED}{BOLD}",
        WARNING: f"{YELLOW}{BOLD}",
        SUCCESS: f"{GREEN}{BOLD}",
        INFO: f"{CYAN}"
    }
    color = colors.get(status, '')
    end_color = RESET if bold else ''
    
    prefix = f"[{status}] " if status in [ERROR, WARNING, SUCCESS] else ''
    print(f"{color}{prefix}{message}{end_color}")

def load_json(path: str):
    if not os.path.exists(path):
        print_colored(f"Missing {path}", ERROR)
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# Stat categories
BASIC_KEYS = [
    'gamesPlayed', 'goals', 'assists', 'points', 'plusMinus', 'pim',
]
ADVANCED_KEYS = [
    'last5Games', 'careerGamesPlayed', 'careerGoals', 'careerAssists', 'careerPoints',
    'shootingPctg'
]
BIO_KEYS = ['id', 'name', 'nameKey', 'team', 'position', 'birthDate', 'sweaterNumber', 'headshot', 'heroImage', 'teamLogo', 'awards']


def extract_fields(player_data: dict, keys: list):
    """Return a dict with only the requested keys present in player_data."""
    return {k: player_data.get(k) for k in keys if k in player_data}


def _open_image_rgb(path: str):
    """Open image and return an RGB image with transparent areas composited onto black.

    This avoids white backgrounds produced by PIL.convert('RGB') when the source has alpha.
    """
    from PIL import Image as PILImage
    im = PILImage.open(path)
    try:
        if im.mode in ('RGBA', 'LA') or im.info.get('transparency') is not None:
            bg = PILImage.new('RGBA', im.size, (0, 0, 0, 255))
            im = PILImage.alpha_composite(bg, im.convert('RGBA')).convert('RGB')
        else:
            im = im.convert('RGB')
    except Exception:
        # Fallback to simple conversion
        im = im.convert('RGB')
    return im


def get_basic_stats(player_data: dict):
    return extract_fields(player_data, BASIC_KEYS)


def get_advanced_stats(player_data: dict):
    return extract_fields(player_data, ADVANCED_KEYS)


def get_bio(player_data: dict):
    return extract_fields(player_data, BIO_KEYS)


def get_stats(player_data: dict, stat_type: str = 'basic'):
    """Return stats dict for requested type."""
    if stat_type == 'basic':
        return get_basic_stats(player_data)
    if stat_type == 'advanced':
        return get_advanced_stats(player_data)
    if stat_type == 'bio':
        return get_bio(player_data)
    if stat_type == 'all':
        return player_data.copy()
    return {}


def player_info(player, stat_type: str = 'basic', print_output: bool = True):
    """Lookup player and return a dict of requested stats. Also prints when print_output=True."""
    player_name = player.lower().replace(" ", "")
    players_data = load_json(PLAYERS_PATH)
    if not players_data:
        return None

    # Search by nameKey first, then fallback to name
    found = None
    for p in players_data:
        if p.get("nameKey") == player_name or p.get("name", "").lower().replace(" ", "") == player_name:
            found = p
            break
    if not found:
        print_colored(f"Player '{player}' not found.", ERROR)
        return None

    current_season = reg_season()
    if str(found.get("season", "")) != current_season:
        print_colored(f"Player '{player}' has no stats for current season.", WARNING)

    stats = get_stats(found, stat_type)

    if print_output:
        print_colored(f"\n{found.get('name', player)} ({stat_type}) stats:", INFO, bold=True)
        if not stats:
            print("  (no stats for this category)")
        for key, value in stats.items():
            print(f"  {key}: {value}")

    return stats

def find_player(player: str):
    """Return the full player record or None."""
    player_name = player.lower().replace(" ", "")
    players_data = load_json(PLAYERS_PATH)
    if not players_data:
        return None
    for p in players_data:
        if p.get("nameKey") == player_name or p.get("name", "").lower().replace(" ", "") == player_name:
            return p
    return None


def _locate_image(player_record: dict):
    """Look for a local image using several filename variants, otherwise download headshot if available.

    Behavior:
    - Check variants: nameKey (no spaces), name with underscores, name with hyphens.
    - Prefer any existing local image and return it (case-insensitive on Windows).
    - If none found, try to download headshot/heroImage into images folder using remote basename, but don't overwrite local images.
    """
    if not os.path.exists(IMAGES_DIR):
        try:
            os.makedirs(IMAGES_DIR, exist_ok=True)
        except Exception:
            pass

    raw_name = (player_record.get("nameKey") or player_record.get("name", "")).lower()
    name_no_space = raw_name.replace(" ", "")
    name_underscore = player_record.get("name", "").lower().replace(" ", "_")
    name_hyphen = player_record.get("name", "").lower().replace(" ", "-")

    # Deterministic ordered preference: prefer underscore (user files), then nospace, then hyphen
    ordered = []
    for v in (name_underscore, name_no_space, name_hyphen):
        if v and v not in ordered:
            ordered.append(v)

    # 1) Exact match candidates (preferred, in order)
    for v in ordered:
        for ext in ("png", "jpg", "jpeg", "webp"):
            pth = os.path.join(IMAGES_DIR, f"{v}.{ext}")
            if os.path.exists(pth):
                return pth

    # 2) Any file in images directory that includes the normalized name, prefer earlier ordered variants
    try:
        for v in ordered:
            for fname in os.listdir(IMAGES_DIR):
                if v in fname.lower():
                    return os.path.join(IMAGES_DIR, fname)
    except Exception:
        pass

    # 3) Try to download the headshot if available (but avoid overwriting local files)
    url = player_record.get("headshot") or player_record.get("heroImage")
    if not url:
        return None

    try:
        import urllib.request
        from urllib.parse import urlparse
        parsed = urlparse(url)
        basename = os.path.basename(parsed.path)
        ext = os.path.splitext(basename)[1] or ".png"

        # If any local file exists that matches our naming variants, use it instead of downloading
        for v in ordered:
            for ext_check in ("png", "jpg", "jpeg", "webp"):
                existing = os.path.join(IMAGES_DIR, f"{v}.{ext_check}")
                if os.path.exists(existing):
                    return existing

        dest = os.path.join(IMAGES_DIR, basename)
        if not os.path.exists(dest):
            urllib.request.urlretrieve(url, dest)
        return dest if os.path.exists(dest) else None
    except Exception:
        return None


def _render_image_half_block(pil_image, width: int):
    """Render image using Unicode upper-half blocks '▀' with foreground=top pixel, background=bottom pixel.

    Returns ANSI string with 24-bit color escapes.
    """
    im = pil_image.convert('RGB')
    aspect = im.height / im.width
    pixel_width = max(1, width)
    pixel_height = max(1, int(pixel_width * aspect))  # full-pixel height
    im = im.resize((pixel_width, pixel_height))

    rows = []
    for y in range(0, im.height, 2):
        row = []
        for x in range(im.width):
            top = im.getpixel((x, y))
            if y + 1 < im.height:
                bottom = im.getpixel((x, y + 1))
            else:
                bottom = (0, 0, 0)
            r1, g1, b1 = top
            r2, g2, b2 = bottom
            # Use upper half block '▀' with foreground=top, background=bottom
            cell = f"\x1b[38;2;{r1};{g1};{b1}m\x1b[48;2;{r2};{g2};{b2}m▀"
            row.append(cell)
        row.append("\x1b[0m")
        rows.append(''.join(row))
    return '\n'.join(rows)


def print_player_with_image(player: str, stat_type: str = "basic", width: int = 24, print_output: bool = True, debug: bool = False, mode: str = 'auto', image_size: int | None = None):
    """Render player image on the left and stats on the right using Rich.

    Modes:
      - auto: prefer Rich.image, otherwise use half-block ANSI fallback
      - ansi: existing full-block background color with double-width spaces
      - half: improved half-block rendering (better vertical resolution)
      - braille: (not implemented) - placeholder

    When `image_size` is provided (integer), the image will be center-cropped to square then resized so the final CLI square is `image_size` characters wide and tall (small footprint). This gives the best, square result for player headshots.

    Falls back to text output if Rich/Pillow aren't installed. When `debug=True` prints diagnostics about availability and any errors.
    """
    # Track availability and errors
    rich_ok = True
    rich_err = None
    rich_image_ok = True
    rich_image_err = None
    pillow_ok = True
    pillow_err = None

    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.columns import Columns
        from rich.table import Table
        from rich.text import Text
    except Exception as e:
        rich_ok = False
        rich_err = str(e)
    try:
        from rich.image import Image as RichImage
    except Exception as e:
        rich_image_ok = False
        rich_image_err = str(e)
        RichImage = None
    try:
        import PIL
    except Exception as e:
        pillow_ok = False
        pillow_err = str(e)

    if debug:
        print_colored(f"Rich available: {rich_ok}", INFO)
        if not rich_ok:
            print_colored(f"Rich error: {rich_err}", WARNING)
        print_colored(f"Rich.image available: {rich_image_ok}", INFO)
        if not rich_image_ok:
            print_colored(f"Rich.image error: {rich_image_err}", WARNING)
        print_colored(f"Pillow available: {pillow_ok}", INFO)
        if not pillow_ok:
            print_colored(f"Pillow error: {pillow_err}", WARNING)

    if not rich_ok:
        print_colored("Rich is not available. Install with: pip install rich", WARNING)
        return player_info(player, stat_type=stat_type, print_output=print_output)
    if not pillow_ok:
        print_colored("Pillow is not available. Install with: pip install pillow", WARNING)
        return player_info(player, stat_type=stat_type, print_output=print_output)

    found = find_player(player)
    if not found:
        print_colored(f"Player '{player}' not found.", ERROR)
        return None

    stats = get_stats(found, stat_type)
    img_path = _locate_image(found)

    console = Console()

    # Left: image or placeholder
    left = None
    if img_path and os.path.exists(img_path) and RichImage is not None and mode in ('auto', 'rich'):
        # Try to open with PIL to validate image first
        try:
            from PIL import Image as PILImage
            with PILImage.open(img_path) as im:
                im.verify()  # verify image validity
        except Exception as e:
            if debug:
                print_colored(f"PIL failed to open image: {e}", WARNING)
            left = Panel(f"[bold]Image found but invalid:[/bold]\n{img_path}", height=12)
        else:
            try:
                img = RichImage(img_path, width=width)
                left = Panel(img, padding=0)
            except Exception as e:
                if debug:
                    print_colored(f"Rich failed to render image: {e}", WARNING)
                left = Panel(f"[bold]Image found but cannot render:[/bold]\n{img_path}", height=12)
    elif img_path and os.path.exists(img_path):
        # Image exists but RichImage not available; try ANSI render using Pillow as fallback
        if pillow_ok:
            try:
                from PIL import Image as PILImage
                im = PILImage.open(img_path).convert('RGB')

                # compute terminal and panel sizes so both panels end up equal
                from rich.console import Console
                console = Console()
                term_width = console.size.width if getattr(console, 'size', None) else 80
                panel_width = max(16, (term_width - 6) // 2)  # leave space between panels and borders

                # decide char width for rendering (cap to panel width)
                if image_size is not None and isinstance(image_size, int) and image_size > 0:
                    target_char_w = min(image_size, panel_width - 4)
                else:
                    target_char_w = min(width, panel_width - 4)

                if debug:
                    print_colored(f"Terminal width: {term_width}, panel_width: {panel_width}, target_char_w: {target_char_w}", INFO)

                if mode in ('half', 'auto'):
                    # If image_size is provided, crop to square and resize to (image_size x image_size*2) pixels
                    if image_size is not None and isinstance(image_size, int) and image_size > 0:
                        side = min(im.width, im.height)
                        left_crop = (im.width - side) // 2
                        top_crop = (im.height - side) // 2
                        right_crop = left_crop + side
                        bottom_crop = top_crop + side
                        if debug:
                            print_colored(f"Cropping to square {side}x{side} px and resizing to ({target_char_w},{target_char_w*2}) px", INFO)
                        im = im.crop((left_crop, top_crop, right_crop, bottom_crop))
                        im = im.resize((target_char_w, target_char_w * 2))
                        ansi = _render_image_half_block(im, width=target_char_w)
                    else:
                        ansi = _render_image_half_block(im, width=target_char_w)

                    # Use Rich Text.from_ansi so Rich renders the ANSI escapes properly inside Panel
                    try:
                        from rich.text import Text
                        ansi_text = Text.from_ansi(ansi)
                        rows = ansi.count('\n') + 1
                        left = Panel(ansi_text, padding=0, width=panel_width, height=rows)
                        if debug:
                            print_colored(f"Rendered image with half-block ANSI fallback (Pillow + Rich Text). Rows: {rows}", INFO)
                    except Exception as e:
                        if debug:
                            print_colored(f"Text.from_ansi failed: {e}", WARNING)
                        preview = '\n'.join(ansi.split('\n')[:min(6, len(ansi.split('\n')))])
                        rows = preview.count('\n') + 1
                        left = Panel(preview, padding=0, width=panel_width, height=rows)
                else:
                    # legacy full-block rendering
                    # compute target size: use 'width' chars; compensate aspect (chars are taller)
                    pixel_width = max(1, width)
                    aspect = im.height / im.width
                    pixel_height = max(1, int(pixel_width * aspect * 0.5))
                    im2 = im.resize((pixel_width, pixel_height))

                    rows = []
                    for y in range(im2.height):
                        row_pixels = [im2.getpixel((x, y)) for x in range(im2.width)]
                        # build ANSI background blocks
                        row = ''.join(f"\x1b[48;2;{r};{g};{b}m  " for (r, g, b) in row_pixels)
                        row += "\x1b[0m"
                        rows.append(row)
                    ascii_img = "\n".join(rows)
                    try:
                        from rich.text import Text
                        ansi_text = Text.from_ansi(ascii_img)
                        left = Panel(ansi_text, padding=0)
                        if debug:
                            print_colored("Rendered image with ANSI fallback (Pillow + Rich Text).", INFO)
                    except Exception as e:
                        if debug:
                            print_colored(f"Text.from_ansi failed: {e}", WARNING)
                        preview = "\n".join(rows[:min(4, len(rows))])
                        left = Panel(preview, padding=0)
            except Exception as e:
                if debug:
                    print_colored(f"ANSI render failed: {e}", WARNING)
                left = Panel(f"[bold]Image found:[/bold]\n{img_path}", height=12)
        else:
            left = Panel(f"[bold]Image found:[/bold]\n{img_path}", height=12)
    else:
        left = Panel("[bold red]No image found[/bold red]", height=12)

    # Right: stats as a table and make height match left
    table = Table(show_header=False, box=None, pad_edge=False)
    for k, v in (stats or {}).items():
        table.add_row(f"[bold]{k}[/bold]", str(v))
    # ensure right panel has same height as left
    right_height = None
    try:
        right_height = left.height
    except Exception:
        # fallback to number of rows if available
        try:
            right_height = rows
        except Exception:
            right_height = None
    if right_height:
        right = Panel(table, title=f"{found.get('name', player)} ({stat_type})", width=panel_width, height=right_height)
    else:
        right = Panel(table, title=f"{found.get('name', player)} ({stat_type})", width=panel_width)

    # Print two equal columns so both panels appear the same size
    console.print(Columns([left, right], expand=True, equal=True))

    if print_output:
        return None
    return {"image": img_path, "stats": stats}


players = load_json(PLAYERS_PATH) or []





