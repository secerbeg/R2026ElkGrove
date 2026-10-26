#!/usr/bin/env python3
"""Sync publicly available Roseville fixtures to a local JSON snapshot.
Does not use private Kitman credentials or unpublished APIs.
"""
import json
import pathlib
import urllib.request

URL = "https://mls-assist.theintelligenceplatform.com/data/schedule/mls-next-cup-qualifier-roseville-regional.json"
OUTPUT = pathlib.Path(__file__).resolve().parents[1] / "data" / "published-schedule.json"

req = urllib.request.Request(URL, headers={"User-Agent": "RosevilleScheduleViewer/1.0 (public-feed-fetch)", "Accept": "application/json"})
with urllib.request.urlopen(req, timeout=25) as response:
    if response.status != 200:
        raise RuntimeError(f"HTTP {response.status}")
    data = json.load(response)
if not isinstance(data, dict) or not isinstance(data.get("events"), list):
    raise ValueError("Unexpected JSON data: missing events list")
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
content = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
# Avoid committing identical data.
if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != content:
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"Updated {OUTPUT.name}: {len(data['events'])} published events")
else:
    print(f"No changes: {len(data['events'])} published events")
