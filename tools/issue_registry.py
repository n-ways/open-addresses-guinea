#!/usr/bin/env python3
"""The compounds of Guinea for issuing their codes (engine/SPEC.md 5, 6, 8).

Reads <work>/buildings.csv (tools/extract-buildings.py, sorted by area) one area at
a time, so the 5 million footprints never sit in memory together.

  python3 tools/issue_registry.py group <work>     groups every area's structures into compounds
                                                    (SPEC 5.1), profiles them (6) and writes
                                                    <work>/compounds.jsonl.gz and <work>/area-counts.json
  python3 tools/build-register.py <work> --freeze  cuts the national ranges from those counts
  python3 tools/issue_registry.py number <work> <lotes.jsonl.gz>
                                                    numbers every area's compounds inside its block (5.2)
                                                    and writes the lotes, frame by frame, for the registry
                                                    server (the N-Ways backend, `homecodes issue -country GN`),
                                                    which numbers them again with its own port of the
                                                    engine and refuses the run if any number differs

Grouping (SPEC 5.1, the first rule that applies):
  plot       footprints inside the smallest mapped wall, fence, hedge, farmyard or small
             residential plot are one compound (a plot holding more than 25 is grouped
             by the rules below, inside it)
  site       footprints inside an institutional site (school, hospital, mosque, market,
             military, police, government, industry) are one compound when the site holds
             at most 30 and is at most 6 ha; a bigger site is only an outer enclosure
  concession where fewer than 4 buildings stand per hectare (villages, hamlets): round
             (4 pi A / P^2 > 0.88, under 60 m2) and small (under 40 m2) structures within
             10 m of one another are one concession, at most 60 m across; the concession
             joins a larger house within 10 m when the whole stays within 60 m. Three or
             more round houses make a family concession
  annex      a structure under 40 m2 joins the nearest structure at least twice its size
             within 8 m
  single     every other structure is its own compound
The border decides (SPEC 2.1): before grouping, every structure whose centre lies
more than 300 m outside the national border (engine/data/border.geojson, from
tools/border.py; gn_codes.Border) is dropped, and after it every compound whose
centre (its entrance at issue) lies beyond it, whatever the frame outlines say, so
no building in a neighbouring country is ever numbered.
A compound never holds more than 12 structures: a bigger group is split again with
half the distance. Gaps are measured between footprints, as centre distance less half
the square root of each footprint's area.

Each lote line: {"key": the main structure's stable id, "muni": frame key ("CKY"),
"zone": area zone ("0-00412"), "frame", "index", "nameId", "number", "lat", "lon",
"anchor", "anchorKind": "centre", "gate": null, "coverage": "nways" or "official-street",
"official": "<street>, Kaloum" or null, "enclosed", "rule", "settlement", "family",
"label", "structures": [...]} (largest structure first: structure 1).
Structure ids: OpenStreetMap "osm:way/<id>"; a Google/Microsoft footprint "nw:" + the first
12 hex characters of the SHA-1 of its centre to 1e-6 degrees and its area to 1 m2.
"""
import collections, csv, gzip, hashlib, json, math, os, sys

csv.field_size_limit(1 << 30)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import gn_codes as g  # noqa: E402

KY = 110574.0
CELL = 40.0
ANNEX_M2, ROUND_M2, CIRC = 40, 60, 0.88
CONCESSION_GAP, CONCESSION_SPAN, ANNEX_GAP = 10.0, 60.0, 8.0
RURAL_DENSITY = 4.0                       # buildings per hectare
CAP = 12
PLOTS = ('osm-wall', 'osm-fence', 'osm-hedge', 'osm-retaining_wall', 'osm-farmyard', 'osm-residential')
PLOT_MAX = 25
SITE_MAX, SITE_M2 = 30, 60000
TAGS = ['building', 'amenity', 'shop', 'office', 'religion', 'tourism', 'healthcare', 'man_made', 'government', 'craft',
        'building:levels', 'height', 'name', 'roof:material', 'building:material']
FRAME_KEY = {0: 'CKY', 1: 'BAS', 2: 'MOY', 3: 'HAU', 4: 'FOR'}

# --- use classes (SPEC 6, model/design.json "profile") -----------------------
OSM_BUILDING = {
    'house': 'residential.house', 'detached': 'residential.house', 'residential': 'residential.house', 'semidetached_house': 'residential.house',
    'terrace': 'residential.house', 'hut': 'residential.round-house', 'cabin': 'residential.house', 'apartments': 'residential.apartments',
    'commercial': 'commercial.shop', 'retail': 'commercial.shop', 'kiosk': 'commercial.kiosk', 'office': 'commercial.office',
    'warehouse': 'commercial.warehouse', 'industrial': 'industrial', 'shed': 'agricultural.store', 'farm': 'agricultural.store',
    'barn': 'agricultural.store', 'farm_auxiliary': 'agricultural.store', 'school': 'education', 'university': 'education',
    'kindergarten': 'education', 'college': 'education', 'hospital': 'health', 'clinic': 'health', 'church': 'religious',
    'chapel': 'religious', 'cathedral': 'religious', 'mosque': 'religious', 'public': 'government', 'civic': 'government',
    'government': 'government', 'hotel': 'hospitality', 'stadium': 'public.sport', 'construction': 'status.construction',
    'ruins': 'status.ruin', 'garage': 'transport', 'roof': 'commercial.market', 'canopy': 'commercial.market', 'tank': 'utility',
}
OSM_AMENITY = {
    'school': 'education', 'kindergarten': 'education', 'university': 'education', 'college': 'education',
    'hospital': 'health', 'clinic': 'health', 'doctors': 'health', 'pharmacy': 'health', 'place_of_worship': 'religious',
    'townhall': 'government', 'courthouse': 'government', 'police': 'government', 'post_office': 'government',
    'marketplace': 'commercial.market', 'bank': 'commercial.office', 'restaurant': 'hospitality', 'bar': 'hospitality',
    'fuel': 'transport', 'bus_station': 'transport', 'ferry_terminal': 'transport',
}
POI = {
    'office': 'commercial.office', 'school': 'education', 'hotel': 'hospitality', 'hospital': 'health', 'food': 'hospitality',
    'shop': 'commercial.shop', 'church': 'religious', 'bar': 'hospitality', 'mosque': 'religious', 'petrol': 'transport',
    'bank': 'commercial.office', 'supermarket': 'commercial.shop', 'pharmacy': 'health', 'market': 'commercial.market',
    'police': 'government', 'cafe': 'hospitality', 'motorpark': 'transport', 'salon': 'commercial.shop', 'phones': 'commercial.shop',
    'mechanic': 'commercial.workshop', 'fastfood': 'hospitality', 'vulcanizer': 'commercial.workshop', 'attraction': 'public.landmark',
}
ENCL = {'osm-amenity-school': 'education', 'osm-amenity-university': 'education', 'osm-amenity-college': 'education',
        'osm-amenity-hospital': 'health', 'osm-amenity-clinic': 'health', 'osm-amenity-place_of_worship': 'religious',
        'osm-religious': 'religious', 'osm-amenity-marketplace': 'commercial.market', 'osm-military': 'government.military',
        'nways-military': 'government.military', 'nways-government': 'government', 'nways-police': 'government',
        'osm-amenity-police': 'government', 'osm-amenity-townhall': 'government', 'osm-amenity-courthouse': 'government',
        'osm-industrial': 'industrial', 'osm-commercial': 'commercial.office', 'osm-retail': 'commercial.shop'}
SITES = tuple(ENCL) + ('nways-site', 'nways-estate')


def structure_id(r):
    if r['src'] == 'osm':
        return 'osm:' + r['oid']
    return 'nw:' + hashlib.sha1(f"{float(r['lat']):.6f},{float(r['lon']):.6f},{round(float(r['area']))}".encode()).hexdigest()[:12]


def areas_of(path):
    """(aid, rows) for each area of the sorted buildings file."""
    cur, rows = None, []
    with open(path, encoding='utf-8', newline='') as f:
        for r in csv.DictReader(f):
            if r['aid'] != cur:
                if rows:
                    yield cur, rows
                cur, rows = r['aid'], []
            rows.append(r)
    if rows:
        yield cur, rows


def prep(rows):
    kx = math.cos(math.radians(float(rows[0]['lat']))) * 111320.0
    for r in rows:
        r['x'] = float(r['lon']) * kx
        r['y'] = float(r['lat']) * KY
        r['a'] = max(float(r['area']), 1.0)
        r['p'] = max(float(r['perim']), 1.0)
        r['round'] = 4 * math.pi * r['a'] / (r['p'] ** 2) > CIRC and r['a'] < ROUND_M2
        r['small'] = r['a'] < ANNEX_M2
        r['sid'] = structure_id(r)
    rows.sort(key=lambda r: r['sid'])          # one fixed order: grouping never depends on the extract's
    cells = collections.Counter((int(r['x'] // 50), int(r['y'] // 50)) for r in rows)
    for r in rows:
        cx, cy = int(r['x'] // 50), int(r['y'] // 50)
        r['dens'] = sum(cells.get((cx + i, cy + j), 0) for i in range(-2, 3) for j in range(-2, 3)) / 6.25
        r['rural'] = r['dens'] < RURAL_DENSITY


def gap(a, b):
    return math.hypot(a['x'] - b['x'], a['y'] - b['y']) - 0.5 * math.sqrt(a['a']) - 0.5 * math.sqrt(b['a'])


def span(rows, ks):
    xs = [rows[k]['x'] for k in ks]
    ys = [rows[k]['y'] for k in ks]
    return math.hypot(max(xs) - min(xs), max(ys) - min(ys))


class UF:
    def __init__(self, ks):
        self.p = {k: k for k in ks}

    def f(self, i):
        while self.p[i] != i:
            self.p[i] = self.p[self.p[i]]
            i = self.p[i]
        return i

    def join(self, a, b):
        a, b = self.f(a), self.f(b)
        if a != b:
            self.p[max(a, b)] = min(a, b)

    def groups(self):
        out = collections.defaultdict(list)
        for k in self.p:
            out[self.f(k)].append(k)
        return [sorted(v) for v in out.values()]


def grid_of(rows, ks):
    gr = collections.defaultdict(list)
    for k in ks:
        gr[(int(rows[k]['x'] // CELL), int(rows[k]['y'] // CELL))].append(k)
    return gr


def near(rows, gr, k, R):
    r = rows[k]
    cx, cy, m = int(r['x'] // CELL), int(r['y'] // CELL), int(R // CELL) + 1
    for i in range(-m, m + 1):
        for j in range(-m, m + 1):
            for q in gr.get((cx + i, cy + j), ()):
                if q != k:
                    yield q


def proximity(rows, ks, scale=1.0):
    """Concession and annex rules over ks; returns groups."""
    S = set(ks)
    gr = grid_of(rows, ks)
    uf = UF(ks)
    # concession rule (rural): round and small structures within 10 m
    for k in ks:
        r = rows[k]
        if r['rural'] and (r['round'] or r['small']):
            for q in near(rows, gr, k, CONCESSION_GAP * scale + 30):
                rq = rows[q]
                if q > k and rq['rural'] and (rq['round'] or rq['small']) and gap(r, rq) <= CONCESSION_GAP * scale:
                    uf.join(k, q)
    groups = uf.groups()
    # a concession wider than 60 m is split again with half the distance
    out = []
    for grp in groups:
        if len(grp) > 1 and span(rows, grp) > CONCESSION_SPAN and scale > 0.1:
            out += proximity(rows, grp, scale / 2)
        else:
            out.append(grp)
    groups = out
    member = {}
    for i, grp in enumerate(groups):
        for k in grp:
            member[k] = i
    # a concession joins a larger house within 10 m; an annex joins a structure twice its size within 8 m
    for i, grp in enumerate(groups):
        if not grp:
            continue
        # Only a group of round or small structures joins something: a concession (rural) joins a
        # house, an annex (or annexes already joined) a structure twice its size. A group that holds
        # a house is a target, never a joiner, so houses are never chained together.
        if not all(rows[k]['round'] or rows[k]['small'] for k in grp):
            continue
        if all(rows[k]['rural'] for k in grp) and (len(grp) > 1 or not rows[grp[0]]['small']):
            kind, reach = 'concession', CONCESSION_GAP * scale
        elif all(rows[k]['small'] for k in grp):
            kind, reach = 'annex', ANNEX_GAP * scale
        else:
            continue
        best, bd = None, None
        for k in grp:
            for q in near(rows, gr, k, reach + 30):
                if q not in S or member[q] == i:
                    continue
                big = rows[q]
                if kind == 'concession' and (big['small'] or big['round']):
                    continue
                if kind == 'annex' and big['a'] < 2 * max(rows[x]['a'] for x in grp):
                    continue
                d = gap(rows[k], big)
                if bd is None or (d, big['sid']) < (bd, rows[best]['sid']):
                    best, bd = q, d
        if best is None or bd > reach:
            continue
        j = member[best]
        merged = groups[j] + grp
        if kind == 'concession' and span(rows, merged) > CONCESSION_SPAN:
            continue
        groups[j] = merged
        for k in grp:
            member[k] = j
        groups[i] = []
    return [grp for grp in groups if grp]


def cap(rows, grp, scale=1.0):
    if len(grp) <= CAP or scale < 0.05:
        return [grp] if len(grp) <= CAP else [[k] for k in grp]
    out = []
    for sub in proximity(rows, grp, scale / 2):
        out += cap(rows, sub, scale / 2)
    return out


def group(rows, enc):
    """[(structure indexes, rule)] for one area."""
    by_e = collections.defaultdict(list)
    free = []
    for k, r in enumerate(rows):
        e = enc.get(r['eid']) if r['eid'] else None
        if e and (e['kind'] in PLOTS or e['kind'].startswith(SITES)):
            by_e[r['eid']].append(k)
        else:
            free.append(k)
    out = []
    for eid in sorted(by_e):
        ks = by_e[eid]
        e = enc[eid]
        if e['kind'] in PLOTS and len(ks) <= PLOT_MAX:
            out.append((ks, 'enclosure'))
        elif e['kind'] not in PLOTS and len(ks) <= SITE_MAX and float(e['areaM2']) <= SITE_M2:
            out.append((ks, 'site'))
        else:
            for grp in proximity(rows, ks):
                for sub in cap(rows, grp):
                    out.append((sub, 'proximity'))
    for grp in proximity(rows, free):
        for sub in cap(rows, grp):
            rural = rows[sub[0]]['rural'] and any(rows[k]['round'] or rows[k]['small'] for k in sub)
            out.append((sub, 'single' if len(sub) == 1 else ('concession' if rural else 'annex')))
    return out


def profile(r, enc, members):
    """Use class, confidence and source of one structure (SPEC 6)."""
    b = (r['building'] or '').lower()
    if r['amenity'] in OSM_AMENITY:
        return OSM_AMENITY[r['amenity']], 0.85, 'osm:amenity'
    if r['shop']:
        return 'commercial.shop', 0.85, 'osm:shop'
    if r['office'] or r['government']:
        return ('government' if r['government'] else 'commercial.office'), 0.85, 'osm:office'
    if r['tourism'] in ('hotel', 'guest_house', 'hostel', 'motel'):
        return 'hospitality', 0.85, 'osm:tourism'
    if b in OSM_BUILDING:
        return OSM_BUILDING[b], 0.9, 'osm:building'
    e = enc.get(r['eid']) if r['eid'] else None
    if e and e['kind'] in ENCL:
        return ENCL[e['kind']], 0.7, 'nways:compound' if e['kind'].startswith('nways') else 'enclosure:' + e['kind']
    if r['poi']:
        cats = sorted(POI[c] for c in r['poi'].split('|') if c in POI)
        if cats:
            return collections.Counter(cats).most_common(1)[0][0], 0.7, 'nways:places'
    if r['a'] < 12 and len(members) > 1:
        return 'residential.annex', 0.5, 'shape:size'
    if r['round']:
        return 'residential.round-house', 0.5, 'shape:round'
    fl, _ = floors(r)
    if r['a'] >= 1500 and (fl or 1) <= 2:
        return 'commercial.warehouse', 0.5, 'shape:size'
    return 'residential.house', 0.3, 'default'


def floors(r):
    lv = r['building:levels']  # OpenStreetMap's levels, then its height
    try:
        if lv:
            return max(1, round(float(lv))), 'osm:building:levels'
    except ValueError:
        pass
    h = r['height']
    try:
        if h:
            return max(1, math.floor((float(h.replace('m', '').strip()) + 0.5) / 3)), 'osm:height'
    except ValueError:
        pass
    # The Google/Microsoft footprints' height h is a rendering filler (36 values spread evenly
    # from 3.5 to 7.0 m, about 98,000 footprints each), so it never gives floors.
    return None, None


def load_enc(work):
    return {r['eid']: r for r in csv.DictReader(open(os.path.join(work, 'enclosure-gates.csv'), encoding='utf-8'))}


def cmd_group(work):
    enc = load_enc(work)
    border = g.Border()
    counts, stats = {}, collections.Counter()
    sizes = collections.Counter()
    seen = set()
    with gzip.open(os.path.join(work, 'compounds.jsonl.gz'), 'wt', encoding='utf-8') as out:
        for aid, rows in areas_of(os.path.join(work, 'buildings.csv')):
            kept = [r for r in rows if border.holds(float(r['lat']), float(r['lon']))]
            stats['abroadStructure'] += len(rows) - len(kept)
            rows = kept
            if not rows:
                counts[aid] = 0
                continue
            prep(rows)
            n = 0
            for ks, rule in group(rows, enc):
                ks = sorted(ks, key=lambda k: (-rows[k]['a'], rows[k]['sid']))
                areas = [rows[k]['a'] for k in ks]
                sts = []
                for k in ks:
                    r = rows[k]
                    cls, conf, src = profile(r, enc, areas)
                    fl, fls = floors(r)
                    sts.append({'id': r['sid'], 'src': r['src'], 'lat': round(float(r['lat']), 7), 'lon': round(float(r['lon']), 7),
                                'areaM2': round(float(r['area']), 1), 'perimeterM': round(float(r['perim']), 1),
                                'tags': {t: r[t] for t in TAGS if r.get(t)}, 'places': [p for p in (r['poi'] or '').split('|') if p],
                                'class': cls, 'confidence': conf, 'classSource': src, 'floors': fl, 'floorsSource': fls, 'wkt': r['wkt']})
                key = sts[0]['id']
                if key in seen:
                    stats['duplicateKey'] += 1
                    continue
                seen.add(key)
                w = sum(areas)
                lat = sum(rows[k]['y'] * rows[k]['a'] for k in ks) / w / KY
                lon = sum(float(rows[k]['lon']) * rows[k]['a'] for k in ks) / w
                if not border.holds(lat, lon):
                    stats['abroadCompound'] += 1
                    continue
                streets = collections.Counter(rows[k]['street'] for k in ks if rows[k]['street'])
                street = min(streets, key=lambda s: (-streets[s], s)) if streets else None
                rounds = sum(1 for k in ks if rows[k]['round'])
                rec = {'key': key, 'aid': aid, 'lat': round(lat, 7), 'lon': round(lon, 7), 'rule': rule,
                       'enclosed': rule in ('enclosure', 'site'), 'settlement': 'rural' if rows[ks[0]]['rural'] else 'town',
                       'family': rounds >= 3, 'label': rows[ks[0]]['label'] or '',
                       'official': f'{street}, Kaloum' if street else None, 'structures': sts}
                out.write(json.dumps(rec, ensure_ascii=False, separators=(',', ':')) + '\n')
                n += 1
                stats['rule:' + rule] += 1
                stats['structures'] += len(sts)
                sizes[min(len(sts), 13)] += 1
                if street:
                    stats['kaloumStreet'] += 1
            counts[aid] = n
            stats['compounds'] += n
    json.dump(counts, open(os.path.join(work, 'area-counts.json'), 'w'))
    stats.update({f'size:{k}': v for k, v in sizes.items()})
    json.dump(dict(stats), open(os.path.join(work, 'group-stats.json'), 'w'), indent=1)
    print(json.dumps(dict(stats)))


def cmd_number(work, out_path):
    reg = json.load(open(os.path.join(REPO, 'model', 'names.json')))
    frames = g.load_frames()
    area = {b['aid']: (n['id'], b) for n in reg['names'] for b in n['blocks']}
    counts = collections.Counter()
    with gzip.open(out_path, 'wt', encoding='utf-8') as out:
        for digit in sorted(frames):
            by_area = collections.defaultdict(list)
            with gzip.open(os.path.join(work, 'compounds.jsonl.gz'), 'rt', encoding='utf-8') as f:
                for line in f:
                    c = json.loads(line)
                    nid, b = area[c['aid']]
                    if b['frame'] == digit:
                        by_area[c['aid']].append(c)
            for aid in sorted(by_area, key=lambda a: area[a][1]['index']):
                nid, b = area[aid]
                lo, hi = b['blocks'][0]
                cs = by_area[aid]
                nums = g.number_area([{'id': c['key'], 'lat': c['lat'], 'lon': c['lon']} for c in cs], lo, hi - lo + 1, frames[digit])
                for c in sorted(cs, key=lambda c: nums[c['key']]):
                    rec = {'key': c['key'], 'muni': FRAME_KEY[digit], 'zone': b['zone'], 'frame': digit, 'index': b['index'], 'nameId': nid,
                           'number': nums[c['key']], 'lat': c['lat'], 'lon': c['lon'], 'anchor': [c['lat'], c['lon']], 'anchorKind': 'centre',
                           'gate': None, 'coverage': 'official-street' if c['official'] else 'nways', 'official': c['official'],
                           'enclosed': c['enclosed'], 'rule': c['rule'], 'settlement': c['settlement'], 'family': c['family'],
                           'label': c['label'], 'structures': c['structures']}
                    out.write(json.dumps(rec, ensure_ascii=False, separators=(',', ':')) + '\n')
                    counts['compounds'] += 1
                    counts[f'digits:{len(str(rec["number"]))}'] += 1
            print(FRAME_KEY[digit], sum(len(v) for v in by_area.values()), 'compounds', flush=True)
    print(json.dumps(counts))


if __name__ == '__main__':
    if sys.argv[1] == 'group':
        cmd_group(os.path.abspath(sys.argv[2]))
    elif sys.argv[1] == 'number':
        cmd_number(os.path.abspath(sys.argv[2]), sys.argv[3])
