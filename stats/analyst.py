"""Small analytics helpers for the `okey` app.

Primarily provides a simple `hottest_players` function which examines recent
game-level or summary fields on player records and returns the top N players
based on points in the last `last_n` games.

The function is defensive: it tries several common field names and falls back
to simple summary fields where available.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _int(v: Any) -> int:
    try:
        return int(v)
    except Exception:
        return 0


def hottest_players(players: List[Dict[str, Any]], top_n: int = 3, last_n: int = 5) -> List[Dict[str, Any]]:
    """Return up to `top_n` players most productive over the last `last_n` games.

    The returned list contains dicts with keys:
      - player: original player dict
      - games: number of recent games observed (<= last_n)
      - goals, assists, points: summed over those games
      - headshot: a best-effort URL/path for the player's headshot
      - team_logo: a best-effort path for a team logo (may not exist)
    """
    if not isinstance(players, list):
        return []

    results: List[Dict[str, Any]] = []

    # common keys that datasets use for recent game lists
    recent_keys = (
        "last5Games",
        "lastFive",
        "last_5",
        "recentGames",
        "recent_game_stats",
        "recentGameStats",
        "lastGames",
        "gameLog",
        "gameLogs",
        "games",
    )

    for p in players:
        if not isinstance(p, dict):
            continue

        recent: Optional[List[Dict[str, Any]]] = None
        for k in recent_keys:
            v = p.get(k)
            if isinstance(v, list) and v:
                recent = v
                break

        goals = assists = pts = 0
        games_seen = 0

        if recent:
            for entry in recent[:last_n]:
                if not isinstance(entry, dict):
                    continue
                goals += _int(entry.get("goals") or entry.get("G") or entry.get("g"))
                assists += _int(entry.get("assists") or entry.get("A") or entry.get("a"))
                pts += _int(entry.get("points") or entry.get("PTS") or entry.get("pts"))
                games_seen += 1

        else:
            # try summary fields like goalsLast5 / assistsLast5
            g = p.get("goalsLast5") or p.get("g_last5") or p.get("last5_goals")
            a = p.get("assistsLast5") or p.get("a_last5") or p.get("last5_assists")
            if g is not None or a is not None:
                goals = _int(g)
                assists = _int(a)
                pts = goals + assists
                games_seen = last_n
            else:
                # unable to compute recent stats for this player
                continue

        score = pts

        # best-effort headshot path: prefer absolute URL, fall back to /headshots/<id|nameKey>.
        hs = None
        for hk in ("headshot", "headshotUrl", "photo", "photoUrl", "img"):
            cand = p.get(hk)
            if cand:
                hs = cand
                break
        if isinstance(hs, str):
            hs = hs if hs.startswith("http") else f"/headshots/{hs}"
        else:
            # try nameKey or id
            nid = p.get("nameKey") or p.get("id")
            if nid:
                hs = f"/headshots/{nid}.jpg"
            else:
                hs = "/static/placeholder_headshot.png"

        # best-effort team logo path
        team_logo = p.get("teamLogo") or p.get("team_logo")
        if isinstance(team_logo, str):
            team_logo = team_logo if team_logo.startswith("http") else f"{team_logo}"
        else:
            # try team abbreviation
            t = p.get("team") or p.get("teamAbbrev") or p.get("teamName") or p.get("team_name")
            if t:
                abbr = str(t).lower().replace(" ", "_")
                team_logo = f"/static/team_logos/{abbr}.png"
            else:
                team_logo = None

        results.append(
            {
                "player": p,
                "games": games_seen,
                "goals": goals,
                "assists": assists,
                "points": pts,
                "score": score,
                "headshot": hs,
                "team_logo": team_logo,
            }
        )

    # sort by score (points in last_n games) descending
    results.sort(key=lambda r: r.get("score", 0), reverse=True)
    return results[: max(0, int(top_n))]
