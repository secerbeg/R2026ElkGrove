#!/usr/bin/env python3
"""Fetch the public Roseville MLS Assist JSON; never invent or overwrite on failure."""
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
import argparse
import json

DEFAULT_URL = 'https://mls-assist.theintelligenceplatform.com/data/schedule/mls-next-cup-qualifier-roseville-regional.json'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default=DEFAULT_URL)
    parser.add_argument('--out', default='data/published-schedule.json')
    args = parser.parse_args()
    req = Request(args.url, headers={'User-Agent':'ElkGroveRosevilleSchedule/1.0 (public tournament updates)', 'Accept':'application/json','Cache-Control':'no-cache'})
    with urlopen(req, timeout=25) as response:
        if response.status != 200:
            raise RuntimeError(f'Published feed returned HTTP {response.status}')
        payload = json.load(response)
    if not isinstance(payload, dict) or not isinstance(payload.get('events'), list):
        raise ValueError('Published response has no valid events list')
    payload['_site_fetched_at'] = datetime.now(timezone.utc).isoformat().replace('+00:00','Z')
    payload['_source_url'] = DEFAULT_URL if args.url == DEFAULT_URL else args.url
    path=Path(args.out)
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp = path.with_suffix('.json.tmp')
    tmp.write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':'))+'\n')
    tmp.replace(path)
    print(f"Fetched {len(payload['events'])} events at {payload['_site_fetched_at']}")

if __name__=='__main__':
    main()
