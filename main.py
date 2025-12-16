"""
Terminal NHL predictor (uses local JSON files under src/okey/collector/statistics).
- Reads todayGames.json, teamsStats.json, playerStats.json
- Heuristic expected-goals model + Monte Carlo simulation for win probabilities
- Removed goalie and individual player contributor projections
Requires: pandas, numpy
Install: pip install pandas numpy
"""
import os
import json
import math
import random
from typing import Dict, Any, List, Optional, Tuple
import argparse

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.abspath(__file__))
STAT_DIR = os.path.join(ROOT, "src", "okey", "collector", "statistics")

TODAY_PATH = os.path.join(STAT_DIR, "todayGames.json")
TEAMS_PATH = os.path.join(STAT_DIR, "teamsStats.json")
PLAYERS_PATH = os.path.join(STAT_DIR, "playerStats.json")


def load_json(path: str):
    if not os.path.exists(path):
        print(f"Missing {path}")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_team_df(teams_raw: List[Dict[str, Any]]) -> pd.DataFrame:
    # teamsStats.json uses 'abrev' as abbreviation
    rows = []
    for t in teams_raw:
        ab = t.get("abrev") or t.get("abbrev") or ""
        gp = t.get("gamesPlayed") or 0
        ga = t.get("goalAgainst") or 0
        gd = t.get("goalDifferential") or 0
        gf = (gd + ga) if gp else None
        gf_pg = float(gf) / gp if gp else None
        ga_pg = float(ga) / gp if gp else None
        pts = t.get("points") or 0
        rows.append({
            "abbrev": ab,
            "team": t.get("team", ""),
            "gamesPlayed": gp,
            "points": pts,
            "goalFor": gf,
            "goalAgainst": ga,
            "goalDiff": gd,
            "gf_per_game": gf_pg,
            "ga_per_game": ga_pg,
            "raw": t,
        })
    return pd.DataFrame(rows)


def build_player_df(players_raw: List[Dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(players_raw)
    # keep original raw dict for flexible parsing of recent game logs
    df["raw"] = players_raw
    # normalize some fields
    if "team" in df.columns:
        df["team_abbrev"] = df["team"].astype(str)
    else:
        df["team_abbrev"] = df.get("currentTeamAbbrev", "")
    df["gamesPlayed"] = pd.to_numeric(df.get("gamesPlayed", 0), errors="coerce").fillna(0).astype(int)
    df["points"] = pd.to_numeric(df.get("points", 0), errors="coerce").fillna(0)
    # points per game (season)
    df["ppg"] = df.apply(lambda r: float(r["points"]) / r["gamesPlayed"] if r["gamesPlayed"] > 0 else 0.0, axis=1)

    # compute recent form over last 5 games when available (fallback to season ppg)
    form5 = []
    for raw in players_raw:
        val = None
        # common patterns: 'gameLog' list of games, 'lastFive' list/dict, or explicit 'last5Points'
        if isinstance(raw, dict):
            if "gameLog" in raw and isinstance(raw["gameLog"], list) and raw["gameLog"]:
                # expect most recent games first; try to extract points from each game
                gl = raw["gameLog"][:5]
                pts_sum = 0.0
                cnt = 0
                for g in gl:
                    if isinstance(g, dict):
                        pts = None
                        # try explicit points, otherwise goals+assists
                        if "points" in g and g["points"] is not None:
                            pts = g.get("points")
                        else:
                            # fallback to goals/assists if present
                            gval = g.get("goals")
                            aval = g.get("assists")
                            if (gval is not None) or (aval is not None):
                                pts = (gval or 0) + (aval or 0)
                        if pts is not None:
                            try:
                                pts_sum += float(pts)
                                cnt += 1
                            except Exception:
                                pass
                if cnt > 0:
                    val = pts_sum / cnt
            # explicit aggregated fields
            if val is None:
                if "last5Points" in raw and raw.get("last5Points") is not None:
                    try:
                        val = float(raw.get("last5Points")) / 5.0
                    except Exception:
                        val = None
                elif "recentPoints" in raw and raw.get("recentGames") in raw and raw.get("recentGames"):
                    try:
                        val = float(raw.get("recentPoints")) / int(raw.get("recentGames"))
                    except Exception:
                        val = None
                elif "lastFive" in raw and isinstance(raw["lastFive"], list) and raw["lastFive"]:
                    # lastFive as list of per-game points
                    try:
                        last = [float(x) for x in raw["lastFive"] if x is not None]
                        if last:
                            val = sum(last) / len(last)
                    except Exception:
                        val = None
        # fallback to season ppg
        if val is None:
            try:
                val = float(raw.get("points", 0)) / max(1, int(raw.get("gamesPlayed", 1)))
            except Exception:
                val = 0.0
        form5.append(float(val))

    df["form5_ppg"] = form5
    # avoid division by zero; compute form_factor (recent / season)
    df["form_factor"] = df.apply(lambda r: float(r["form5_ppg"]) / r["ppg"] if r["ppg"] > 0 else 1.0, axis=1)
    # clamp implausible ratios
    df["form_factor"] = df["form_factor"].clip(0.5, 1.5)
    return df


def expected_goals_from_team_stats(home: Dict[str, Any], away: Dict[str, Any], home_adv: float = 0.12) -> Tuple[float, float]:
    # heuristic: combine home GF/G and opponent GA/G; add a small home advantage
    h_gf = home.get("gf_per_game") or 2.7
    h_ga = home.get("ga_per_game") or 2.9
    a_gf = away.get("gf_per_game") or 2.7
    a_ga = away.get("ga_per_game") or 2.9
    # home expected = weighted average: team's scoring + opponent's concession
    lam_home = 0.55 * h_gf + 0.45 * a_ga + home_adv
    lam_away = 0.55 * a_gf + 0.45 * h_ga
    # clamp to reasonable range
    lam_home = max(0.2, min(6.0, lam_home))
    lam_away = max(0.1, min(6.0, lam_away))
    return lam_home, lam_away


def monte_carlo_game(lam_home: float, lam_away: float, sims: int = 2000) -> Dict[str, float]:
    rng = np.random.default_rng()
    home_goals = rng.poisson(lam_home, sims)
    away_goals = rng.poisson(lam_away, sims)
    home_wins = np.sum(home_goals > away_goals)
    away_wins = np.sum(home_goals < away_goals)
    draws = np.sum(home_goals == away_goals)
    avg_home = float(np.mean(home_goals))
    avg_away = float(np.mean(away_goals))
    total_avg = avg_home + avg_away
    # distribution for totals (P(total >= x))
    probs = {
        "home_win_prob": float(home_wins / sims),
        "away_win_prob": float(away_wins / sims),
        "draw_prob": float(draws / sims),
        "avg_home_goals": avg_home,
        "avg_away_goals": avg_away,
        "avg_total_goals": total_avg,
    }
    return probs


def apply_player_form_adjustment(home_ab: str, away_ab: str, players_df: pd.DataFrame, lam_home: float, lam_away: float) -> Tuple[float, float, float, float]:
    """Adjust lambdas by team player-form. Returns (lam_home_adj, lam_away_adj, home_factor, away_factor)."""
    def team_factor(abbrev: str) -> float:
        if not abbrev:
            return 1.0
        team_players = players_df[players_df["team_abbrev"].astype(str).str.upper() == abbrev.upper()]
        if team_players.empty:
            return 1.0
        # focus on regular contributors: players with some games played, take up to top 9 by gamesPlayed
        candidates = team_players[team_players["gamesPlayed"] > 0].sort_values(by="gamesPlayed", ascending=False).head(9)
        if candidates.empty:
            candidates = team_players.head(9)
        # use average form_factor; this reflects hot/cold streaks vs season rate
        avg_factor = float(candidates["form_factor"].mean())
        # clamp team factor to modest effect
        return max(0.85, min(1.15, avg_factor))

    home_factor = team_factor(home_ab)
    away_factor = team_factor(away_ab)
    lam_home_adj = lam_home * home_factor
    lam_away_adj = lam_away * away_factor
    return lam_home_adj, lam_away_adj, home_factor, away_factor


def _player_display_name(raw: Dict[str, Any]) -> str:
    for k in ("fullName", "name", "playerName", "displayName", "player"):
        if isinstance(raw.get(k), str) and raw.get(k).strip():
            return raw.get(k).strip()
    # fallback to id
    return str(raw.get("id", raw.get("playerId", "unknown")))


def _is_goalie(raw: Dict[str, Any]) -> bool:
    # common patterns: position as string or dict with code/abbrev
    pos = raw.get("position") or raw.get("pos") or {}
    if isinstance(pos, dict):
        code = (pos.get("code") or pos.get("abbrev") or pos.get("name") or "").upper()
        return "G" in code or "GOAL" in code
    if isinstance(pos, str):
        p = pos.upper()
        return "G" in p or "GOAL" in p
    return False


def _safe_num(x, default=0.0):
    try:
        if x is None:
            return default
        if isinstance(x, (int, float)):
            return x
        s = str(x).replace("+", "").strip()
        return float(s)
    except Exception:
        return default


def _parse_toi(toi) -> float:
    """Parse time-on-ice value to minutes (float). Accepts 'MM:SS' or numeric minutes."""
    if toi is None:
        return 0.0
    if isinstance(toi, (int, float)):
        return float(toi)
    s = str(toi).strip()
    if ":" in s:
        try:
            mm, ss = s.split(":", 1)
            return float(mm) + float(ss) / 60.0
        except Exception:
            return 0.0
    try:
        return float(s)
    except Exception:
        return 0.0


def _effective_players_for_game(game: Dict[str, Any], players_df: pd.DataFrame) -> pd.DataFrame:
    """Return players participating in the game with an expanded effectiveness score.

    Score components (weighted):
      - recent form (form5_ppg) and season ppg
      - offensive activity: shots, shots on goal, shooting %
      - usage: time on ice per game
      - possession proxy: corsi/fenwick %
      - defensive actions: hits + blocks
      - plus/minus / PIM and games-played stabilizer

    The function tolerates many field-name variants from different JSON sources.
    """
    home_ab = (game.get("homeTeam") or {}).get("abbrev") or ""
    away_ab = (game.get("awayTeam") or {}).get("abbrev") or ""
    team_codes = {str(home_ab).upper(), str(away_ab).upper()}

    rows = []
    for _, r in players_df.iterrows():
        raw = r.get("raw") if isinstance(r.get("raw"), dict) else (r.get("raw") or {})
        team = str(r.get("team_abbrev", "")).upper()
        if team not in team_codes:
            continue
        # skip goalies
        if _is_goalie(raw):
            continue

        name = _player_display_name(raw)
        gp = int(r.get("gamesPlayed", 0))
        form5 = float(r.get("form5_ppg", 0.0))
        ppg = float(r.get("ppg", 0.0))

        # season / aggregate counts — try common keys, then fallbacks
        shots_total = _safe_num(raw.get("shots", raw.get("shotsTotal", raw.get("shotsFor", None))), 0.0)
        sog_total = _safe_num(raw.get("shotsOnGoal", raw.get("sog", None)), 0.0)
        hits_total = _safe_num(raw.get("hits", raw.get("h", None)), 0.0)
        blocks_total = _safe_num(raw.get("blocked", raw.get("blocks", None)), 0.0)
        plus_minus = _safe_num(raw.get("plusMinus", raw.get("plus_minus", None)), 0.0)
        pim = _safe_num(raw.get("penaltyMinutes", raw.get("pim", None)), 0.0)

        # possession / shot metrics
        corsi_pct = _safe_num(raw.get("corsiForPct", raw.get("cf_pct", raw.get("corsi_pct", None))), 50.0)
        fenwick_pct = _safe_num(raw.get("fenwickForPct", raw.get("ff_pct", None)), 50.0)
        shooting_pct = _safe_num(raw.get("shootingPct", raw.get("shPct", raw.get("shootingPercentage", None))), 0.0)

        # time on ice: can be per-game string "12:34" or numeric total/minutes-per-game
        toi_raw = raw.get("timeOnIcePerGame", raw.get("timeOnIce", raw.get("toi", None)))
        toi_min = _parse_toi(toi_raw)

        # convert totals to per-game where appropriate
        shots_pg = shots_total / gp if gp > 0 else 0.0
        sog_pg = sog_total / gp if gp > 0 else 0.0
        hits_pg = hits_total / gp if gp > 0 else 0.0
        blocks_pg = blocks_total / gp if gp > 0 else 0.0
        pim_pg = pim / gp if gp > 0 else pim  # sometimes pim already per-game

        # Compose score (weights chosen to prioritize recent form + activity)
        w_form_recent = 0.40
        w_form_season = 0.15
        w_shots = 0.12
        w_sog = 0.08
        w_toi = 0.10
        w_possession = 0.08
        w_defense = 0.07

        form_component = w_form_recent * form5 + w_form_season * ppg
        activity_component = w_shots * shots_pg + w_sog * sog_pg
        toi_component = w_toi * (toi_min / 20.0)  # normalize by ~20 min to keep scale small
        possession_component = w_possession * ((corsi_pct - 50.0) / 50.0)  # roughly -1..+1 scaled
        defense_component = w_defense * ((hits_pg + blocks_pg) / 2.0)

        base_score = form_component + activity_component + toi_component + possession_component + defense_component

        # penalties / small adjustments
        plus_adj = 0.06 * (plus_minus / 1.0)         # boost for positive +/- (small)
        pim_penalty = 0.03 * pim_pg                  # penalize excessive PIM per game
        gp_penalty = 0.25 if gp < 3 else 0.0          # penalize tiny sample sizes

        adj_score = base_score + plus_adj - pim_penalty - gp_penalty

        # tie-breaker: season ppg and games played
        tie_break = (ppg * 0.002) + (min(gp, 82) / 1000.0)

        rows.append({
            "name": name,
            "team": team,
            "gamesPlayed": gp,
            "form5_ppg": form5,
            "ppg": ppg,
            "shots_pg": shots_pg,
            "sog_pg": sog_pg,
            "toi_min": toi_min,
            "corsi_pct": corsi_pct,
            "fenwick_pct": fenwick_pct,
            "hits_pg": hits_pg,
            "blocks_pg": blocks_pg,
            "plusMinus": plus_minus,
            "pim": pim,
            "base_score": base_score,
            "adj_score": adj_score + tie_break,
        })

    if not rows:
        return pd.DataFrame(rows)

    df = pd.DataFrame(rows)
    # sort descending for top players
    return df.sort_values(by="adj_score", ascending=False).reset_index(drop=True)

# new helper to produce human-readable explanations for low-effect players
def _describe_least_effective(p: pd.Series) -> str:
    """Return a short explanation why a player is considered 'least effective' (varied sentences)."""
    name = str(p.get("name", "Unknown"))
    gp = int(p.get("gamesPlayed", 0) or 0)
    season_ppg = float(p.get("ppg", 0.0) or 0.0)
    recent = float(p.get("form5_ppg", 0.0) or 0.0)
    shots_pg = float(p.get("shots_pg", 0.0) or 0.0)
    toi = float(p.get("toi_min", 0.0) or 0.0)
    plus = float(p.get("plusMinus", 0.0) or 0.0)
    pim = float(p.get("pim", 0.0) or 0.0)
    adj = float(p.get("adj_score", 0.0) or 0.0)

    reasons = []
    if season_ppg > 0 and recent < season_ppg * 0.6:
        reasons.append(f"recent form down ({recent:.2f} ppg vs season {season_ppg:.2f})")
    elif recent == 0 and season_ppg == 0:
        reasons.append("no scoring this season")
    elif recent == 0 and season_ppg > 0:
        reasons.append(f"no points in last 5 ({recent:.2f} ppg)")

    # usage / sample size
    if gp < 5:
        reasons.append(f"small sample ({gp} games)")
    if toi > 0 and toi < 10:
        reasons.append(f"limited usage (~{toi:.1f} min TOI/game)")

    # activity
    if shots_pg < 0.5:
        reasons.append(f"low shot volume ({shots_pg:.2f} S/G)")

    # defense / discipline
    if plus < 0:
        reasons.append(f"negative +/- ({plus:+.0f})")
    if pim > 5:
        reasons.append(f"high PIM ({pim:.0f}) reducing availability")

    if not reasons:
        reasons.append("adj score low due to model weights (form/usage/activity)")

    templates = [
        f"    {name} is less effective because " + ", ".join(reasons) + ".",
        f"    {name} has struggled recently: " + ", ".join(reasons) + ".",
        f"    {name} shows reduced impact — " + ", ".join(reasons) + ".",
        f"    {name} is a concern: " + ", ".join(reasons) + ".",
    ]
    return random.choice(templates)


def _describe_hot_player(p: pd.Series) -> str:
    """Return a short varied explanation highlighting why a player is 'hot'."""
    name = str(p.get("name", "Unknown"))
    gp = int(p.get("gamesPlayed", 0) or 0)
    season_ppg = float(p.get("ppg", 0.0) or 0.0)
    recent = float(p.get("form5_ppg", 0.0) or 0.0)
    shots_pg = float(p.get("shots_pg", 0.0) or 0.0)
    toi = float(p.get("toi_min", 0.0) or 0.0)
    corsi = float(p.get("corsi_pct", 50.0) or 50.0)
    plus = float(p.get("plusMinus", 0.0) or 0.0)
    adj = float(p.get("adj_score", 0.0) or 0.0)

    highlights = []
    if season_ppg == 0 and recent > 0:
        highlights.append(f"caught fire recently ({recent:.2f} ppg in last 5)")
    elif recent > season_ppg * 1.25:
        highlights.append(f"hot streak ({recent:.2f} ppg vs season {season_ppg:.2f})")
    elif recent > 0 and recent >= season_ppg:
        highlights.append(f"consistent recent scoring ({recent:.2f} ppg)")

    if shots_pg >= 2.0:
        highlights.append(f"high shot volume ({shots_pg:.2f} S/G)")
    if toi >= 15:
        highlights.append(f"heavy usage (~{toi:.1f} min TOI/game)")
    if corsi >= 55:
        highlights.append(f"strong possession (Corsi {corsi:.0f}%)")
    if plus > 0:
        highlights.append(f"positive +/- ({plus:+.0f})")

    if not highlights:
        highlights.append("recent form and usage indicate above-average impact")

    templates = [
        f"    {name} is heating up: " + ", ".join(highlights) + ".",
        f"    Expect production from {name} — " + ", ".join(highlights) + ".",
        f"    {name} looks dangerous right now: " + ", ".join(highlights) + ".",
        f"    {name} has momentum: " + ", ".join(highlights) + ".",
    ]
    return random.choice(templates)


def _print_sep(width: int = 88, ch: str = "-"):
    print(ch * width)

def display_games_list(today: List[Dict[str, Any]]):
    width = 88
    print()
    print("=" * width)
    header = f" Today's games ({len(today)}) "
    print(header.center(width))
    _print_sep(width)
    print(f"{'#':>3}  {'Home':20} vs {'Away':20}  {'Start(UTC)':12}  {'Venue':25}")
    _print_sep(width)
    for i, g in enumerate(today):
        home = ((g.get("homeTeam") or {}).get("abbrev") or "")[:20]
        away = ((g.get("awayTeam") or {}).get("abbrev") or "")[:20]
        time = (g.get("startTimeUTC") or "")[:12]
        venue = (g.get("venue") or "")[:25]
        print(f"{i:>3}  {home:20} vs {away:20}  {time:12}  {venue:25}")
    _print_sep(width)
    print()

def _format_team_line(label: str, gf_pg: float, ga_pg: float, pts: int) -> str:
    return f"{label:>6}: GF/G={gf_pg:4.2f}  GA/G={ga_pg:4.2f}  pts={pts:3d}"

def _format_player_line(p: pd.Series) -> str:
    name = str(p.get("name", "Unknown"))
    team = str(p.get("team", ""))
    adj = float(p.get("adj_score", 0.0))
    recent = float(p.get("form5_ppg", 0.0))
    season = float(p.get("ppg", 0.0))
    plus = float(p.get("plusMinus", 0.0))
    pim = float(p.get("pim", 0.0))
    shots = float(p.get("shots_pg", 0.0))
    toi = float(p.get("toi_min", 0.0))
    return (f"{name:20.20} {team:3}  adj={adj:7.3f}  recent={recent:4.2f}  season={season:4.2f}  "
            f"+/−={plus:+4.0f}  PIM={pim:3.0f}  shots={shots:4.2f}  TOI={toi:4.1f}m")


def summarize_game(game: Dict[str, Any], teams_df: pd.DataFrame, players_df: pd.DataFrame):
    home_ab = game.get("homeTeam", {}).get("abbrev") or ""
    away_ab = game.get("awayTeam", {}).get("abbrev") or ""
    start = game.get("startTimeUTC") or ""
    date = game.get("date") or ""
    venue = game.get("venue") or ""
    width = 88
    print()
    print("=" * width)
    title = f"{home_ab} (HOME)  vs  {away_ab} (AWAY)"
    meta = f"{date}  @ {start}  —  {venue}"
    print(title.center(width))
    print(meta.center(width))
    _print_sep(width, "-")

    th = teams_df[teams_df["abbrev"].str.upper() == home_ab.upper()]
    ta = teams_df[teams_df["abbrev"].str.upper() == away_ab.upper()]
    if th.empty or ta.empty:
        print("Missing team stats for one side — aborting this match.")
        print("=" * width)
        return
    home = th.iloc[0].to_dict()
    away = ta.iloc[0].to_dict()

    print(_format_team_line("Home", home.get("gf_per_game", 0.0), home.get("ga_per_game", 0.0), int(home.get("points", 0))))
    print(_format_team_line("Away", away.get("gf_per_game", 0.0), away.get("ga_per_game", 0.0), int(away.get("points", 0))))
    lam_h, lam_a = expected_goals_from_team_stats(home, away)
    print(f"Model expected goals (lambda): home={lam_h:.2f}, away={lam_a:.2f}")
    _print_sep(width, "-")

    lam_h_adj, lam_a_adj, hf, af = apply_player_form_adjustment(home_ab, away_ab, players_df, lam_h, lam_a)
    if hf != 1.0 or af != 1.0:
        print(f"Applied player-form adjustments — home_factor={hf:.3f}  away_factor={af:.3f}")
        print(f"Adjusted lambdas: home={lam_h_adj:.2f}, away={lam_a_adj:.2f}")
        _print_sep(width, "-")

    mc = monte_carlo_game(lam_h_adj, lam_a_adj, sims=3000)
    print(f"Win probs — Home: {mc['home_win_prob']*100:5.1f}%  Away: {mc['away_win_prob']*100:5.1f}%  Draw: {mc['draw_prob']*100:5.1f}%")
    print(f"Expected goals — home: {mc['avg_home_goals']:.2f}  away: {mc['avg_away_goals']:.2f}  total: {mc['avg_total_goals']:.2f}")
    _print_sep(width, "-")

    eff_df = _effective_players_for_game(game, players_df)
    if eff_df.empty:
        print("No skater player data available for this game (missing players or only goalies).")
    else:
        top_n = 3
        top_players = eff_df.head(top_n)
        bottom_candidates = eff_df[eff_df["adj_score"] != 0].sort_values(by="adj_score", ascending=True)
        if len(bottom_candidates) < top_n:
            bottom_players = eff_df.sort_values(by="adj_score", ascending=True).head(top_n)
        else:
            bottom_players = bottom_candidates.head(top_n)

        print("Top players (hot):")
        for _, p in top_players.iterrows():
            print("  " + _format_player_line(p))
            print("   " + _describe_hot_player(p).strip())

        _print_sep(width, ".")

        print("Least effective players (cold):")
        for _, p in bottom_players.iterrows():
            print("  " + _format_player_line(p))
            print("   " + _describe_least_effective(p).strip())

    _print_sep(width)
    prob_over_5 = np.mean((np.random.poisson(lam_h_adj, 3000) + np.random.poisson(lam_a_adj, 3000)) > 5)
    prob_over_6 = np.mean((np.random.poisson(lam_h_adj, 3000) + np.random.poisson(lam_a_adj, 3000)) > 6)
    print(f"Totals: P(total>5)={prob_over_5*100:4.1f}%   P(total>6)={prob_over_6*100:4.1f}%")
    print("=" * width)
    print()

def find_game_by_team(today: List[Dict[str, Any]], team_code: str) -> List[int]:
    """Return list of indices where team_code matches home or away abbrev (case-insensitive)."""
    if not team_code:
        return []
    tc = team_code.strip().upper()
    matches = []
    for i, g in enumerate(today):
        ha = (g.get("homeTeam") or {}).get("abbrev") or (g.get("homeTeam") or {}).get("abbrev", "")
        aa = (g.get("awayTeam") or {}).get("abbrev") or (g.get("awayTeam") or {}).get("abbrev", "")
        if not ha: ha = ""
        if not aa: aa = ""
        if tc == ha.upper() or tc == aa.upper():
            matches.append(i)
        else:
            # allow partial match (e.g. "MTL" vs "MON" variants), check contains
            if tc in ha.upper() or tc in aa.upper():
                matches.append(i)
    return matches


def main():
    parser = argparse.ArgumentParser(prog="main.py", description="OKey - Terminal NHL Match Predictor")
    parser.add_argument("-g", "--game", help="Select a game by team abbrev (home or away), e.g. --game mtl")
    parser.add_argument("-i", "--index", type=int, help="Select game by index (shown in list)")
    parser.add_argument("-a", "--all", action="store_true", help="Analyze all games and exit")
    args = parser.parse_args()

    # If no CLI flags provided, exit silently (produce no terminal output).
    if not (args.all or args.index is not None or args.game):
        return

    today = load_json(TODAY_PATH) or []
    teams_raw = load_json(TEAMS_PATH) or []
    players_raw = load_json(PLAYERS_PATH) or []

    teams_df = build_team_df(teams_raw)
    players_df = build_player_df(players_raw)

    if not today:
        print("No games found in todayGames.json")
        return

    # Require the user to supply one of the argparse options before listing games.
    if not (args.all or args.index is not None or args.game):
        # Don't show the full help menu automatically — fall back to interactive mode.
        print("No mode selected. Running in interactive mode (use --game / --index / --all to run non-interactively).")
        # continue on to list games and enter the interactive loop below


    print(f"Found {len(today)} games today.")
    for i, g in enumerate(today):
        home = (g.get("homeTeam") or {}).get("abbrev") or ""
        away = (g.get("awayTeam") or {}).get("abbrev") or ""
        print(f"[{i}] {home} vs {away} — {g.get('startTimeUTC')} @ {g.get('venue')}")

    # CLI modes: all, index, game, else interactive
    if args.all:
        for g in today:
            summarize_game(g, teams_df, players_df)
        return

    if args.index is not None:
        idx = args.index
        if idx < 0 or idx >= len(today):
            print("Index out of range")
            return
        summarize_game(today[idx], teams_df, players_df)
        return

    if args.game:
        matches = find_game_by_team(today, args.game)
        if not matches:
            print(f"No game found with team '{args.game}' in today's slate.")
            return
        if len(matches) > 1:
            print(f"Multiple matches found for '{args.game}', showing the first one (indices: {matches})")
        summarize_game(today[matches[0]], teams_df, players_df)
        return

    # fallback to original interactive loop
    while True:
        sel = input("\nEnter game index to analyze (or 'all' / 'exit'): ").strip().lower()
        if sel in ("exit", "quit"):
            break
        if sel == "all":
            for g in today:
                summarize_game(g, teams_df, players_df)
            continue
        if not sel.isdigit():
            print("Enter a number or 'all'")
            continue
        idx = int(sel)
        if idx < 0 or idx >= len(today):
            print("Index out of range")
            continue
        summarize_game(today[idx], teams_df, players_df)


if __name__ == "__main__":
    main()