#!/usr/bin/env python3
"""The summary of the national name registry, counted on the published registry:
model/stats/national-names.json.

  python3 tools/name-stats.py [registry]

Reads the frozen name registry (model/names.json: names, places, plate names,
ranges and blocks) and counts every place's codes in registry/ (the `zone`
column), so the summary always matches the published codes: a place is in use,
and a name is shared, by the places that hold codes. The blocks are not
touched: they were sized at first issue (SPEC 4.2) and are frozen.
Standard library only; streams the registry one frame at a time.
"""
import collections, csv, gzip, json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REG = sys.argv[1] if len(sys.argv) > 1 else os.path.join(REPO, 'registry')
FRAMES = ('CKY', 'BAS', 'MOY', 'HAU', 'FOR')

codes_in = collections.Counter()
for key in FRAMES:
    with gzip.open(os.path.join(REG, key + '.csv.gz'), 'rt', encoding='utf-8', newline='') as fh:
        rows = csv.reader(fh)
        iz = next(rows).index('zone')
        for r in rows:
            codes_in[r[iz]] += 1

reg = json.load(open(os.path.join(REPO, 'model', 'names.json'), encoding='utf-8'))
names = reg['names']
areas = [dict(b, compounds=codes_in.get(b["zone"], 0)) for n in names for b in n['blocks']]
unknown = set(codes_in) - {a['zone'] for a in areas}
if unknown:
    sys.exit(f'codes in places the name registry does not hold: {sorted(unknown)[:5]}')
zones_of = {n['id']: {b['zone'] for b in n['blocks']} for n in names}
by_name = {n['id']: [a for a in areas if a['zone'] in zones_of[n['id']]] for n in names}
use = [a for a in areas if a['compounds']]
held = lambda n: [a for a in by_name[n['id']] if a['compounds']]  # noqa: E731  places of a name holding codes
shared = [n for n in names if len(held(n)) > 1]
flag_use = [a for a in use if a.get('needsCouncilChoice')]
digits_used = collections.Counter(len(str(a['blocks'][-1][1])) for a in use)
held_by = lambda n: sum(a['compounds'] for a in by_name[n['id']])  # noqa: E731
summary = {
    'areas': len(areas), 'areasInUse': len(use), 'compounds': sum(a['compounds'] for a in use), 'names': len(names),
    'namesInUse': sum(1 for n in names if held(n)),
    'repeatedNames': len(shared), 'areasSharingAName': sum(len(held(n)) for n in shared),
    'repeatedAcrossPrefectures': sum(1 for n in shared if len({a['pref'] for a in held(n)}) > 1),
    'fourDigitNames': sum(1 for n in names if n['digits'] == 4), 'fiveDigitNames': sum(1 for n in names if n['digits'] == 5),
    'areasByDigitsOfLastNumber': {str(k): v for k, v in sorted(digits_used.items())},
    'namesNeedingQualifier': len(reg.get('qualified', [])), 'qualified': reg.get('qualified', []),
    'plateNames': {'byRule': dict(collections.Counter(a['plateRule'] for a in use)), 'needsCouncilChoice': len(flag_use),
                   'stillOverLimit': sum(1 for a in use if a.get('overLimit')), 'aliases': len(reg['aliases']), 'droppedAliases': len(reg['droppedAliases']),
                   'needsCouncilChoiceByReason': dict(collections.Counter(a['plateReason'] for a in flag_use).most_common())},
    'largestRanges': sorted(({'name': n['spellings'][0], 'areas': len(held(n)), 'compounds': held_by(n),
                              'numbers': n['nextFree'] - n['range'][0], 'digits': n['digits']} for n in names), key=lambda x: (-x['numbers'], x['name']))[:12],
    'mostAreasPerName': sorted(({'name': n['spellings'][0], 'areas': len(held(n)), 'compounds': held_by(n),
                                 'digits': n['digits']} for n in shared), key=lambda x: (-x['areas'], x['name']))[:12],
    'biggestAreas': sorted(({'name': a['name'], 'label': a['label'], 'compounds': a['compounds']} for a in use), key=lambda x: -x['compounds'])[:12],
}
json.dump(summary, open(os.path.join(REPO, 'model', 'stats', 'national-names.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps({k: summary[k] for k in ('areas', 'areasInUse', 'compounds', 'repeatedNames', 'areasSharingAName')}))
