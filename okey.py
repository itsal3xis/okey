import os
import json
import argparse
import sys
import time
from datetime import datetime
from src.okey.collector.collector import collector, reg_season

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
STAT_DIR = os.path.join(ROOT, "src", "okey", "collector", "statistics")

TODAY_PATH = os.path.join(STAT_DIR, "todayGames.json")
TEAMS_PATH = os.path.join(STAT_DIR, "teamsStats.json")
PLAYERS_PATH = os.path.join(STAT_DIR, "playerStats.json")

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

def run_collector(quiet=False, standings_date=None, game_type_id=2, wildcard_indicator=True, season_id=None, log_file=None):
    """Unified collector runner - handles CLI, daemon, logging"""
    if not quiet and log_file is None:
        print_colored("Updating NHL statistics, can take a few minutes...", INFO, bold=True)
    
    collector(
        quiet=quiet,
        standings_date=standings_date,
        game_type_id=game_type_id,
        wildcard_indicator=wildcard_indicator,
        season_id=season_id
    )
    
    if not quiet and log_file is None:
        print_colored("NHL statistics updated successfully!", SUCCESS, bold=True)

def run_background_collector():
    """Daemonized collector - fully detached background process"""
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError:
        sys.exit(1)
    
    os.setsid()
    os.umask(0)
    
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError:
        sys.exit(1)
    
    # Redirect output to log file
    log_fd = open('okey.log', 'a')
    sys.stdout = log_fd
    sys.stderr = log_fd
    
    start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"=== OKey NHL Collector Started: {start_time} (every 10min) ===")
    
    while True:
        try:
            run_collector(quiet=True, log_file='okey.log')
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Collector cycle complete")
            time.sleep(600)  # 10 minutes
        except Exception as e:
            print(f"[{datetime.now()}] ERROR: {e}")
            time.sleep(60)  # Wait 1 min on error

# Background check FIRST
if '--background' in sys.argv:
    print_colored("Starting OKey NHL collector in background...", INFO, bold=True)
    run_background_collector()
    sys.exit(0)

def main():
    parser = argparse.ArgumentParser(prog="okey", description="OKey - CLI statistics tool for NHL")
    parser.add_argument("-p", "--player", help="Select player by name (Connor McDavid or cmcdavid)")
    parser.add_argument("-c", "--collector", action="store_true", help="Update statistics")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress output")
    parser.add_argument("--standings-date", help="Standings date (YYYY-MM-DD)")
    parser.add_argument("--game-type", type=int, default=2, help="Game type: 2=regular, 4=playoffs")
    parser.add_argument("--season", help="Specific season ID")
    args = parser.parse_args()

    if args.player:
        player_name = args.player.lower().replace(" ", "")
        players_data = load_json(PLAYERS_PATH)
        if not players_data:
            return
    
        # Search by nameKey first, then fallback to name
        player_info = None
        for player in players_data:
            if player.get("nameKey") == player_name or player.get("name", "").lower().replace(" ", "") == player_name:
                player_info = player
                break
        if not player_info:
            print_colored(f"Player '{args.player}' not found.", ERROR)
            return
        current_season = reg_season()
        if str(player_info.get("season", "")) != current_season:
            print_colored(f"Player '{args.player}' has no stats for current season.", WARNING)
        print_colored(f"\n{player_info.get('name', args.player)} stats:", INFO, bold=True)
        for key, value in player_info.items():
            if key not in ['id', 'name', 'team', 'position']:
                print(f"  {key}: {value}")
    
    if args.collector:
        run_collector(
            quiet=args.quiet,
            standings_date=args.standings_date,
            game_type_id=args.game_type,
            season_id=args.season
        )

if __name__ == "__main__":
    main()
