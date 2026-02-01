#!/usr/bin/env python3
"""Flask web app for browsing NHL player and team statistics.

Routes:
  /           - index
  /players    - list players (from stats/playerStats.json)
  /player/<key> - player detail by `nameKey` or numeric id
  /teams      - list teams (from stats/teamsStats.json)
  /headshots/<path:filename> - serve or redirect to headshot image

This app reads local JSON files produced by the collector (stats/playerStats.json
and stats/teamsStats.json). It intentionally avoids any external API calls.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

STATS_DIR = os.path.join(REPO_ROOT, "stats")
PLAYER_FILE = os.path.join(STATS_DIR, "playerStats.json")
TEAM_FILE = os.path.join(STATS_DIR, "teamsStats.json")


def load_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def create_app():
    try:
        from flask import Flask, render_template, abort, redirect, request, send_from_directory, jsonify
    except Exception:
        raise

    app = Flask(__name__)

    @app.route("/")
    def index():
        # load top featured players to show on the index page
        players = load_json(PLAYER_FILE) or []
        try:
            featured = sorted([p for p in players if isinstance(p, dict)], key=lambda x: x.get("points") or 0, reverse=True)[:8]
        except Exception:
            featured = players[:8]

        # compute 'hot' players from recent games when possible
        try:
            from stats import analyst

            hot_players = analyst.hottest_players(players, top_n=3, last_n=5)
        except Exception:
            hot_players = []

        return render_template("index.html", featured=featured, hot_players=hot_players)

    @app.route("/players")
    def players():
        players = load_json(PLAYER_FILE) or []
        # allow simple query param filtering
        q = (request.args.get("q") or "").strip().lower()
        if q:
            filtered = []
            for p in players:
                if not isinstance(p, dict):
                    continue
                name = (p.get("name") or "").lower()
                nid = str(p.get("id", ""))
                key = (p.get("nameKey") or "").lower()
                if q in name or q == nid or q in key:
                    filtered.append(p)
            players = filtered
        # sort by points desc if present
        try:
            players = sorted(players, key=lambda x: x.get("points") or 0, reverse=True)
        except Exception:
            pass
        return render_template("players.html", players=players)

    @app.route("/_search_players")
    def search_players():
        # simple JSON endpoint for autocomplete on the players page
        players = load_json(PLAYER_FILE) or []
        q = (request.args.get("q") or "").strip().lower()
        if not q:
            return jsonify([])
        matches = []
        for p in players:
            if not isinstance(p, dict):
                continue
            name = (p.get("name") or "").lower()
            nid = str(p.get("id", ""))
            key = (p.get("nameKey") or "").lower()
            if q in name or q == nid or q in key:
                matches.append({
                    "name": p.get("name"),
                    "id": p.get("id"),
                    "nameKey": p.get("nameKey"),
                    "headshot": p.get("headshot"),
                    "team": p.get("team"),
                })
            if len(matches) >= 12:
                break
        return jsonify(matches)

    @app.route("/player/<key>")
    def player_detail(key: str):
        players = load_json(PLAYER_FILE) or []
        found = None
        for p in players:
            if not isinstance(p, dict):
                continue
            if str(p.get("id")) == key or (p.get("nameKey") or "") == key:
                found = p
                break
        if not found:
            abort(404)
        return render_template("player_detail.html", p=found)

    @app.route("/teams")
    def teams():
        teams = load_json(TEAM_FILE) or []
        # group teams by division and sort by divisionSequence (position)
        try:
            from collections import defaultdict
            divs = defaultdict(list)
            for t in teams:
                div = t.get('division') or t.get('divisionAbbrev') or t.get('conference') or 'Unknown'
                divs[div].append(t)
            # sort each division by divisionSequence if present, fallback to points desc
            for k in divs:
                divs[k].sort(key=lambda x: x.get('divisionSequence') or -int(x.get('points', 0)), reverse=False)
            # create an ordered list of (division_name, teams_list)
            divisions = [(k, divs[k]) for k in sorted(divs.keys())]
        except Exception:
            divisions = [(None, teams)]

        return render_template("teams.html", divisions=divisions)

    @app.route("/_teams")
    def teams_json():
        teams = load_json(TEAM_FILE) or []
        return jsonify(teams)

    @app.route("/bracket")
    def bracket():
        """Compute a simple playoff bracket if the playoffs started now.

        Approach: pick top 8 teams by `points` in each conference and seed 1..8
        then pair: 1 vs 8, 2 vs 7, 3 vs 6, 4 vs 5. This is a straightforward
        conference-based bracket (not the full NHL divisional wildcard pairing
        complexity) but answers "if playoffs started now" clearly.
        """
        teams = load_json(TEAM_FILE) or []
        by_conf = {}
        for t in teams:
            conf = t.get("conferenceAbbrev") or t.get("conference") or "Unknown"
            by_conf.setdefault(conf, []).append(t)

        bracket = {}
        for conf, lst in by_conf.items():
            # group teams by division inside the conference
            divs = {}
            for t in lst:
                div = t.get("divisionAbbrev") or t.get("division") or "Unknown"
                divs.setdefault(div, []).append(t)

            # sort each division by divisionSequence (1 is top) or by points
            for k in divs:
                try:
                    divs[k] = sorted(divs[k], key=lambda x: x.get("divisionSequence") or 999)
                except Exception:
                    divs[k] = sorted(divs[k], key=lambda x: x.get("points", 0), reverse=True)

            # If we have exactly two divisions for the conference, build NHL-style bracket
            if len(divs) == 2:
                # collect automatic qualifiers: top 3 from each division (if available)
                auto = []
                for k in divs:
                    auto.extend(divs[k][:3])

                # wild-card teams: the next two highest-point teams in the conference not already auto-qualified
                remaining = [t for t in lst if t not in auto]
                try:
                    remaining = sorted(remaining, key=lambda x: x.get("points", 0), reverse=True)
                except Exception:
                    pass
                wildcards = remaining[:2]

                # identify division winners and their divisions
                div_items = list(divs.items())
                # ensure stable order
                div1_name, div1_list = div_items[0]
                div2_name, div2_list = div_items[1]
                div1_winner = div1_list[0] if div1_list else None
                div2_winner = div2_list[0] if div2_list else None

                # sort division winners by points to find the top division winner
                winners = [w for w in (div1_winner, div2_winner) if w]
                try:
                    winners = sorted(winners, key=lambda x: x.get("points", 0), reverse=True)
                except Exception:
                    pass

                top_div_winner = winners[0] if winners else None
                other_div_winner = winners[1] if len(winners) > 1 else None

                # determine higher/lower wildcards by points
                try:
                    wild_sorted = sorted(wildcards, key=lambda x: x.get("points", 0), reverse=True)
                except Exception:
                    wild_sorted = wildcards
                higher_wild = wild_sorted[0] if len(wild_sorted) > 0 else None
                lower_wild = wild_sorted[1] if len(wild_sorted) > 1 else (wild_sorted[0] if wild_sorted else None)

                # Build structured first-round slots so we can place them visually
                # upper: top division winner vs lower wild, and that division's 2v3
                # lower: other division winner vs higher wild, and that division's 2v3
                # determine which div list corresponds to the top_div_winner
                if top_div_winner and top_div_winner is div1_winner:
                    top_div_list = div1_list
                    other_div_list = div2_list
                else:
                    top_div_list = div2_list
                    other_div_list = div1_list

                upper = []
                # top division winner vs lower wild
                upper.append((1, top_div_list[0] if top_div_list else None, None, lower_wild))
                # top division 2 vs 3
                upper.append((2, top_div_list[1] if len(top_div_list) > 1 else None, 3, top_div_list[2] if len(top_div_list) > 2 else None))

                lower = []
                # other division winner vs higher wild
                lower.append((1, other_div_list[0] if other_div_list else None, None, higher_wild))
                # other division 2 vs 3
                lower.append((2, other_div_list[1] if len(other_div_list) > 1 else None, 3, other_div_list[2] if len(other_div_list) > 2 else None))

                bracket[conf] = {"upper": upper, "lower": lower}
            else:
                # fallback: simple top-8 seeding by points (1v8,2v7,...)
                try:
                    sorted_lst = sorted(lst, key=lambda x: x.get("points", 0), reverse=True)
                except Exception:
                    sorted_lst = lst
                seeds = sorted_lst[:8]
                matchups = []
                for i in range(4):
                    a = seeds[i] if len(seeds) > i else None
                    b = seeds[7 - i] if len(seeds) > 7 - i else None
                    matchups.append((i + 1, a, 8 - i, b))
                bracket[conf] = matchups

        return render_template("bracket.html", bracket=bracket)

    @app.route('/headshots/<path:filename>')
    def headshot_proxy(filename: str):
        # Many headshot URLs in player JSON are full remote URLs; simply redirect to them
        # But also support local files under stats/headshots if you place them there.
        # Prefer local file if exists
        local_dir = os.path.join(STATS_DIR, "headshots")
        local_path = os.path.join(local_dir, filename)
        if os.path.exists(local_path):
            return send_from_directory(local_dir, filename)
        # otherwise assume filename is a full URL
        # unescape and redirect
        return redirect(filename)

    return app


if __name__ == '__main__':
    try:
        app = create_app()
    except Exception:
        print("Flask not installed. Install with: pip install flask", file=sys.stderr)
        raise
    app.run(host='127.0.0.1', port=5000, debug=True)
