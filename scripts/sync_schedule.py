#!/usr/bin/env python3
"""Fetch Roseville MLS Assist JSON and prepare safe GitHub Pages deployment.

Network failures preserve the previous successfully published snapshot if available.
Nothing is represented as official published data unless fetched from validated source.
"""
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

FEED_URL = 'https://mls-assist.theintelligenceplatform.com/data/schedule/mls-next-cup-qualifier-roseville-regional.json'
OLD_SITE_URL = 'https://secerbeg.github.io/R2026ElkGrove/data/published-schedule.json'
COMPETITION_KEY = 'mls-next-cup-qualifier-roseville-regional'
DATA = Path(__file__).resolve().parents[1] / 'data'
DATA.mkdir(parents=True, exist_ok=True)
SNAPSHOT = DATA / 'published-schedule.json'
STATUS = DATA / 'feed-status.json'


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def fetch_json(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Roseville-Elk-Grove-Schedule-Sync/1.0', 'Accept': 'application/json', 'Cache-Control': 'no-cache'})
    with urllib.request.urlopen(req, timeout=20) as response:
        data = response.read(5_000_001)
        if len(data) > 5_000_000:
            raise ValueError('Feed exceeded size limit')
    return json.loads(data.decode('utf-8'))


def validate(obj):
    if not isinstance(obj, dict) or not isinstance(obj.get('events'), list):
        raise ValueError('Expected JSON object containing events array')
    linked = obj.get('linked_competition_seasons')
    if not isinstance(linked, list) or COMPETITION_KEY not in [v.get('key') for v in linked if isinstance(v, dict)]:
        raise ValueError('Competition key missing or incorrect')
    return obj


def write_json(path, obj):
    target = path.with_suffix(path.suffix + '.tmp')
    target.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    target.replace(path)


def recover():
    if SNAPSHOT.exists():
        try:
            return validate(json.loads(SNAPSHOT.read_text(encoding='utf-8')))
        except Exception:
            pass
    try:
        prior = validate(fetch_json(OLD_SITE_URL))
        # Require a timestamp proving this was saved by our workflow, not an undated draft.
        if not prior.get('_site_fetched_at'):
            raise ValueError('Previous snapshot missing sync metadata')
        write_json(SNAPSHOT, prior)
        print('Recovered previously deployed published JSON')
        return prior
    except Exception as exc:
        print('Previous snapshot unavailable:', exc)
        return None


def main():
    checked_at = utc_now()
    error = None
    for attempt in range(1, 4):
        try:
            result = validate(fetch_json(FEED_URL))
            result['_site_fetched_at'] = checked_at
            write_json(SNAPSHOT, result)
            write_json(STATUS, {'state': 'ok', 'checked_at': checked_at, 'last_success_at': checked_at, 'source_synced_at': result.get('synced_at'), 'event_count': len(result['events'])})
            print(f'Successfully synced Roseville: {len(result["events"])} published fixtures; provider sync {result.get("synced_at")}')
            return 0
        except Exception as exc:
            error = str(exc)
            print(f'Fetch attempt {attempt}/3 failed: {error}', file=sys.stderr)
            if attempt < 3:
                time.sleep(3)
    prior = recover()
    write_json(STATUS, {'state': 'error', 'checked_at': checked_at, 'last_success_at': prior.get('_site_fetched_at') if prior else None, 'source_synced_at': prior.get('synced_at') if prior else None, 'event_count': len(prior['events']) if prior else None, 'error': error})
    print('Upstream feed not reachable. Published previous snapshot if available, otherwise only failure status.')
    return 0  # Deploy status page even if upstream feed was temporarily unavailable.


if __name__ == '__main__':
    sys.exit(main())
