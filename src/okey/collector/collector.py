import requests
import json
import os
import time
import random
import urllib.parse
from datetime import datetime
from requests.exceptions import RequestException
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATISTICS_DIR = os.path.join(BASE_DIR, "statistics")
os.makedirs(STATISTICS_DIR, exist_ok=True)

# ANSI Colors (imported from main.py when needed)
try:
    from main import print_colored, INFO, SUCCESS, ERROR, WARNING
    COLORS_AVAILABLE = True
except ImportError:
    COLORS_AVAILABLE = False
    def print_colored(msg, status=0, bold=False): print(msg)

# Session with retry/backoff
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "okey-collector/1.0 (+https://github.com/itsal3xis/okey)",
    "Accept": "application/json, text/plain, */*",
})

RETRY_STRATEGY = Retry(
    total=5,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET"],
    raise_on_status=False,
)
ADAPTER = HTTPAdapter(max_retries=RETRY_STRATEGY)
SESSION.mount("https://", ADAPTER)
SESSION.mount("http://", ADAPTER)

def safe_get(url, timeout=10, quiet=False):
    """Perform GET with shared session + retry"""
    try:
        resp = SESSION.get(url, timeout=timeout)
    except RequestException as e:
        if COLORS_AVAILABLE and not quiet:
            print_colored(f"Error fetching {url}: {e}", ERROR)
        return None

    if resp.status_code == 429:
        wait = 5 + random.random() * 5
        if COLORS_AVAILABLE and not quiet:
            print_colored(f"HTTP 429 for {url} — backing off {wait:.1f}s", WARNING)
        time.sleep(wait)
    return resp

def stats(standings_date=None, game_type_id=2, wildcard_indicator=True, quiet=False):
    """Fetch comprehensive team standings with ALL available statistics"""
    params = {
        'gameTypeId': game_type_id,
        'wildCardIndicator': wildcard_indicator
    }
    if standings_date:
        params['standingsDateTimeUtc'] = standings_date
    
    url = 'https://api-web.nhle.com/v1/standings/now'
    if params:
        url += f"?{urllib.parse.urlencode(params)}"
    
    if COLORS_AVAILABLE and not quiet:
        print_colored("Fetching comprehensive standings...", INFO)
    
    response = safe_get(url, quiet=quiet)
    if not response or response.status_code != 200:
        if COLORS_AVAILABLE and not quiet:
            print_colored(f"Failed to fetch standings: HTTP {response.status_code if response else 'network'}", ERROR)
        return
    
    try:
        data = response.json()
    except ValueError:
        if COLORS_AVAILABLE and not quiet:
            print_colored("Unable to parse standings JSON.", ERROR)
        return

    equipes_stats = []
    for record in data.get('standings', []):
        equipe_info = {
            # Basic Team Info
            "team": record.get('teamName', {}).get('default'),
            "teamCommonName": record.get('teamCommonName', {}).get('default'),
            "abrev": record.get('teamAbbrev', {}).get('default'),
            "placeName": record.get('placeName', {}).get('default'),
            "conference": record.get('conferenceName'),
            "conferenceAbbrev": record.get('conferenceAbbrev'),
            "division": record.get('divisionName'),
            "divisionAbbrev": record.get('divisionAbbrev'),
            "teamLogo": record.get('teamLogo'),
            
            # Core Record
            "date": record.get('date'),
            "seasonId": record.get('seasonId'),
            "gamesPlayed": record.get('gamesPlayed'),
            "wins": record.get('wins'),
            "losses": record.get('losses'),
            "otLosses": record.get('otLosses'),
            "ties": record.get('ties'),
            "shootoutWins": record.get('shootoutWins'),
            "shootoutLosses": record.get('shootoutLosses'),
            "points": record.get('points'),
            
            # Home/Road Splits
            "homeGamesPlayed": record.get('homeGamesPlayed'),
            "homeWins": record.get('homeWins'),
            "homeLosses": record.get('homeLosses'),
            "homeOtLosses": record.get('homeOtLosses'),
            "homeTies": record.get('homeTies'),
            "homePoints": record.get('homePoints'),
            "homeRegulationWins": record.get('homeRegulationWins'),
            "homeRegulationPlusOtWins": record.get('homeRegulationPlusOtWins'),
            "homeGoalDifferential": record.get('homeGoalDifferential'),
            "homeGoalsFor": record.get('homeGoalsFor'),
            "homeGoalsAgainst": record.get('homeGoalsAgainst'),
            
            "roadGamesPlayed": record.get('roadGamesPlayed'),
            "roadWins": record.get('roadWins'),
            "roadLosses": record.get('roadLosses'),
            "roadOtLosses": record.get('roadOtLosses'),
            "roadTies": record.get('roadTies'),
            "roadPoints": record.get('roadPoints'),
            "roadRegulationWins": record.get('roadRegulationWins'),
            "roadRegulationPlusOtWins": record.get('roadRegulationPlusOtWins'),
            "roadGoalDifferential": record.get('roadGoalDifferential'),
            "roadGoalsFor": record.get('roadGoalsFor'),
            "roadGoalsAgainst": record.get('roadGoalsAgainst'),
            
            # Last 10 Games (L10)
            "l10GamesPlayed": record.get('l10GamesPlayed'),
            "l10Wins": record.get('l10Wins'),
            "l10Losses": record.get('l10Losses'),
            "l10OtLosses": record.get('l10OtLosses'),
            "l10Ties": record.get('l10Ties'),
            "l10Points": record.get('l10Points'),
            "l10RegulationWins": record.get('l10RegulationWins'),
            "l10RegulationPlusOtWins": record.get('l10RegulationPlusOtWins'),
            "l10GoalDifferential": record.get('l10GoalDifferential'),
            "l10GoalsFor": record.get('l10GoalsFor'),
            "l10GoalsAgainst": record.get('l10GoalsAgainst'),
            
            # Advanced Stats
            "goalDifferential": record.get('goalDifferential'),
            "goalDifferentialPctg": record.get('goalDifferentialPctg'),
            "goalFor": record.get('goalFor'),
            "goalAgainst": record.get('goalAgainst'),
            "goalsForPctg": record.get('goalsForPctg'),
            
            # Percentages
            "pointPctg": record.get('pointPctg'),
            "winPctg": record.get('winPctg'),
            "regulationWinPctg": record.get('regulationWinPctg'),
            "regulationPlusOtWinPctg": record.get('regulationPlusOtWinPctg'),
            
            # Rankings/Sequences
            "conferenceSequence": record.get('conferenceSequence'),
            "conferenceHomeSequence": record.get('conferenceHomeSequence'),
            "conferenceRoadSequence": record.get('conferenceRoadSequence'),
            "conferenceL10Sequence": record.get('conferenceL10Sequence'),
            
            "divisionSequence": record.get('divisionSequence'),
            "divisionHomeSequence": record.get('divisionHomeSequence'),
            "divisionRoadSequence": record.get('divisionRoadSequence'),
            "divisionL10Sequence": record.get('divisionL10Sequence'),
            
            "leagueSequence": record.get('leagueSequence'),
            "leagueHomeSequence": record.get('leagueHomeSequence'),
            "leagueRoadSequence": record.get('leagueRoadSequence'),
            "leagueL10Sequence": record.get('leagueL10Sequence'),
            
            "wildcardSequence": record.get('wildcardSequence'),
            "waiversSequence": record.get('waiversSequence'),
            
            # Streaks
            "streakCode": record.get('streakCode'),
            "streakCount": record.get('streakCount'),
            
            # Regulation Wins
            "regulationWins": record.get('regulationWins'),
            "regulationPlusOtWins": record.get('regulationPlusOtWins'),
        }
        equipes_stats.append(equipe_info)

    with open(os.path.join(STATISTICS_DIR, "teamsStats.json"), "w", encoding="utf-8") as f:
        json.dump(equipes_stats, f, ensure_ascii=False, indent=4)
    
    if COLORS_AVAILABLE and not quiet:
        print_colored(f"Updated {len(equipes_stats)} teams with 70+ statistics fields", SUCCESS)

def today_schedule(quiet=False):
    """Fetch today's game schedule"""
    url = 'https://api-web.nhle.com/v1/schedule/now'
    response = safe_get(url, quiet=quiet)
    if not response or response.status_code != 200:
        if COLORS_AVAILABLE and not quiet:
            code = response.status_code if response else "network-fail"
            print_colored(f"Error fetching schedule: {code}", ERROR)
        return

    try:
        data = response.json()
    except ValueError:
        if COLORS_AVAILABLE and not quiet:
            print_colored("Unable to parse schedule JSON.", ERROR)
        return

    today_str = datetime.now().strftime("%Y-%m-%d")
    today_games = []

    for day in data.get("gameWeek", []):
        if day.get("date") == today_str:
            for game in day.get("games", []):
                game_info = {
                    "date": day.get("date"),
                    "venue": game.get("venue", {}).get("default"),
                    "startTimeUTC": game.get("startTimeUTC"),
                    "homeTeam": {
                        "name": game.get("homeTeam", {}).get("placeName", {}).get("default", "") + " " +
                                game.get("homeTeam", {}).get("commonName", {}).get("default", ""),
                        "abbrev": game.get("homeTeam", {}).get("abbrev")
                    },
                    "awayTeam": {
                        "name": game.get("awayTeam", {}).get("placeName", {}).get("default", "") + " " +
                                game.get("awayTeam", {}).get("commonName", {}).get("default", ""),
                        "abbrev": game.get("awayTeam", {}).get("abbrev")
                    }
                }
                today_games.append(game_info)

    with open(os.path.join(STATISTICS_DIR, "todayGames.json"), "w", encoding="utf-8") as f:
        json.dump(today_games, f, indent=2, ensure_ascii=False)
    
    if COLORS_AVAILABLE and not quiet:
        print_colored(f"{len(today_games)} game(s) saved to todayGames.json", SUCCESS)

def team_players(abbr, season_id):
    """Get team roster"""
    url = f"https://api-web.nhle.com/v1/roster/{abbr}/{season_id}"
    response = safe_get(url, timeout=10)
    if not response or response.status_code != 200:
        return []
    try:
        data = response.json()
    except ValueError:
        return []

    informations = []
    for group in ["forwards", "defensemen", "goalies"]:
        for player in data.get(group, []):
            player_info = {
                "name": f"{player.get('firstName', {}).get('default','')} {player.get('lastName', {}).get('default','')}".strip(),
                "id": player.get("id"),
                "position": player.get("positionCode") or (group[:-1].capitalize() if group.endswith("s") else group),
                "height": player.get("heightInCentimeters"),
                "weight": player.get("weightInKilograms"),
                "birthDate": player.get("birthDate"),
                "headshot": player.get("headshot"),
                "heroImage": player.get("heroImage")
            }
            informations.append(player_info)
    return informations

def player_stats(player_id, season_id):
    """Get comprehensive player statistics"""
    url = f"https://api-web.nhle.com/v1/player/{player_id}/landing"
    response = safe_get(url, timeout=10)
    if not response or response.status_code != 200:
        return None
    try:
        data = response.json()
    except ValueError:
        return None

    featured_season = data.get("featuredStats", {}).get("season")
    position = data["position"].get("code", "").upper() if isinstance(data.get("position"), dict) else str(data.get("position", "")).upper()

    reg_stats = data.get("featuredStats", {}).get("regularSeason", {}).get("subSeason", {})
    reg_career = data.get("featuredStats", {}).get("regularSeason", {}).get("career", {})
    po_stats = data.get("featuredStats", {}).get("playoffs", {}).get("subSeason", {})
    po_career = data.get("featuredStats", {}).get("playoffs", {}).get("career", {})

    awards = []
    for award in data.get("awards", []):
        trophy = award.get("trophy", {}).get("default") or award.get("displayName", "")
        seasons = [s.get("seasonId") for s in award.get("seasons", [])] or [award.get("season")]
        awards.append({"trophy": trophy, "seasons": seasons})

    if position == "G":
        return {
            "season": featured_season,
            "gamesPlayed": reg_stats.get("gamesPlayed", 0),
            "wins": reg_stats.get("wins", 0),
            "losses": reg_stats.get("losses", 0),
            "otLosses": reg_stats.get("otLosses", 0),
            "goalsAgainstAvg": reg_stats.get("goalsAgainstAvg", 0),
            "savePctg": reg_stats.get("savePctg", 0),
            "shutouts": reg_stats.get("shutouts", 0),
            "careerGamesPlayed": reg_career.get("gamesPlayed", 0),
            "careerWins": reg_career.get("wins", 0),
            "careerLosses": reg_career.get("losses", 0),
            "careerOtLosses": reg_career.get("otLosses", 0),
            "careerGoalsAgainstAvg": reg_career.get("goalsAgainstAvg", 0),
            "careerSavePctg": reg_career.get("savePctg", 0),
            "careerShutouts": reg_career.get("shutouts", 0),
            "sweaterNumber": data.get("sweaterNumber", ""),
            "birthDate": data.get("birthDate", ""),
            "headshot": data.get("headshot", ""),
            "heroImage": data.get("heroImage", ""),
            "teamLogo": data.get("teamLogo", ""),
            "awards": awards
        }
    
    return {
        "season": featured_season,
        "gamesPlayed": reg_stats.get("gamesPlayed", 0),
        "goals": reg_stats.get("goals", 0),
        "assists": reg_stats.get("assists", 0),
        "points": reg_stats.get("points", 0),
        "plusMinus": reg_stats.get("plusMinus", 0),
        "shots": reg_stats.get("shots", 0),
        "pim": reg_stats.get("pim", 0),
        "powerPlayGoals": reg_stats.get("powerPlayGoals", 0),
        "powerPlayPoints": reg_stats.get("powerPlayPoints", 0),
        "shorthandedGoals": reg_stats.get("shorthandedGoals", 0),
        "shorthandedPoints": reg_stats.get("shorthandedPoints", 0),
        "gameWinningGoals": reg_stats.get("gameWinningGoals", 0),
        "otGoals": reg_stats.get("otGoals", 0),
        "shootingPctg": reg_stats.get("shootingPctg", 0),
        "careerGamesPlayed": reg_career.get("gamesPlayed", 0),
        "careerGoals": reg_career.get("goals", 0),
        "careerAssists": reg_career.get("assists", 0),
        "careerPoints": reg_career.get("points", 0),
        "sweaterNumber": data.get("sweaterNumber", ""),
        "birthDate": data.get("birthDate", ""),
        "headshot": data.get("headshot", ""),
        "heroImage": data.get("heroImage", ""),
        "teamLogo": data.get("teamLogo", ""),
        "awards": awards,
        "last5Games": data.get("last5Games", []),
    }

def collect_all_player_stats(season_id, quiet=False):
    """Collect stats for all players across all teams"""
    teams_file = os.path.join(STATISTICS_DIR, "teamsStats.json")
    if not os.path.exists(teams_file):
        if COLORS_AVAILABLE and not quiet:
            print_colored("teamsStats.json not found — run stats() first", ERROR)
        return

    REQUIRED_SEASON = "20252026"
    current_season = reg_season()
    is_current = (str(season_id) == str(current_season))

    with open(teams_file, "r", encoding="utf-8") as f:
        teams = json.load(f)

    all_players = []
    for team in teams:
        abbr = team.get("abrev")
        if not abbr:
            continue
        
        if COLORS_AVAILABLE and not quiet:
            print_colored(f"Fetching players for {abbr}...", INFO)
        
        players = team_players(abbr, season_id)
        
        for player in players:
            time.sleep(0.12 + random.random() * 0.08)
            stats_data = player_stats(player["id"], season_id)
            if not stats_data:
                continue

            stats_season = stats_data.get("season")
            if str(stats_season) != REQUIRED_SEASON:
                continue

            gp = stats_data.get("gamesPlayed", 0)
            if not is_current and gp == 0:
                continue

            headshot = stats_data.get("headshot") or player.get("headshot") or ""
            
            # FIXED: Store both original name and lookup key
            original_name = player.get("name")
            name_key = original_name.lower().replace(" ", "") if original_name else ""
            
            player_info = {
                "id": player.get("id"),
                "name": original_name,  # "Gavin Brindley" (for display)
                "nameKey": name_key,    # "gavinbrindley" (for CLI lookup)
                "team": abbr,
                "position": player.get("position"),
                **stats_data,
                "headshot": headshot,
            }
            all_players.append(player_info)

        time.sleep(0.6 + random.random() * 0.6)

    if COLORS_AVAILABLE and not quiet:
        print_colored(f"Total players collected: {len(all_players)}", SUCCESS)
    
    with open(os.path.join(STATISTICS_DIR, "playerStats.json"), "w", encoding="utf-8") as f:
        json.dump(all_players, f, ensure_ascii=False, indent=2)

    """Collect stats for all players across all teams"""
    teams_file = os.path.join(STATISTICS_DIR, "teamsStats.json")
    if not os.path.exists(teams_file):
        if COLORS_AVAILABLE and not quiet:
            print_colored("teamsStats.json not found — run stats() first", ERROR)
        return

    REQUIRED_SEASON = "20252026"
    current_season = reg_season()
    is_current = (str(season_id) == str(current_season))

    with open(teams_file, "r", encoding="utf-8") as f:
        teams = json.load(f)

    all_players = []
    for team in teams:
        abbr = team.get("abrev")
        if not abbr:
            continue
        
        if COLORS_AVAILABLE and not quiet:
            print_colored(f"Fetching players for {abbr}...", INFO)
        
        players = team_players(abbr, season_id)
        
        for player in players:
            time.sleep(0.12 + random.random() * 0.08)
            stats_data = player_stats(player["id"], season_id)
            if not stats_data:
                continue

            stats_season = stats_data.get("season")
            if str(stats_season) != REQUIRED_SEASON:
                continue

            gp = stats_data.get("gamesPlayed", 0)
            if not is_current and gp == 0:
                continue

            headshot = stats_data.get("headshot") or player.get("headshot") or ""
            player_info = {
                "id": player.get("id"),
                "name": player.get("name"),
                "nameKey": player.get("name").lower().replace(" ", ""),
                "team": abbr,
                "position": player.get("position"),
                **stats_data,
                "headshot": headshot,
            }
            all_players.append(player_info)

        time.sleep(0.6 + random.random() * 0.6)

    if COLORS_AVAILABLE and not quiet:
        print_colored(f"Total players collected: {len(all_players)}", SUCCESS)
    
    with open(os.path.join(STATISTICS_DIR, "playerStats.json"), "w", encoding="utf-8") as f:
        json.dump(all_players, f, ensure_ascii=False, indent=2)

def reg_season():
    """Detect current NHL season"""
    now = datetime.now()
    if now.month < 9:
        year1 = now.year - 1
        year2 = now.year
    else:
        year1 = now.year
        year2 = now.year + 1
    return f"{year1}{year2}"

def collector(quiet=False, standings_date=None, game_type_id=2, wildcard_indicator=True, season_id=None):
    """
    Main collector function with full parameter support
    
    Args:
        quiet: Suppress output
        standings_date: Specific standings date
        game_type_id: 2=regular, 4=playoffs
        wildcard_indicator: Include wildcard teams
        season_id: Override auto-detection
    """
    stats(standings_date=standings_date, game_type_id=game_type_id, 
          wildcard_indicator=wildcard_indicator, quiet=quiet)
    today_schedule(quiet=quiet)
    
    season = season_id or reg_season()
    collect_all_player_stats(season, quiet=quiet)

if __name__ == "__main__":
    collector()
