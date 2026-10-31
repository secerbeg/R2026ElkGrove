#!/usr/bin/env python3
"""Roseville MLS NEXT: synchronize fixtures and the separate standings/results feed.

Stdlib-only, GitHub Actions compatible, preserves last valid snapshots on errors.
The standings JSON schema is not published; import ONLY match objects with an
unambiguous match ID, explicit score pair, and no indication of an unplayed match.
The full standings response is also published for inspection and future mapping.
"""
import copy
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

KEY = 'mls-next-cup-qualifier-roseville-regional'
ROOT = 'https://mls-assist.theintelligenceplatform.com/data/'
SCHEDULE_URL = ROOT + 'schedule/' + KEY + '.json'
STANDINGS_URL = ROOT + 'standings/' + KEY + '.json'
PREVIOUS_SITE = 'https://secerbeg.github.io/R2026ElkGrove/data/'
DATA_DIR = Path(__file__).resolve().parent.parent / 'data'
SCHEDULE = DATA_DIR / 'published-schedule.json'
STANDINGS = DATA_DIR / 'published-standings.json'
STATUS = DATA_DIR / 'feed-status.json'
DATA_DIR.mkdir(parents=True, exist_ok=True)


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def fetch_json(url):
    # Force a fresh response, mirroring the request made by the MLS NEXT site.
    separator = '&' if '?' in url else '?'
    url += separator + '_t=' + str(int(time.time() * 1000))
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; RosevilleScheduleSync/2.0)',
        'Accept': 'application/json, text/plain, */*',
        'Cache-Control': 'no-cache',
    })
    with urllib.request.urlopen(req, timeout=25) as response:
        content = response.read(10_000_001)
        if len(content) > 10_000_000:
            raise ValueError('Response exceeds 10 MB')
    return json.loads(content.decode('utf-8'))


def write_json(path, obj):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def validate_schedule(obj):
    if not isinstance(obj, dict) or not isinstance(obj.get('events'), list):
        raise ValueError('Schedule JSON lacks events array')
    linked = obj.get('linked_competition_seasons')
    if not isinstance(linked, list) or KEY not in [x.get('key') for x in linked if isinstance(x, dict)]:
        raise ValueError('Schedule competition key does not match Roseville')
    return obj


def validate_standings(obj):
    if not isinstance(obj, (dict, list)):
        raise ValueError('Standings JSON must be an object or array')
    if isinstance(obj, dict):
        linked = obj.get('linked_competition_seasons')
        if isinstance(linked, list) and linked and KEY not in [x.get('key') for x in linked if isinstance(x, dict)]:
            raise ValueError('Standings linked competition is not Roseville')
        candidate = obj.get('competition_key') or obj.get('competition_season_key')
        if isinstance(candidate, str) and candidate and candidate != KEY:
            raise ValueError('Standings competition key is not Roseville')
    return obj


def local_snapshot(path, validator):
    if not path.exists():
        return None
    try:
        return validator(json.loads(path.read_text(encoding='utf-8')))
    except (OSError, ValueError, TypeError) as exc:
        print('Ignoring invalid saved snapshot:', path.name, str(exc))
        return None


def restore_site_copy(filename, validator):
    try:
        obj = validator(fetch_json(PREVIOUS_SITE + filename))
        if filename == 'published-schedule.json' and not obj.get('_site_fetched_at'):
            raise ValueError('Previous schedule is not a confirmed sync snapshot')
        print('Recovered previously published', filename)
        return obj
    except Exception as exc:
        print('No previously deployed', filename, ':', exc)
        return None


def attempt(url, validator, label):
    error = None
    for i in range(1, 4):
        try:
            data = validator(fetch_json(url))
            return data, None
        except Exception as exc:
            error = str(exc)
            print(f'{label} fetch {i}/3 failed: {error}', file=sys.stderr)
            if i != 3:
                time.sleep(2)
    return None, error


def as_score(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, int) and 0 <= v <= 99:
        return v
    if isinstance(v, str) and re.fullmatch(r'\s*\d{1,2}\s*', v):
        return int(v.strip())
    return None


def field(d, names):
    if not isinstance(d, dict):
        return None
    for name in names:
        if name in d and d[name] is not None:
            return d[name]
    return None


HOME_KEYS = ('home_score', 'homeScore', 'score_home', 'home_goals', 'homeGoals', 'home_team_score', 'home_final_score')
AWAY_KEYS = ('away_score', 'awayScore', 'score_away', 'away_goals', 'awayGoals', 'away_team_score', 'away_final_score')
HOME_PK_KEYS = ('home_penalty_shootout_score', 'homePenaltyShootoutScore', 'home_pk', 'homePk', 'home_penalties', 'home_penalty_score')
AWAY_PK_KEYS = ('away_penalty_shootout_score', 'awayPenaltyShootoutScore', 'away_pk', 'awayPk', 'away_penalties', 'away_penalty_score')
ID_KEYS = ('id', 'game_key', 'gameKey', 'match_id', 'matchId', 'event_id', 'eventId', 'fixture_id', 'fixtureId')
FINISHED = {'final', 'full time', 'full-time', 'ft', 'complete', 'completed', 'finished', 'ended', 'played'}
NOT_FINISHED = {'scheduled', 'upcoming', 'pending', 'not started', 'not_started', 'postponed', 'cancelled', 'canceled', 'tbd'}


def identifiers(obj):
    result = set()
    for k in ID_KEYS:
        v = obj.get(k)
        if isinstance(v, (str, int)) and not isinstance(v, bool) and str(v).strip():
            result.add(str(v).strip())
    return result


def parse_match(obj):
    """Identify a result-bearing match without confusing aggregate standings with scores."""
    if not isinstance(obj, dict) or not identifiers(obj):
        return None
    home = as_score(field(obj, HOME_KEYS))
    away = as_score(field(obj, AWAY_KEYS))
    score_block = obj.get('score') or obj.get('result')
    if (home is None or away is None) and isinstance(score_block, dict):
        home = as_score(field(score_block, ('home', 'home_score', 'homeScore', 'home_goals')))
        away = as_score(field(score_block, ('away', 'away_score', 'awayScore', 'away_goals')))
    if home is None or away is None:
        # Some providers store score on nested team records.
        h = obj.get('home_team') or obj.get('home')
        a = obj.get('away_team') or obj.get('away')
        if isinstance(h, dict) and isinstance(a, dict):
            home = as_score(field(h, ('score', 'goals', 'final_score')))
            away = as_score(field(a, ('score', 'goals', 'final_score')))
    if home is None or away is None:
        return None
    hp = as_score(field(obj, HOME_PK_KEYS))
    ap = as_score(field(obj, AWAY_PK_KEYS))
    if isinstance(score_block, dict):
        if hp is None:
            hp = as_score(field(score_block, HOME_PK_KEYS))
        if ap is None:
            ap = as_score(field(score_block, AWAY_PK_KEYS))
    completed = obj.get('completed')
    status = str(field(obj, ('status', 'match_status', 'game_status', 'state', 'match_state')) or '').lower().strip()
    if completed is False or completed == 0 or (isinstance(completed, str) and completed.strip().lower() in ('false', '0', 'no')) or status in NOT_FINISHED:
        return None
    # An unmarked 0-0 may be a pre-match placeholder; never publish it as final.
    if completed is not True and not status and home == 0 and away == 0 and hp is None and ap is None:
        return None
    # No status field: scores from official standings data are usable only when
    # both sides are known and the match is not explicitly marked unplayed.
    if completed is not True and status and status not in FINISHED:
        return None
    return {'ids': identifiers(obj), 'home': home, 'away': away,
            'home_pk': hp, 'away_pk': ap,
            'explicit_final': completed is True or status in FINISHED}


def match_records(document):
    """Walk nesting without assuming whether the provider uses events, games, groups or matches."""
    results = []
    nodes = [(document, 0)]
    count = 0
    while nodes:
        obj, depth = nodes.pop()
        count += 1
        if count > 200_000:
            raise ValueError('Standings tree unexpectedly large')
        if isinstance(obj, dict):
            item = parse_match(obj)
            if item:
                results.append(item)
            if depth < 18:
                nodes.extend((v, depth + 1) for v in obj.values() if isinstance(v, (dict, list)))
        elif isinstance(obj, list) and depth < 18:
            nodes.extend((v, depth + 1) for v in obj)
    # Prefer explicit final records when multiple objects describe the same game.
    results.sort(key=lambda x: (x['explicit_final'], x['home_pk'] is not None and x['away_pk'] is not None), reverse=True)
    return results


def merge_results(schedule, source):
    records = match_records(source)
    index = {}
    ambiguous = set()
    for rec in records:
        for key in rec['ids']:
            prev = index.get(key)
            # When the same provider ID points at conflicting scores, refuse it.
            if prev is not None and (prev['home'], prev['away']) != (rec['home'], rec['away']):
                if prev['explicit_final'] == rec['explicit_final']:
                    ambiguous.add(key)
                elif rec['explicit_final']:
                    index[key] = rec
            elif prev is None:
                index[key] = rec
    applied = 0
    penalties = 0
    ids_matched = 0
    for game in schedule['events']:
        if not isinstance(game, dict):
            continue
        fixture = game.get('event') or game.get('fixture') or game
        if not isinstance(fixture, dict):
            continue
        ids = identifiers(fixture)
        selected = [index[k] for k in ids if k in index and k not in ambiguous]
        if not selected:
            continue
        if len({(r['home'], r['away']) for r in selected}) > 1:
            continue
        ids_matched += 1
        selected.sort(key=lambda x: (x['explicit_final'], x['home_pk'] is not None and x['away_pk'] is not None), reverse=True)
        rec = selected[0]
        fixture['home_score'] = rec['home']
        fixture['away_score'] = rec['away']
        fixture['completed'] = True
        fixture['status'] = 'completed'
        if rec['home_pk'] is not None and rec['away_pk'] is not None:
            fixture['home_penalty_shootout_score'] = rec['home_pk']
            fixture['away_penalty_shootout_score'] = rec['away_pk']
            penalties += 1
        applied += 1
    return {'records_found': len(records), 'matches_by_id': ids_matched,
            'results_applied': applied, 'shootouts_applied': penalties,
            'ambiguous_ids': len(ambiguous)}


def main():
    checked = utc_now()
    prior_schedule = local_snapshot(SCHEDULE, validate_schedule)
    prior_standings = local_snapshot(STANDINGS, validate_standings)
    fresh_schedule, schedule_error = attempt(SCHEDULE_URL, validate_schedule, 'Schedule')
    fresh_standings, standings_error = attempt(STANDINGS_URL, validate_standings, 'Standings')
    schedule = fresh_schedule or prior_schedule or restore_site_copy('published-schedule.json', validate_schedule)
    standings = fresh_standings or prior_standings or restore_site_copy('published-standings.json', validate_standings)

    if standings is not None and fresh_standings is not None:
        # Keep the last valid results snapshot if the API subsequently fails.
        write_json(STANDINGS, standings)
    elif standings is not None and not STANDINGS.exists():
        write_json(STANDINGS, standings)

    status = {
        'state': 'ok' if fresh_schedule is not None else 'error',
        'checked_at': checked,
        'last_success_at': checked if fresh_schedule is not None else (schedule or {}).get('_site_fetched_at'),
        'source_synced_at': (schedule or {}).get('synced_at'),
        'event_count': len(schedule['events']) if schedule is not None else None,
        'standings_state': 'ok' if fresh_standings is not None else ('cached' if standings is not None else 'unavailable'),
        'standings_checked_at': checked,
        'standings_source_synced_at': standings.get('synced_at') if isinstance(standings, dict) else None,
    }
    if schedule_error:
        status['error'] = schedule_error
    if standings_error:
        status['standings_error'] = standings_error

    if schedule is not None:
        schedule = copy.deepcopy(schedule)
        if standings is not None:
            stats = merge_results(schedule, standings)
            status.update(stats)
            if stats['results_applied'] == 0:
                print('Warning: standings loaded, but no results could be mapped; inspect saved standings JSON.', file=sys.stderr)
        else:
            status.update({'records_found': 0, 'matches_by_id': 0, 'results_applied': 0, 'shootouts_applied': 0})
        schedule['_site_fetched_at'] = checked if fresh_schedule is not None else schedule.get('_site_fetched_at')
        schedule['_results_source'] = 'MLS Assist standings' if standings is not None and status.get('results_applied') else 'MLS Assist schedule'
        write_json(SCHEDULE, schedule)
    write_json(STATUS, status)
    print('Roseville sync:', 'fixtures', status['event_count'], 'results matched', status.get('results_applied', 0),
          'shootouts', status.get('shootouts_applied', 0), 'standings feed', status['standings_state'])
    return 0  # Always deploy preserved data and a truthful status page.


if __name__ == '__main__':
    sys.exit(main())
