#!/usr/bin/env python3
"""The small inputs of Guinea's registry build, in a work folder.

Reads, read-only, the osmium exports of N-Ways' Guinea extract (tools/README.md,
"Inputs prepared with osmium": admin, bar, place, hw and site .geojsonseq in the
work folder), N-Ways' routing compounds and gates (data/valhalla), N-Ways places
(the database) and GeoNames, and writes:

  enclosures.geojson  walls, fences, hedges and retaining walls closed into rings
                      (40-20,000 m2), landuse=farmyard (<= 10,000 m2) and small
                      landuse=residential plots (<= 2,500 m2), institutional sites
                      (schools, hospitals, markets, mosques, military ...) and
                      N-Ways' government, military, police and site compounds
  gates.csv           OpenStreetMap barrier=gate/entrance points, N-Ways gates
  places.csv          N-Ways places (POIs) in Guinea
  localities.csv      the named places an area can take its name from (SPEC 4.1):
                      OpenStreetMap place nodes, then GeoNames populated places
                      OSM lacks (no OSM node of the same name within 1 km); a town
                      node with 3+ quartier nodes within 5 km is dropped (its
                      quartiers name its parts)
  quartiers.geojson   official quartier polygons (admin_level 10)
  labels.geojson      préfectures (admin_level 6) and the communes of Kaloum,
                      Dixinn and Matam (admin_level 8), shown beside codes
  streets.csv         named streets of Kaloum (the official street names of the
                      national addressing programme, 2024), split into segments

Every id is stable: osm:<type>/<id>, geonames:<id>, nways:<id>.

  python3 tools/prepare-inputs.py <work folder>
"""
import csv, json, math, os, re, subprocess, sys, unicodedata

ROOT = os.environ.get('NWAYS_ROOT', '.')
DB = os.environ.get('NWAYS_DB', 'postgres:///nmap?host=/tmp')
work = os.path.abspath(sys.argv[1])
W = lambda f: os.path.join(work, f)
BOX = (-15.4, 7.1, -7.6, 12.7)


def seq(path):
    for line in open(path, encoding='utf-8'):
        line = line.strip('\x1e\n ')
        if line:
            yield json.loads(line)


def oid(p):
    return f"osm:{p.get('@type', 'way')}/{p.get('@id')}"


def ring_area(ring):
    """Area of a lon/lat ring in m2 (local equirectangular)."""
    k = math.cos(math.radians(ring[0][1])) * 111320.0
    a = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i][0] * k, ring[i][1] * 110574.0
        x2, y2 = ring[i + 1][0] * k, ring[i + 1][1] * 110574.0
        a += x1 * y2 - x2 * y1
    return abs(a) / 2


def polys(g):
    if g['type'] == 'Polygon':
        return [g['coordinates']]
    if g['type'] == 'MultiPolygon':
        return g['coordinates']
    if g['type'] == 'LineString' and len(g['coordinates']) >= 4 and g['coordinates'][0] == g['coordinates'][-1]:
        return [[g['coordinates']]]
    return []


def poly_area(ps):
    return sum(ring_area(p[0]) - sum(ring_area(h) for h in p[1:]) for p in ps)


def in_box(x, y):
    return BOX[0] <= x <= BOX[2] and BOX[1] <= y <= BOX[3]


def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s or '') if not unicodedata.combining(c)).lower().strip()


# ---------------------------------------------------------------- enclosures
feats, seen = [], set()
LIMIT = {'wall': (40, 20000), 'fence': (40, 20000), 'hedge': (40, 20000), 'retaining_wall': (40, 20000),
         'farmyard': (40, 10000), 'residential': (40, 2500)}
for o in seq(W('bar.geojsonseq')):
    p, g = o['properties'], o['geometry']
    kind = p.get('barrier') if p.get('barrier') in LIMIT else p.get('landuse') if p.get('landuse') in ('farmyard', 'residential') else None
    ps = polys(g)
    if not kind or not ps:
        continue
    i = oid(p)
    if i in seen:          # osmium writes a closed way twice (line and area)
        continue
    a = poly_area(ps)
    lo, hi = LIMIT[kind]
    if lo <= a <= hi:
        seen.add(i)
        feats.append({'type': 'Feature', 'properties': {'eid': i, 'kind': 'osm-' + kind, 'areaM2': round(a, 1)},
                      'geometry': {'type': 'MultiPolygon', 'coordinates': ps}})
for o in seq(W('site.geojsonseq')):
    p, g = o['properties'], o['geometry']
    ps = polys(g)
    i = oid(p)
    if not ps or i in seen:
        continue
    if p.get('amenity'):
        kind = 'osm-amenity-' + p['amenity']
    elif p.get('landuse'):
        kind = 'osm-' + p['landuse']
    else:
        continue
    a = poly_area(ps)
    if 40 <= a <= 400000:
        seen.add(i)
        feats.append({'type': 'Feature', 'properties': {'eid': i, 'kind': kind, 'areaM2': round(a, 1)},
                      'geometry': {'type': 'MultiPolygon', 'coordinates': ps}})
for o in seq(os.path.join(ROOT, 'data', 'valhalla', 'compounds.geojsonseq')):
    p, g = o['properties'], o['geometry']
    ps = polys(g)
    if not ps or not in_box(*ps[0][0][0]):
        continue
    a = poly_area(ps)
    if 40 <= a <= 400000:
        feats.append({'type': 'Feature', 'properties': {'eid': 'nways:' + str(p['id']), 'kind': 'nways-' + p['kind'], 'areaM2': round(a, 1)},
                      'geometry': {'type': 'MultiPolygon', 'coordinates': ps}})
json.dump({'type': 'FeatureCollection', 'features': feats}, open(W('enclosures.geojson'), 'w'))

# ---------------------------------------------------------------- gates
with open(W('gates.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['gid', 'src', 'barrier', 'lon', 'lat'])
    for o in seq(W('bar.geojsonseq')):
        p, g = o['properties'], o['geometry']
        if g['type'] == 'Point' and (p.get('barrier') in ('gate', 'lift_gate', 'sliding_gate', 'swing_gate', 'entrance') or p.get('entrance')):
            w.writerow([oid(p), 'osm', p.get('barrier') or 'entrance', *g['coordinates']])
    for o in seq(os.path.join(ROOT, 'data', 'valhalla', 'gates.geojsonseq')):
        p, g = o['properties'], o['geometry']
        if g['type'] == 'Point' and in_box(*g['coordinates']):
            w.writerow(['nways:' + str(p.get('id')), 'nways', p.get('barrier') or p.get('kind') or 'gate', *g['coordinates']])

# ---------------------------------------------------------------- N-Ways places (POIs)
with open(W('places.csv'), 'w') as f:
    subprocess.run(['psql', DB, '-Atc', """COPY (SELECT p.id, p.name, p.category, p.source, ST_X(p.location::geometry) lon, ST_Y(p.location::geometry) lat
        FROM places p JOIN regions r ON ST_Intersects(r.geom, p.location::geometry) WHERE r.country='GN' ORDER BY p.id) TO STDOUT WITH CSV HEADER"""],
                   stdout=f, check=True)

# ---------------------------------------------------------------- localities (area names)
loc = []
for o in seq(W('place.geojsonseq')):
    p, g = o['properties'], o['geometry']
    if p.get('name') and g['type'] == 'Point':
        loc.append({'id': oid(p), 'src': 'osm', 'kind': p['place'], 'name': p['name'].strip(), 'lon': g['coordinates'][0], 'lat': g['coordinates'][1]})
near = {}
for r in loc:
    near.setdefault(norm(r['name']), []).append((r['lon'], r['lat']))
for f in csv.reader(open(os.path.join(ROOT, 'data', 'places', 'geonames', 'GN.txt'), encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE):
    if len(f) > 7 and f[6] == 'P' and f[8] == 'GN':
        x, y = float(f[5]), float(f[4])
        if not any(abs(x - a) < 0.009 and abs(y - b) < 0.009 for a, b in near.get(norm(f[1]), [])):
            loc.append({'id': 'geonames:' + f[0], 'src': 'geonames', 'kind': f[7], 'name': f[1].strip(), 'lon': x, 'lat': y})
QUARTER = ('suburb', 'quarter', 'neighbourhood', 'PPLX')
qpts = [(r['lon'], r['lat']) for r in loc if r['kind'] in QUARTER]


def crowded(r):
    k = math.cos(math.radians(r['lat']))
    return sum(1 for x, y in qpts if math.hypot((x - r['lon']) * k * 111.32, (y - r['lat']) * 110.57) <= 5) >= 3


loc = [r for r in loc if not (r['kind'] in ('city', 'town', 'PPLC', 'PPLA', 'PPLA2') and crowded(r))]
loc.sort(key=lambda r: r['id'])
with open(W('localities.csv'), 'w', newline='') as f:
    w = csv.DictWriter(f, ['id', 'src', 'kind', 'name', 'lon', 'lat'])
    w.writeheader()
    w.writerows(loc)

# ---------------------------------------------------------------- quartiers and labels
q, lab = [], []
for o in seq(W('admin.geojsonseq')):
    p = o['properties']
    lv = p.get('admin_level')
    if lv == '10':
        q.append({'type': 'Feature', 'properties': {'qid': oid(p), 'name': (p.get('name') or '').strip()}, 'geometry': o['geometry']})
    elif lv == '6' or (lv == '8' and p.get('name') in ('Kaloum', 'Dixinn', 'Matam')) or (lv == '4' and p.get('name') == 'Conakry'):
        lab.append({'type': 'Feature', 'properties': {'lid': oid(p), 'level': int(lv), 'name': p['name'].replace('Préfecture de ', '').replace("Préfecture d'", '')},
                    'geometry': o['geometry']})
json.dump({'type': 'FeatureCollection', 'features': sorted(q, key=lambda f: f['properties']['qid'])}, open(W('quartiers.geojson'), 'w'), ensure_ascii=False)
json.dump({'type': 'FeatureCollection', 'features': lab}, open(W('labels.geojson'), 'w'), ensure_ascii=False)

# ---------------------------------------------------------------- Kaloum's streets
kal = next(f for f in lab if f['properties']['name'] == 'Kaloum')
SKIP = ('footway', 'path', 'steps', 'track', 'cycleway', 'proposed', 'construction', 'motorway_link', 'trunk_link')
kb = [min(c[0] for p in polys(kal['geometry']) for c in p[0]), min(c[1] for p in polys(kal['geometry']) for c in p[0]),
      max(c[0] for p in polys(kal['geometry']) for c in p[0]), max(c[1] for p in polys(kal['geometry']) for c in p[0])]
with open(W('streets.csv'), 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['sid', 'name', 'highway', 'wkt'])
    for o in seq(W('hw.geojsonseq')):
        p, g = o['properties'], o['geometry']
        nm = (p.get('name') or '').strip()
        # a street word typed in capitals by a mapper ("AVENUE Dinah Salifou") is written as the plates write it
        nm = re.sub(r'^(AVENUE|RUE|BOULEVARD|ROUTE|CORNICHE|IMPASSE)\b', lambda m: m.group(1).capitalize(), nm)
        if not nm or p.get('highway') in SKIP or nm.startswith(('Pont ', 'Pénétrante')) or g['type'] != 'LineString':
            continue
        cs = g['coordinates']
        if not any(kb[0] <= x <= kb[2] and kb[1] <= y <= kb[3] for x, y in cs):
            continue
        w.writerow([oid(p), nm, p.get('highway'), 'LINESTRING(' + ','.join(f'{x:.7f} {y:.7f}' for x, y in cs) + ')'])
print(len(feats), 'enclosures,', len(loc), 'localities,', len(q), 'quartiers,', len(lab), 'labels')
