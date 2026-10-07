"""Build CBB Simulator imports. No football enum values are permitted.

The existing wider college dataset is retained; D1 is replaced by the ESPN
2026 standings roster. See BASKETBALL_SETUP.md for sources and limits.
"""
import copy
import json
import re
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent
OFFENSES = {'motion', 'uptempo', 'pickAndRoll', 'dribbleDrive', 'princeton', 'postUp'}
DEFENSES = {'Man-to-Man', 'Full Court Press', '2-3 Zone', 'Matchup'}
REGIONS = {'East', 'Midwest', 'South', 'West'}
REGION_MAP = {'Northeast': 'East', 'Southeast': 'South', 'Southwest': 'South', 'Plains': 'Midwest'}
TOP_KEYS = {'conferences', 'independents', 'rivalries', 'protectedPairs',
            'nationalChampionshipLogoURL', 'subdivisionTeams', 'awardCustomizations'}

def read(name):
    return json.loads((ROOT / name).read_text(encoding='utf-8'))

def validate(league):
    assert set(league) == TOP_KEYS, 'Unexpected import envelope'
    names = []
    for conf in league['conferences']:
        assert conf['tier'] in {'Power', 'Non-Power', 'Independent'}
        assert type(conf['requiredConferenceGames']) is int
        assert 0 <= conf['requiredConferenceGames'] <= 2 * (len(conf['teams']) - 1)
        assert type(conf['conferencePrestige']) is int and 25 <= conf['conferencePrestige'] <= 100
        for team in conf['teams']:
            names.append(team['name'])
            assert team['offenseScheme'] in OFFENSES, team['name']
            assert team['defenseScheme'] in DEFENSES, team['name']
            assert team['region'] in REGIONS, team['name']
            assert type(team['prestige']) is int and 25 <= team['prestige'] <= 100
            for key in ['primary', 'secondary', 'tertiary']:
                assert re.fullmatch(r'#[0-9A-Fa-f]{6}', team[key]), (team['name'], key)
            for key in ['name', 'mascot', 'abbreviation', 'logoURL']:
                assert isinstance(team[key], str) and team[key], (team['name'], key)
            assert team['logoURL'].startswith('https://')
    assert len(names) == len(set(names)), 'Ambiguous team names'
    for rivalry in league['rivalries']:
        assert rivalry['teamA'] in names and rivalry['teamB'] in names
        assert rivalry['teamA'] != rivalry['teamB']
        assert type(rivalry['mutual']) is bool
    assert len(league['subdivisionTeams']) <= 32
    return len(names)

def write(name, league):
    count = validate(league)
    text = json.dumps(league, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    (ROOT / name).write_text(text, encoding='utf-8')
    assert json.loads((ROOT / name).read_text(encoding='utf-8')) == league
    print(f'{name}: {count} teams, {len(league["conferences"])} conferences, {len(league["rivalries"])} rivalries')

def main():
    d1 = read('basketball_D1_source.json')
    assert validate(d1) == 365
    full = copy.deepcopy(d1)
    old = read('college_basketball_all_1306_teams_REAL_LOGOS.json')
    for conf in old['conferences']:
        if '(NCAA DI)' in conf['name']:
            continue
        conf = copy.deepcopy(conf)
        conf['tier'] = 'Non-Power'
        conf['conferencePrestige'] = 40
        conf['requiredConferenceGames'] = min(20, 2 * (len(conf['teams']) - 1))
        conf['conferenceLogoURL'] = ''
        for team in conf['teams']:
            team['offenseScheme'] = 'motion'
            team['defenseScheme'] = 'Man-to-Man'
            team['region'] = REGION_MAP.get(team['region'], team['region'])
            team['prestige'] = int(round(team['prestige']))
        full['conferences'].append(conf)
    counts = Counter(t['name'] for c in full['conferences'] for t in c['teams'])
    # Keep distinct schools; qualify duplicate lower-division labels by conference.
    d1_names = {t['name'] for c in d1['conferences'] for t in c['teams']}
    for conf in full['conferences'][len(d1['conferences']):]:
        for team in conf['teams']:
            if counts[team['name']] > 1 or team['name'] in d1_names:
                team['name'] += ' [' + conf['name'] + ']'
    write('basketball_2026.json', full)
    write('basketball_2026_D1.json', d1)
    # Repair the previously shared URL as well, avoiding stale football values.
    write('basketball_D1_football_format.json', d1)

if __name__ == '__main__':
    main()
