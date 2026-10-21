#!/usr/bin/env python3
"""Guinea's named code areas, sized from the real building counts.

  tools/areas-gn.py STAGED.duckdb PLACES.geojsonseq OUTDIR [SAMPLE_QUARTIER]

Guinea-specific rules (model.md, "Areas"):
  1. Where OpenStreetMap has an official quartier polygon (admin_level 10:
     Conakry's quartiers, and quartiers of Nzérékoré, Coyah, Kankan …), the
     area is that quartier, with its official name.
  2. Elsewhere the area is the nearest named locality: OSM place nodes
     (town, village, hamlet, suburb, quarter, neighbourhood …) plus GeoNames
     populated places (class P) that OSM lacks (Voronoi cells).
  3. Every area belongs to the frame (0–4) holding most of its buildings
     (model/frames.geojson, frozen).
Counts are structures (footprints). Compounds are estimated with Conakry's
measured ratio (structures per compound) where compounds were not grouped.
With SAMPLE_QUARTIER, numbers that quartier's compounds (Conakry grouping
from tools/analyze.py) and writes OUTDIR/sample-<quartier>.json.
DuckDB runs at memory_limit 3GB.
"""
import csv, json, os, subprocess, sys, unicodedata

db, places_path, outdir = sys.argv[1:4]
sample = sys.argv[4] if len(sys.argv) > 4 else None
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(outdir, exist_ok=True)
tmp = os.path.join(os.path.dirname(db), 'areas-gn-places.csv')


def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s or '') if not unicodedata.combining(c)).lower().strip()


rows = []
for line in open(places_path):
    line = line.strip('\x1e\n ')
    if line:
        o = json.loads(line); p = o['properties']
        if p.get('name'):
            x, y = o['geometry']['coordinates']
            rows.append(('osm', p['place'], p['name'], x, y))
seen = {}
for r in rows:
    seen.setdefault(norm(r[2]), []).append((r[3], r[4]))
for f in csv.reader(open(os.path.join(os.environ.get('NWAYS_ROOT', '.'), 'data', 'places', 'geonames', 'GN.txt'), encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE):
    if len(f) > 7 and f[6] == 'P':
        x, y = float(f[5]), float(f[4])
        if not any(abs(x - a) < 0.009 and abs(y - b) < 0.009 for a, b in seen.get(norm(f[1]), [])):
            rows.append(('geonames', f[7], f[1], x, y))
with open(tmp, 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['src', 'kind', 'name', 'lon', 'lat']); w.writerows(rows)

frames = os.path.join(REPO, 'model', 'frames.geojson')
SETUP = "LOAD spatial; SET geometry_always_xy=true; SET memory_limit='3GB'; SET threads=4; SET preserve_insertion_order=false;"
sql = f"""{SETUP}
CREATE OR REPLACE TABLE fr AS SELECT digit, geom AS g FROM ST_Read('{frames}');
CREATE OR REPLACE TABLE loc0 AS SELECT row_number() OVER () lid, src, kind, "name", ST_Point(lon, lat) g FROM read_csv('{tmp}', header=true);
DELETE FROM loc0 WHERE NOT ST_Intersects(g, (SELECT g FROM country));
CREATE OR REPLACE TABLE loc AS SELECT * FROM loc0 a WHERE NOT (a.kind IN ('city','town','PPLC','PPLA','PPLA2') AND
   (SELECT count(*) FROM loc0 b WHERE b.kind IN ('suburb','quarter','neighbourhood','PPLX') AND ST_DWithin(a.g, b.g, 0.045)) >= 3);
CREATE OR REPLACE TABLE vcell AS
  WITH v AS (SELECT unnest(ST_Dump(ST_VoronoiDiagram(ST_Collect(list(g))))).geom AS g FROM loc)
  SELECT l.lid, v.g FROM v JOIN loc l ON ST_Intersects(v.g, l.g);
CREATE OR REPLACE TABLE qtr AS SELECT 100000000 + row_number() OVER () lid, "name", g FROM admin WHERE level = 10;
CREATE OR REPLACE TABLE ba_q AS SELECT bm.id, any_value(q.lid) lid FROM bm JOIN qtr q ON ST_Intersects(q.g, ST_Point(bm.lon, bm.lat)) GROUP BY bm.id;
CREATE OR REPLACE TABLE ba_v AS SELECT bm.id, vc.lid FROM bm LEFT JOIN ba_q USING (id) JOIN vcell vc ON ST_Intersects(vc.g, ST_Point(bm.lon, bm.lat)) WHERE ba_q.id IS NULL;
CREATE OR REPLACE TABLE ba AS SELECT id, lid, 'quartier' how FROM ba_q UNION ALL SELECT id, lid, 'locality' FROM ba_v;
CREATE OR REPLACE TABLE bf AS SELECT bm.id, any_value(fr.digit) digit FROM bm JOIN fr ON ST_Intersects(fr.g, ST_Point(bm.lon, bm.lat)) GROUP BY bm.id;
CREATE OR REPLACE TABLE area AS
  SELECT ba.lid, any_value(ba.how) how, mode(bf.digit) digit, count(*) n FROM ba LEFT JOIN bf USING (id) GROUP BY ba.lid;
"""
r = subprocess.run(['duckdb', db], input=sql, capture_output=True, text=True)
if r.returncode or 'Error' in r.stderr:
    sys.exit(r.stderr[-3000:])


def q(s):
    out = subprocess.run(['duckdb', db, '-json'], input=SETUP + s, capture_output=True, text=True).stdout.strip()
    return json.loads(out[out.rindex('\n[') + 1:] if '\n[' in out else out[out.index('['):])


# Conakry measured structures-per-compound ratio (analyze.py grouping)
ratio = q("SELECT count(*)::DOUBLE / count(DISTINCT cid) r FROM comp;")[0]['r']
res = {'structuresPerCompoundConakry': round(ratio, 3)}
res['localities'] = q("SELECT src, count(*) n FROM loc GROUP BY 1 ORDER BY 1;")
res['quartierPolygons'] = q("SELECT count(*) n FROM qtr;")
est = f"n / {ratio}"
res['byFrame'] = q(f"""SELECT digit, how, count(*) areas, sum(n) structures, round(quantile_cont(n,0.5)) p50, round(quantile_cont(n,0.9)) p90, max(n) max_n,
   count(*) FILTER (WHERE {est} <= 4500) four_digits, count(*) FILTER (WHERE {est} > 4500 AND {est} <= 45000) five_digits,
   count(*) FILTER (WHERE {est} > 45000) split FROM area GROUP BY ALL ORDER BY digit, how;""")
res['all'] = q(f"""SELECT count(*) areas, sum(n) structures, round(quantile_cont(n,0.5)) p50, round(quantile_cont(n,0.9)) p90, round(quantile_cont(n,0.99)) p99, max(n) max_n,
   count(*) FILTER (WHERE {est} <= 4500) four_digits, count(*) FILTER (WHERE {est} > 4500 AND {est} <= 45000) five_digits,
   count(*) FILTER (WHERE {est} > 45000) split, sum(n) FILTER (WHERE {est} > 4500) structures_in_5digit_or_split,
   max(digit) FILTER (WHERE false) x FROM area;""")
res['biggest'] = q("""SELECT coalesce(q."name", l."name") "name", a.how, a.digit, a.n FROM area a LEFT JOIN qtr q USING (lid) LEFT JOIN loc l USING (lid)
   ORDER BY a.n DESC LIMIT 25;""")
res['conakryQuartiers'] = q(f"""SELECT count(*) quartiers, sum(n) structures, round(quantile_cont(n,0.5)) p50, round(quantile_cont(n,0.9)) p90, max(n) max_n,
   count(*) FILTER (WHERE {est} > 4500) over_4500_compounds FROM area WHERE how='quartier' AND digit=0;""")
if sample:
    res['sample'] = q(f"""SELECT q."name", a.n FROM area a JOIN qtr q USING (lid) WHERE q."name" = '{sample}';""")
    pts = q(f"""WITH s AS (SELECT ba.id FROM ba JOIN qtr q ON q.lid = ba.lid WHERE q."name" = '{sample}'),
       c AS (SELECT comp.cid, cb.id, cb.lat, cb.lon, cb.area_m2, cb.cls, cb.sub, cb.floors, cb.h_m, cb.h_src, cb.cls_src, cb.conf, cb.src
             FROM comp JOIN cb USING (id) WHERE comp.cid IN (SELECT comp.cid FROM comp JOIN s USING (id)))
       SELECT cid, count(*) structures, round(sum(area_m2),1) footprint_m2, round(sum(area_m2*floors),1) floor_area_m2,
              arg_max(lat, area_m2) lat, arg_max(lon, area_m2) lon, arg_max(cls, area_m2) cls, arg_max(sub, area_m2) sub,
              arg_max(cls_src, area_m2) cls_src, round(arg_max(conf, area_m2),2) conf, max(floors) floors,
              list(src ORDER BY area_m2 DESC) sources FROM c GROUP BY cid ORDER BY cid;""")
    res['samplePoints'] = pts
json.dump(res, open(os.path.join(outdir, 'areas-gn.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in res.items() if k != 'samplePoints'}, ensure_ascii=False)[:4000])
