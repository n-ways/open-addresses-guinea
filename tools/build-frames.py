#!/usr/bin/env python3
"""Build Guinea's five code frames (model/frames.json, model/frames.geojson).

A frame is one of the postal regions of La Poste guinéenne's UPU address
format (2005): 0 Conakry, 1 Basse-Guinée, 2 Moyenne-Guinée, 3 Haute-Guinée,
4 Guinée forestière. Its polygon is the union of the administrative regions
of October 2026 (N-Ways regions table, OpenStreetMap boundaries), frozen:
later reforms (the August 2026 decrees creating Beyla and Siguiri regions,
new préfectures, new communes in Conakry) change place names shown beside a
code, never the frame a code belongs to.

  tools/build-frames.py            (reads postgres:///nmap?host=/tmp, read-only)
"""
import json, math, os, subprocess

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = 'postgres:///nmap?host=/tmp'
FRAMES = [
    (0, 'Conakry', 'Conakry', ['GN-C']),
    (1, 'Basse-Guinée', 'Lower Guinea', ['GN-B', 'GN-D']),
    (2, 'Moyenne-Guinée', 'Middle Guinea (Fouta Djallon)', ['GN-L', 'GN-M']),
    (3, 'Haute-Guinée', 'Upper Guinea', ['GN-K', 'GN-F']),
    (4, 'Guinée forestière', 'Forest Guinea', ['GN-N']),
]
frames, feats = [], []
for d, fr, en, codes in FRAMES:
    q = ("SELECT ST_XMin(g), ST_YMin(g), ST_XMax(g), ST_YMax(g), ST_AsGeoJSON(ST_SimplifyPreserveTopology(g, 0.0002)) FROM "
         f"(SELECT ST_Union(geom) g FROM regions WHERE code IN ({','.join(repr(c) for c in codes)})) t")
    x0, y0, x1, y1, gj = subprocess.run(['psql', DB, '-Atc', q, '-F', '|'], capture_output=True, text=True, check=True).stdout.strip().split('|', 4)
    x0, y0, x1, y1 = (float(v) for v in (x0, y0, x1, y1))
    west, south = math.floor(x0 * 100) / 100, math.floor(y0 * 100) / 100
    ref = round((y0 + y1) / 2, 2)
    w_km = (x1 - west) * 111.32 * math.cos(math.radians(ref)); h_km = (y1 - south) * 110.6
    assert w_km < 480 and h_km < 480, (fr, w_km, h_km)
    frames.append({'digit': d, 'name': fr, 'nameEn': en, 'regions2026': codes, 'west': west, 'south': south, 'refLat': ref,
                   'box': [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)],
                   'extentKm': [round(w_km, 1), round(h_km, 1)], 'blocsUsed': [math.ceil(w_km / 1.2), math.ceil(h_km / 1.2)]})
    feats.append({'type': 'Feature', 'properties': {'digit': d, 'name': fr}, 'geometry': json.loads(gj)})
json.dump({'country': 'GN', 'version': '2026-10-18', 'frozen': False, 'cellMetres': 3.0, 'blocMetres': 1200, 'carreMetres': 60,
           'note': 'Frozen once the first code is issued. Digit = first digit of the UPU postal radical (001 BP Conakry, 100 BP Kindia, 200 BP Labé ...).',
           'frames': frames}, open(os.path.join(REPO, 'model', 'frames.json'), 'w'), ensure_ascii=False, indent=1)
json.dump({'type': 'FeatureCollection', 'features': feats}, open(os.path.join(REPO, 'model', 'frames.geojson'), 'w'), separators=(',', ':'), ensure_ascii=False)
for f in frames:
    print(f['digit'], f['name'], f['extentKm'], f['blocsUsed'])
