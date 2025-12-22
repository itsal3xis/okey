import os
import json
import argparse
import sys
import time
from datetime import datetime
from src.okey.collector.collector import collector, reg_season
from src.okey.collector.analyst import player_info, print_colored


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
    parser.add_argument("-s", "--stats", choices=['basic','advanced','all','bio'], default='basic', help="Stats type to show: basic|advanced|all|bio")
    parser.add_argument("-I", "--show-image", action="store_true", help="Show player image next to stats (requires rich and pillow)")
    parser.add_argument("-m", "--image-mode", choices=['auto','half','ansi','rich'], default='auto', help="Image rendering mode: auto|half|ansi|rich")
    parser.add_argument("--image-width", type=int, default=24, help="Image width in characters")
    parser.add_argument("--image-size", type=int, default=None, help="Square image size in characters (small square footprint); overrides --image-width")
    parser.add_argument("-d", "--debug", action="store_true", help="Enable debug output for image rendering")
    parser.add_argument("-c", "--collector", action="store_true", help="Update statistics")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress output")
    parser.add_argument("--standings-date", help="Standings date (YYYY-MM-DD)")
    parser.add_argument("--game-type", type=int, default=2, help="Game type: 2=regular, 4=playoffs")
    parser.add_argument("--season", help="Specific season ID")
    args = parser.parse_args()

    if args.player:
        if args.show_image:
            # Import here to avoid adding the dependency at module import time
            from src.okey.collector.analyst import print_player_with_image
            print_player_with_image(
                args.player,
                stat_type=args.stats,
                debug=args.debug,
                width=args.image_width,
                mode=args.image_mode,
                image_size=args.image_size
            )
        else:
            player_info(args.player, stat_type=args.stats)
    if args.collector:
        run_collector(
            quiet=args.quiet,
            standings_date=args.standings_date,
            game_type_id=args.game_type,
            season_id=args.season
        )

if __name__ == "__main__":
    main()
