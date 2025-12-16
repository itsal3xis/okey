import requests
import json
import os
import time
import random
from datetime import datetime
from requests.exceptions import RequestException
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Get the directory where this script is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATISTICS_DIR = os.path.join(BASE_DIR, "statistics")
os.makedirs(STATISTICS_DIR, exist_ok=True)

# --- session with retry/backoff and default headers ---
SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "okey-collector/1.0 (+https://github.com/you/okey)",
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


def safe_get(url, timeout=10):
    """
    Perform a GET with the shared session + retry adapter.
    Returns a requests.Response or None on network error.
    """
    try:
        resp = SESSION.get(url, timeout=timeout)
    except RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

    if resp.status_code == 429:
        # If we still receive 429 after retries, back off a bit longer
        wait = 5 + random.random() * 5
        print(f"HTTP 429 for {url} — backing off {wait:.1f}s")
        time.sleep(wait)
    return resp
# --- end session helpers ---


def stats():
    url = 'https://api-web.nhle.com/v1/standings/now'
    response = safe_get(url)
    if not response:
        print("Failed to fetch standings.")
        return
    if response.status_code == 200:
        try:
            data = response.json()
        except ValueError:
            print("Unable to parse standings JSON.")
            return

        equipes_stats = []
        for record in data.get('standings', []):
            equipe_info = {
                "team": record.get('teamName', {}).get('default'),
                "abrev": record.get('teamAbbrev', {}).get('default'),
                "conference": record.get('conferenceName'),
                "division": record.get('divisionName'),
                "points": record.get('points'),
                "homePoints": record.get('homePoints'),
                "roadPoints": record.get('roadPoints'),
                "gamesPlayed": record.get('gamesPlayed'),
                "wins": record.get('wins'),
                "homeWins": record.get('homeWins'),
                "roadWins": record.get('roadWins'),
                "loses": record.get('losses'),
                "homeLoses": record.get('homeLosses'),
                "roadLoses": record.get('roadLosses'),
                "OtWins": record.get('otLosses'),
                "goalDifferential": record.get('goalDifferential'),
                "goalAgainst": record.get('goalAgainst'),
                "teamLogo": record.get('teamLogo'),
            }
            equipes_stats.append(equipe_info)

        with open(os.path.join(STATISTICS_DIR, "teamsStats.json"), "w", encoding="utf-8") as f:
            json.dump(equipes_stats, f, ensure_ascii=False, indent=4)
    else:
        print(f"Standings request returned HTTP {response.status_code}")


def today_schedule():
    url = 'https://api-web.nhle.com/v1/schedule/now'
    response = safe_get(url)
    if not response or response.status_code != 200:
        code = response.status_code if response else "network-fail"
        print(f"Error fetching schedule: {code}")
        return

    try:
        data = response.json()
    except ValueError:
        print("Unable to parse schedule JSON.")
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

    print(f"{len(today_games)} game(s) saved to todayGames.json")


def team_players(abbr, season_id):
    url = f"https://api-web.nhle.com/v1/roster/{abbr}/{season_id}"
    response = safe_get(url, timeout=10)
    if not response:
        return []
    if response.status_code != 200:
        print(f"Error fetching roster for {abbr}: HTTP {response.status_code}")
        if getattr(response, "text", None):
            print("  Response snippet:", response.text[:200])
        return []
    try:
        data = response.json()
    except ValueError:
        print(f"Unable to decode JSON for roster {abbr}. Response snippet: {response.text[:200]!r}")
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
    url = f"https://api-web.nhle.com/v1/player/{player_id}/landing"
    response = safe_get(url, timeout=10)
    if not response:
        return None
    if response.status_code != 200:
        print(f"  Stats request for player {player_id} returned HTTP {response.status_code}")
        return None
    try:
        data = response.json()
    except ValueError:
        print(f"  Unable to parse JSON for player {player_id}. Response snippet: {response.text[:200]!r}")
        return None

    # --- NEW: capture featured season from the landing payload ---
    featured_season = data.get("featuredStats", {}).get("season")

    position = ""
    if isinstance(data.get("position"), dict):
        position = data["position"].get("code", "").upper()
    else:
        position = str(data.get("position", "")).upper()

    awards = []
    for award in data.get("awards", []):
        trophy = award.get("trophy", {}).get("default") or award.get("displayName", "")
        seasons = [s.get("seasonId") for s in award.get("seasons", [])] or [award.get("season")]
        awards.append({
            "trophy": trophy,
            "seasons": seasons
        })

    reg_stats = data.get("featuredStats", {}).get("regularSeason", {}).get("subSeason", {})
    reg_career = data.get("featuredStats", {}).get("regularSeason", {}).get("career", {})
    po_stats = data.get("featuredStats", {}).get("playoffs", {}).get("subSeason", {})
    po_career = data.get("featuredStats", {}).get("playoffs", {}).get("career", {})

    if position == "G":
        awards = []
        for award in data.get("awards", []):
            if award.get("displayName") and award.get("season"):
                awards.append({
                    "name": award["displayName"],
                    "season": award["season"]
                })
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
            "playoffGamesPlayed": po_stats.get("gamesPlayed", 0),
            "playoffWins": po_stats.get("wins", 0),
            "playoffLosses": po_stats.get("losses", 0),
            "playoffOtLosses": po_stats.get("otLosses", 0),
            "playoffGoalsAgainstAvg": po_stats.get("goalsAgainstAvg", 0),
            "playoffSavePctg": po_stats.get("savePctg", 0),
            "playoffShutouts": po_stats.get("shutouts", 0),
            "careerPlayoffGamesPlayed": po_career.get("gamesPlayed", 0),
            "careerPlayoffWins": po_career.get("wins", 0),
            "careerPlayoffLosses": po_career.get("losses", 0),
            "careerPlayoffOtLosses": po_career.get("otLosses", 0),
            "careerPlayoffGoalsAgainstAvg": po_career.get("goalsAgainstAvg", 0),
            "careerPlayoffSavePctg": po_career.get("savePctg", 0),
            "careerPlayoffShutouts": po_career.get("shoutouts", 0) if po_career else 0,
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
        "careerPlusMinus": reg_career.get("plusMinus", 0),
        "careerShots": reg_career.get("shots", 0),
        "careerPim": reg_career.get("pim", 0),
        "careerPowerPlayGoals": reg_career.get("powerPlayGoals", 0),
        "careerPowerPlayPoints": reg_career.get("powerPlayPoints", 0),
        "careerShorthandedGoals": reg_career.get("shorthandedGoals", 0),
        "careerShorthandedPoints": reg_career.get("shorthandedPoints", 0),
        "careerGameWinningGoals": reg_career.get("gameWinningGoals", 0),
        "careerOtGoals": reg_career.get("otGoals", 0),
        "careerShootingPctg": reg_career.get("shootingPctg", 0),
        "playoffGamesPlayed": po_stats.get("gamesPlayed", 0),
        "playoffGoals": po_stats.get("goals", 0),
        "playoffAssists": po_stats.get("assists", 0),
        "playoffPoints": po_stats.get("points", 0),
        "playoffPlusMinus": po_stats.get("plusMinus", 0),
        "playoffShots": po_stats.get("shots", 0),
        "playoffPim": po_stats.get("pim", 0),
        "playoffPowerPlayGoals": po_stats.get("powerPlayGoals", 0),
        "playoffPowerPlayPoints": po_stats.get("powerPlayPoints", 0),
        "playoffShorthandedGoals": po_stats.get("shorthandedGoals", 0),
        "playoffShorthandedPoints": po_stats.get("shorthandedPoints", 0),
        "playoffGameWinningGoals": po_stats.get("gameWinningGoals", 0),
        "playoffOtGoals": po_stats.get("otGoals", 0),
        "playoffShootingPctg": po_stats.get("shootingPctg", 0),
        "careerPlayoffGamesPlayed": po_career.get("gamesPlayed", 0),
        "careerPlayoffGoals": po_career.get("goals", 0),
        "careerPlayoffAssists": po_career.get("assists", 0),
        "careerPlayoffPoints": po_career.get("points", 0),
        "careerPlayoffPlusMinus": po_career.get("plusMinus", 0),
        "careerPlayoffShots": po_career.get("shots", 0),
        "careerPlayoffPim": po_career.get("pim", 0),
        "careerPlayoffPowerPlayGoals": po_career.get("powerPlayGoals", 0),
        "careerPlayoffPowerPlayPoints": po_career.get("powerPlayPoints", 0),
        "careerPlayoffShorthandedGoals": po_career.get("shorthandedGoals", 0),
        "careerPlayoffShorthandedPoints": po_career.get("shorthandedPoints", 0),
        "careerPlayoffGameWinningGoals": po_career.get("gameWinningGoals", 0),
        "careerPlayoffOtGoals": po_career.get("otGoals", 0),
        "careerPlayoffShootingPctg": po_career.get("shootingPctg", 0),
        "sweaterNumber": data.get("sweaterNumber", ""),
        "birthDate": data.get("birthDate", ""),
        "headshot": data.get("headshot", ""),
        "heroImage": data.get("heroImage", ""),
        "teamLogo": data.get("teamLogo", ""),
        "awards": awards,
        "last5Games": data.get("last5Games", []),
    }


def collect_all_player_stats(season_id):
    teams_file = os.path.join(STATISTICS_DIR, "teamsStats.json")
    if not os.path.exists(teams_file):
        print("teamsStats.json not found — run stats() first")
        return

    REQUIRED_SEASON = "20252026"
    if str(season_id) != REQUIRED_SEASON:
        print(f"Note: requested season {season_id} differs from required output season {REQUIRED_SEASON}.")
        print(f"Only players whose featured season == {REQUIRED_SEASON} will be written to playerStats.json.")

    current_season = reg_season()
    is_current = (str(season_id) == str(current_season))
    if not is_current:
        print(f"Collecting for season {season_id} which is not the current season {current_season}.")
        print("Players with zero games in that season will be skipped to avoid stale entries.")

    with open(teams_file, "r", encoding="utf-8") as f:
        teams = json.load(f)

    all_players = []
    for team in teams:
        abbr = team.get("abrev")
        if not abbr:
            print(f"Missing abrev for team: {team}")
            continue
        print(f"Fetching players for team: {abbr}")
        players = team_players(abbr, season_id)
        print(f"  Found {len(players)} players")
        for player in players:
            # small per-player throttle to avoid bursts
            time.sleep(0.12 + random.random() * 0.08)
            stats_data = player_stats(player["id"], season_id)
            if not stats_data:
                print(f"    No stats for player {player.get('name')} ({player.get('id')})")
                continue

            # Only include players whose featured season equals REQUIRED_SEASON
            stats_season = stats_data.get("season")
            if not stats_season or str(stats_season) != REQUIRED_SEASON:
                print(f"    Skipping {player.get('name')} — featured season {stats_season} != required {REQUIRED_SEASON}")
                continue

            # If collecting for a non-current season, still skip players with 0 games
            gp = stats_data.get("gamesPlayed", 0)
            try:
                gp_val = int(gp)
            except Exception:
                gp_val = 0
            if not is_current and gp_val == 0:
                print(f"    Skipping {player.get('name')} — 0 games in season {season_id}")
                continue

            headshot = stats_data.get("headshot") or player.get("headshot") or ""
            hero_image = stats_data.get("heroImage") or player.get("heroImage") or ""
            player_info = {
                "id": player.get("id"),
                "name": player.get("name"),
                "team": abbr,
                "position": player.get("position"),
                **stats_data,
                "headshot": headshot,
                "heroImage": hero_image,
            }
            all_players.append(player_info)

        # per-team pause to reduce chance of hitting global rate limits
        time.sleep(0.6 + random.random() * 0.6)

    print(f"Total players collected: {len(all_players)}")
    with open(os.path.join(STATISTICS_DIR, "playerStats.json"), "w", encoding="utf-8") as f:
        json.dump(all_players, f, ensure_ascii=False, indent=2)


def last_games(player_id, season_id, count=5):
    url = f"https://api-web.nhle.com/v1/player/{player_id}/game-log/{season_id}"
    response = safe_get(url, timeout=10)
    if not response:
        return []
    if response.status_code != 200:
        print(f"  Game-log request for player {player_id} returned HTTP {response.status_code}")
        return []
    try:
        data = response.json()
    except ValueError:
        print(f"  Unable to parse JSON game-log for player {player_id}. Snippet: {response.text[:200]!r}")
        return []
    games = data.get("gameLog", [])[:count]
    is_goalie = any(g.get("savePctg") is not None or g.get("goalsAgainst") is not None for g in games)
    result = []
    for g in games:
        if is_goalie:
            result.append({
                "gameDate": g.get("gameDate"),
                "gameId": g.get("gameId"),
                "gameTypeId": g.get("gameTypeId"),
                "gamesStarted": g.get("gamesStarted"),
                "goalsAgainst": g.get("goalsAgainst"),
                "homeRoadFlag": g.get("homeRoadFlag"),
                "opponentAbbrev": g.get("opponentAbbrev"),
                "pim": g.get("pim"),
                "savePctg": g.get("savePctg"),
                "shotsAgainst": g.get("shotsAgainst"),
                "teamAbbrev": g.get("teamAbbrev"),
                "toi": g.get("toi"),
            })
        else:
            result.append({
                "gameDate": g.get("gameDate"),
                "gameId": g.get("gameId"),
                "gameTypeId": g.get("gameTypeId"),
                "goals": g.get("goals"),
                "assists": g.get("assists"),
                "points": g.get("points"),
                "plusMinus": g.get("plusMinus"),
                "shots": g.get("shots"),
                "hits": g.get("hits"),
                "blockedShots": g.get("blockedShots"),
                "pim": g.get("pim"),
                "powerPlayGoals": g.get("powerPlayGoals"),
                "shorthandedGoals": g.get("shorthandedGoals"),
                "shifts": g.get("shifts"),
                "toi": g.get("toi"),
                "teamAbbrev": g.get("teamAbbrev"),
                "opponentAbbrev": g.get("opponentAbbrev"),
                "homeRoadFlag": g.get("homeRoadFlag"),
            })
    return result


def reg_season():
    now = datetime.now()
    if now.month < 9:
        year1 = now.year - 1
        year2 = now.year
    else:
        year1 = now.year
        year2 = now.year + 1
    return f"{year1}{year2}"


def collector():
    stats()
    today_schedule()
    season = reg_season()
    collect_all_player_stats(f"{season}")


if __name__ == "__main__":
    collector()




