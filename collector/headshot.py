#!/usr/bin/env python3
"""Download NHL player headshots listed in src/stats/playerStats.json

Saves images to: src/headshots/

Usage:
  python collector/headshot.py [--workers N] [--force] [--limit N]

Options:
  --workers N   Number of parallel downloads (default 6)
  --force       Re-download files even if they exist
  --limit N     Stop after N images (for testing)
  --quiet       Minimal output
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def load_players(stats_path: str) -> list[dict]:
    with open(stats_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    players = []
    for p in data:
        if not isinstance(p, dict):
            continue
        url = p.get("headshot") or p.get("heroImage")
        key = p.get("nameKey") or p.get("name") or str(p.get("id", "unknown"))
        if url and key:
            players.append({"nameKey": key, "url": url, "id": p.get("id")})
    return players


def sane_filename(name: str) -> str:
    # remove any characters that might be problematic in filenames
    keep = "abcdefghijklmnopqrstuvwxyz0123456789-_"
    name = name.lower().replace(" ", "_")
    return "".join(c for c in name if c in keep)


def download_one(item: dict, dest_dir: str, force: bool = False, quiet: bool = False) -> tuple[str, bool, str]:
    """Download one headshot. Returns (filename, ok, message)"""
    url = item["url"]
    key = item["nameKey"]
    parsed = urllib.parse.urlparse(url)
    base = os.path.basename(parsed.path)
    _, ext = os.path.splitext(base)
    if not ext:
        # fallback
        ext = ".png"

    fname = sane_filename(key) or f"{item.get('id','unknown')}"
    out_path = os.path.join(dest_dir, f"{fname}{ext}")

    if os.path.exists(out_path) and not force:
        return (out_path, True, "exists")

    headers = {"User-Agent": "okey-headshot-collector/1.0"}
    req = urllib.request.Request(url, headers=headers)

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
            # write atomically
            tmp = out_path + ".tmp"
            with open(tmp, "wb") as out:
                out.write(data)
            os.replace(tmp, out_path)
        if not quiet:
            print(f"Saved: {out_path}")
        return (out_path, True, "downloaded")
    except urllib.error.HTTPError as e:
        return (out_path, False, f"http {e.code}")
    except Exception as e:
        return (out_path, False, f"error {e}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download player headshots into /headshots")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    stats_path = os.path.join(repo_root, "stats", "playerStats.json")
    out_dir = os.path.join(repo_root, "headshots")
    os.makedirs(out_dir, exist_ok=True)

    if not os.path.exists(stats_path):
        print("Cannot find playerStats.json at", stats_path, file=sys.stderr)
        return 2

    players = load_players(stats_path)
    if args.limit and args.limit > 0:
        players = players[: args.limit]

    if not args.quiet:
        print(f"Found {len(players)} players. Downloading to: {out_dir}")

    results = []
    start = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = [ex.submit(download_one, p, out_dir, args.force, args.quiet) for p in players]
        for fut in concurrent.futures.as_completed(futures):
            try:
                results.append(fut.result())
            except Exception as e:
                results.append(("", False, f"exception {e}"))

    ok = sum(1 for _, s, _ in results if s)
    bad = len(results) - ok
    if not args.quiet:
        print(f"Done. {ok} saved, {bad} failed in {time.time()-start:.1f}s")

    # exit code 0 if at least one succeeded
    return 0 if ok > 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
