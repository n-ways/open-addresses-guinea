#!/usr/bin/env python3
"""Guinea's national name registry from the real compound counts (engine/SPEC.md 4).

  python3 tools/build-register.py <work folder> [--freeze]

Reads <work>/area-points.csv (every area: the official quartiers and the
localities, from tools/extract-buildings.py) and <work>/area-counts.json (the
compounds of each area, from `tools/issue_registry.py group`), and:

  1. gives every area its plate name (tools/plates_gn.py, the rule of
     engine/reference/plate_names.py with Guinea's settings), its official name
     kept beside it;
  2. groups the areas whose plate names normalise alike (gn_codes.normalise_name)
     into ONE national range per name, split into blocks, one per area in use:
       block size  = 2 x the area's compounds, rounded up to 50 (minimum 50)
       range       = 1000-9999 when the blocks fit in 9,000 numbers, else 10000-99999
       block order = frame digit, then the Hilbert position of the area's point
                     over Guinea, then the area id
       qualifier   = only for a name needing more than 90,000 numbers
  3. numbers the names (ids 1... in alphabetical order of the key) and the areas
     (frame, then Hilbert position, then id: the area's zone "F-NNNNN").

Before first issue it writes an unfrozen registry; with --freeze it marks the
registry frozen (the issue run). Once frozen, nothing that exists is changed: an area
that gets its first compound later takes the next free block of its name, a
new name takes the next id, a new area the next index.

Writes model/names.json (the registry, decoded by gn_codes.decode_home),
engine/data/register.json (what an engine ships: frames, every area with its
blocks, aliases, name ids) and model/stats/national-names.json (the summary).
"""
import collections, csv, json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
sys.path.insert(0, os.path.join(REPO, 'tools'))
import gn_codes as g  # noqa: E402
import plates_gn  # noqa: E402

work = os.path.abspath(sys.argv[1])
FREEZE = '--freeze' in sys.argv
NAMES = os.path.join(REPO, 'model', 'names.json')
# Areas the map gives no name: named from the OSM place node inside their polygon.
UNNAMED = {'osm:way/670104008': ('Fensorikolen', 'OSM quartier way 670104008 has no name; the OSM place node "Fensorikolen" lies inside it')}
CONAKRY = {'Kaloum', 'Dixinn', 'Matam', 'Conakry'}
FRAME_KEY = {0: 'CKY', 1: 'BAS', 2: 'MOY', 3: 'HAU', 4: 'FOR'}

frames = g.load_frames()
counts = json.load(open(os.path.join(work, 'area-counts.json')))
areas = []
for r in csv.DictReader(open(os.path.join(work, 'area-points.csv'), encoding='utf-8')):
    lat, lon = float(r['lat']), float(r['lon'])
    name = (r['name'] or '').strip()
    note = None
    if not name and r['aid'] in UNNAMED:
        name, note = UNNAMED[r['aid']]
    if not name:
        if counts.get(r['aid']):
            sys.exit(f"area {r['aid']} has no name and has compounds: add it to UNNAMED")
        continue
    frame = int(r['frame']) if r['frame'] else g.frame_of(lat, lon, frames)['digit']
    label = r['label'] or ''
    pref = 'Conakry' if label in CONAKRY or frame == 0 else label
    areas.append({'aid': r['aid'], 'how': r['how'], 'name': name, 'official': name, 'nameNote': note, 'lat': lat, 'lon': lon,
                  'digit': frame, 'label': label or ('Conakry' if frame == 0 else ''), 'pref': pref, 'compounds': counts.get(r['aid'], 0)})
in_use = [a for a in areas if a['compounds']]

# ------------------------------------------------------------------ plate names
D = plates_gn.Deriver(in_use)
for a in areas:
    r = D.derive(a)
    a.update(plate=r['plate'], rule=r['rule'], flag=r['needsCouncilChoice'], cands=r['candidates'][:3], reason=r.get('reason'),
             source=r.get('source'), overLimit=r['overLimit'])
    a['name'] = r['plate']

old = json.load(open(NAMES)) if os.path.exists(NAMES) else {}
frozen = bool(old.get('frozen'))


def order_key(a):
    return (a['digit'], g.national_order(a['lat'], a['lon']), a['aid'])


# ------------------------------------------------------------------ names and ranges
groups = collections.defaultdict(list)
for a in areas:
    groups[g.normalise_name(a['plate'])].append(a)

if not frozen:
    qualified, final = [], {}
    for key, lst in groups.items():
        use = sorted((a for a in lst if a['compounds']), key=order_key)
        if g.allocate(use) is None:            # a qualifier people already use: the préfecture or town
            qualified.append(key)
            for a in lst:
                a['name'] = f"{a['name']} ({a['pref']})"
                final.setdefault(g.normalise_name(a['name']), []).append(a)
        else:
            final[key] = lst
    ids = {k: i for i, k in enumerate(sorted(final), 1)}
    blocks = {}
    for key, lst in final.items():
        use = sorted((a for a in lst if a['compounds']), key=order_key)
        al = g.allocate(use)
        for a, start, size in al['blocks']:
            blocks[a['aid']] = [[start, start + size - 1]]
        final[key] = lst
    nxt = {key: g.allocate(sorted((a for a in lst if a['compounds']), key=order_key)) for key, lst in final.items()}
    ranges = {k: {'digits': v['digits'], 'range': [v['first'], v['end'] - 1], 'nextFree': v['nextFree']} for k, v in nxt.items()}
    idx = {a['aid']: i for i, a in enumerate(sorted(areas, key=order_key), 1)}
else:
    # frozen: keep every id, block and index; only add
    ids = {n['key']: n['id'] for n in old['names']}
    blocks = {b['aid']: b['blocks'] for n in old['names'] for b in n['blocks'] if b.get('blocks')}
    ranges = {n['key']: {'digits': n['digits'], 'range': n['range'], 'nextFree': n['nextFree']} for n in old['names']}
    idx = {b['aid']: b['index'] for n in old['names'] for b in n['blocks']}
    plate_of = {b['aid']: (b['name'], b['officialName']) for n in old['names'] for b in n['blocks']}
    qualified = old.get('qualified', [])
    final = collections.defaultdict(list)
    for a in areas:
        if a['aid'] in plate_of:                # an area keeps its frozen plate name
            a['name'], a['plate'] = plate_of[a['aid']][0], plate_of[a['aid']][0]
        final[g.normalise_name(a['name'])].append(a)
    for key in sorted(final):
        if key not in ids:
            ids[key] = max(ids.values()) + 1
            ranges[key] = {'digits': 4, 'range': [1000, 9999], 'nextFree': 1000}
    top = max(idx.values())
    for a in sorted(areas, key=order_key):
        if a['aid'] not in idx:
            top += 1
            idx[a['aid']] = top
    for key in sorted(final):
        for a in sorted(final[key], key=order_key):
            if a['compounds'] and a['aid'] not in blocks:
                size = g.block_size(a['compounds'])
                start = ranges[key]['nextFree']
                if start + size - 1 > g.MAX_NUMBER:
                    sys.exit(f"name {key} has no room left for area {a['aid']}: it needs a qualifier")
                blocks[a['aid']] = [[start, start + size - 1]]
                ranges[key]['nextFree'] = start + size

# ------------------------------------------------------------------ aliases (official name -> plate name), when unambiguous
claims = collections.defaultdict(set)
for key, lst in final.items():
    for a in lst:
        ok = g.normalise_name(plates_gn.prepare(a['official']))
        if ok != key:
            claims[ok].add(key)
aliases, dropped = {}, {}
for ok, keys in sorted(claims.items()):
    if len(keys) > 1:
        dropped[ok] = {'reason': 'claimed by two or more plate names', 'plateNames': sorted(keys)}
    elif ok in final:
        dropped[ok] = {'reason': 'is itself a plate name', 'plateNames': sorted(keys)}
    else:
        aliases[ok] = next(iter(keys))


def block(a):
    b = {'aid': a['aid'], 'index': idx[a['aid']], 'zone': f"{a['digit']}-{idx[a['aid']]:05d}", 'name': a['name'], 'officialName': a['official'],
         'plateRule': a['rule'], 'pref': a['pref'], 'label': a['label'], 'frame': a['digit'], 'kind': a['how'], 'lat': a['lat'], 'lon': a['lon'],
         'compounds': a['compounds'], 'blocks': blocks.get(a['aid'], [])}
    if b['blocks']:                             # the decoder's view: the first block
        b['start'], b['size'] = b['blocks'][0][0], b['blocks'][0][1] - b['blocks'][0][0] + 1
    if a['source']:
        b['plateSource'] = a['source']
    if a.get('nameNote'):
        b['nameNote'] = a['nameNote']
    if a['flag']:
        b.update(needsCouncilChoice=True, plateCandidates=a['cands'], plateReason=a['reason'])
    if a['overLimit']:
        b['overLimit'] = True
    return b


names = []
for key in sorted(final, key=lambda k: ids[k]):
    lst = sorted(final[key], key=order_key)
    rg = ranges[key]
    names.append({'id': ids[key], 'key': key, 'spellings': sorted({a['name'] for a in lst}), 'digits': rg['digits'], 'range': rg['range'],
                  'nextFree': rg['nextFree'], 'blocks': [block(a) for a in lst]})
reg = {'country': 'GN', 'version': '2026-10-20', 'frozen': frozen or FREEZE, 'frozenOn': old.get('frozenOn') or ('2026-10-20' if FREEZE else None),
       'note': ('National name registry. "name" in a block is the plate name (the remembered name, at most 12 characters and 2 words); '
                '"officialName" is the full name, printed small for context and never required. An area flagged needsCouncilChoice carries '
                'a provisional plate name (the first candidate) until its commune chooses; its numbers never change. Name ids, ranges, '
                'blocks and area indexes are frozen at the first issued code; then a new area with an existing name takes the next free '
                'block of that name, and a full block an extra block further along.'),
       'rule': {'blockStep': g.BLOCK_STEP, 'headroom': g.HEADROOM, 'ranges': {'4': [1000, 9999], '5': [10000, 99999]}, 'maxNumber': g.MAX_NUMBER,
                'plateName': {'maxChars': plates_gn.P.MAX_CHARS, 'maxWords': plates_gn.P.MAX_WORDS, 'lang': plates_gn.LANG,
                              'quartierNumber': 'kept; counts as characters, not as a word'}},
       'qualified': qualified, 'aliases': aliases, 'droppedAliases': dropped, 'names': names}
json.dump(reg, open(NAMES, 'w'), ensure_ascii=False, separators=(',', ':'))

# ------------------------------------------------------------------ what an engine ships
rows = []
for n in names:
    for b in n['blocks']:
        rows.append({'index': b['index'], 'aid': b['aid'], 'frame': b['frame'], 'name': b['name'], 'officialName': b['officialName'], 'kind': b['kind'],
                     'label': b['label'], 'nameKey': n['key'], 'family': n['id'], 'blocks': b['blocks'], 'needsCouncilChoice': bool(b.get('needsCouncilChoice')),
                     'lat': b['lat'], 'lon': b['lon'], 'compounds': b['compounds']})
rows.sort(key=lambda r: r['index'])
fr = json.load(open(os.path.join(REPO, 'model', 'frames.json')))['frames']
out = {'version': 1, 'country': 'GN',
       'note': 'N-Ways Addressing for Guinea: the register a decoder needs (no data about any home). Blocks are frozen at first issue; later ones are only added.',
       'frames': [{'digit': f['digit'], 'key': FRAME_KEY[f['digit']], 'name': f['name'], 'west': f['west'], 'south': f['south'], 'refLat': f['refLat'],
                   'box': f['box']} for f in fr],
       'areas': rows, 'aliases': aliases, 'ids': {n['key']: n['id'] for n in names},
       'nextFree': {n['key']: n['nextFree'] for n in names}, 'digits': {n['key']: n['digits'] for n in names}}
os.makedirs(os.path.join(REPO, 'engine', 'data'), exist_ok=True)
json.dump(out, open(os.path.join(REPO, 'engine', 'data', 'register.json'), 'w'), ensure_ascii=False, separators=(',', ':'))

# ------------------------------------------------------------------ summary
use = [a for a in areas if a['compounds']]
shared = [n for n in names if sum(1 for b in n['blocks'] if b['blocks']) > 1]
flag_use = [a for a in use if a['flag']]
digits_used = collections.Counter(len(str(b['blocks'][-1][1])) for n in names for b in n['blocks'] if b['blocks'])
summary = {
    'areas': len(areas), 'areasInUse': len(use), 'compounds': sum(a['compounds'] for a in use), 'names': len(names),
    'namesInUse': sum(1 for n in names if any(b['blocks'] for b in n['blocks'])),
    'repeatedNames': len(shared), 'areasSharingAName': sum(sum(1 for b in n['blocks'] if b['blocks']) for n in shared),
    'repeatedAcrossPrefectures': sum(1 for n in shared if len({b['pref'] for b in n['blocks'] if b['blocks']}) > 1),
    'fourDigitNames': sum(1 for n in names if n['digits'] == 4), 'fiveDigitNames': sum(1 for n in names if n['digits'] == 5),
    'areasByDigitsOfLastNumber': {str(k): v for k, v in sorted(digits_used.items())},
    'namesNeedingQualifier': len(qualified), 'qualified': qualified,
    'plateNames': {'byRule': dict(collections.Counter(a['rule'] for a in use)), 'needsCouncilChoice': len(flag_use),
                   'stillOverLimit': sum(1 for a in use if a['overLimit']), 'aliases': len(aliases), 'droppedAliases': len(dropped),
                   'needsCouncilChoiceByReason': dict(collections.Counter(a['reason'] for a in flag_use).most_common())},
    'largestRanges': sorted(({'name': n['spellings'][0], 'areas': sum(1 for b in n['blocks'] if b['blocks']), 'compounds': sum(b['compounds'] for b in n['blocks']),
                              'numbers': n['nextFree'] - n['range'][0], 'digits': n['digits']} for n in names), key=lambda x: (-x['numbers'], x['name']))[:12],
    'mostAreasPerName': sorted(({'name': n['spellings'][0], 'areas': sum(1 for b in n['blocks'] if b['blocks']), 'compounds': sum(b['compounds'] for b in n['blocks']),
                                 'digits': n['digits']} for n in shared), key=lambda x: (-x['areas'], x['name']))[:12],
    'biggestAreas': sorted(({'name': a['name'], 'label': a['label'], 'compounds': a['compounds']} for a in use), key=lambda x: -x['compounds'])[:12],
}
json.dump(summary, open(os.path.join(REPO, 'model', 'stats', 'national-names.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: summary[k] for k in ('areas', 'areasInUse', 'compounds', 'names', 'namesInUse', 'repeatedNames', 'fourDigitNames', 'fiveDigitNames',
                                          'namesNeedingQualifier', 'plateNames', 'largestRanges')}, ensure_ascii=False, indent=1))
