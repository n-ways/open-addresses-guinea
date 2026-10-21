#!/usr/bin/env python3
"""Named code areas: how many buildings each locality (quartier, village)
would number, to size the remembered number (place name + digits).

  areas.py DB.duckdb GN PLACES_GEOJSONSEQ OUTDIR CAPITAL_SQL

Localities = OpenStreetMap place nodes (suburb, quarter, neighbourhood,
village, hamlet, town, city, locality, isolated_dwelling) plus GeoNames
populated places (feature class P) not already within 1 km of an OSM place
of the same name. A city/town node is dropped where three or more
suburb/quarter/neighbourhood nodes lie within 5 km (the quartiers then name
the city). Each building goes to its nearest locality (Voronoi cell).
"""
import csv, json, os, subprocess, sys, unicodedata

db, cc, places_path, outdir, capital = sys.argv[1:6]
os.makedirs(outdir, exist_ok=True)
tmp = os.path.join(os.path.dirname(db), f'areas-{cc}.csv')


def norm(s):
    return ''.join(c for c in unicodedata.normalize('NFKD', s or '') if not unicodedata.combining(c)).lower().strip()


rows = []
for line in open(places_path):
    line = line.strip('\x1e\n ')
    if not line:
        continue
    o = json.loads(line)
    p = o['properties']
    if p.get('name'):
        x, y = o['geometry']['coordinates']
        rows.append(('osm', p['place'], p['name'], x, y))
gn = os.path.join(os.environ.get('NWAYS_ROOT', '.'), 'data', 'places', 'geonames', f'{cc}.txt')
osm_names = {}
for r in rows:
    osm_names.setdefault(norm(r[2]), []).append((r[3], r[4]))
for f in csv.reader(open(gn, encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE):
    if len(f) > 7 and f[6] == 'P':
        x, y = float(f[5]), float(f[4])
        near = any(abs(x - a) < 0.009 and abs(y - b) < 0.009 for a, b in osm_names.get(norm(f[1]), []))
        if not near:
            rows.append(('geonames', f[7], f[1], x, y))
with open(tmp, 'w', newline='') as fh:
    w = csv.writer(fh)
    w.writerow(['src', 'kind', 'name', 'lon', 'lat'])
    w.writerows(rows)

SETUP = "LOAD spatial; SET geometry_always_xy=true; SET memory_limit='3GB'; SET threads=4; SET preserve_insertion_order=false;"
sql = f"""{SETUP}
CREATE OR REPLACE TABLE loc0 AS SELECT row_number() OVER () lid, src, kind, "name", ST_Point(lon, lat) g FROM read_csv('{tmp}', header=true);
DELETE FROM loc0 WHERE NOT ST_Intersects(g, (SELECT g FROM country));
CREATE OR REPLACE TABLE loc AS
  SELECT * FROM loc0 a WHERE NOT (a.kind IN ('city','town','PPLC','PPLA','PPLA2') AND
     (SELECT count(*) FROM loc0 b WHERE b.kind IN ('suburb','quarter','neighbourhood','PPLX') AND ST_DWithin(a.g, b.g, 0.045)) >= 3);
CREATE OR REPLACE TABLE vor AS
  SELECT unnest(ST_Dump(ST_VoronoiDiagram(ST_Collect(list(g))))).geom AS g FROM loc;
CREATE OR REPLACE TABLE vcell AS SELECT l.lid, v.g FROM vor v JOIN loc l ON ST_Intersects(v.g, l.g);
CREATE OR REPLACE TABLE ba AS SELECT bm.id, vc.lid FROM bm JOIN vcell vc ON ST_Intersects(vc.g, ST_Point(bm.lon, bm.lat));
"""
r = subprocess.run(['duckdb', db], input=sql, capture_output=True, text=True)
if r.returncode or 'Error' in r.stderr:
    sys.exit(r.stderr[-3000:])


def q(s):
    out = subprocess.run(['duckdb', db, '-json'], input=SETUP + s, capture_output=True, text=True).stdout.strip()
    part = out[out.rindex('\n[') + 1:] if '\n[' in out else out[out.index('['):]
    return json.loads(part)


res = {}
res['localities'] = q("SELECT src, count(*) n FROM loc GROUP BY 1 ORDER BY 1;")
res['perArea'] = q("""WITH c AS (SELECT lid, count(*) n FROM ba GROUP BY lid)
  SELECT count(*) areas_with_buildings, round(quantile_cont(n,0.5)) p50, round(quantile_cont(n,0.9)) p90, round(quantile_cont(n,0.99)) p99, max(n) max_n,
         count(*) FILTER (WHERE n<=450) le_450, count(*) FILTER (WHERE n BETWEEN 451 AND 4500) le_4500,
         count(*) FILTER (WHERE n BETWEEN 4501 AND 45000) le_45000, count(*) FILTER (WHERE n>45000) gt_45000,
         sum(n) FILTER (WHERE n>4500) buildings_in_areas_over_4500, sum(n) total FROM c;""")
res['capitalTop'] = q(f"""WITH cap AS (SELECT ST_Union_Agg(g) g FROM admin WHERE {capital}),
  c AS (SELECT lid, count(*) n FROM ba JOIN bm USING (id) WHERE ST_Intersects((SELECT g FROM cap), ST_Point(bm.lon, bm.lat)) GROUP BY lid)
  SELECT l."name", l.kind, l.src, c.n FROM c JOIN loc l USING (lid) ORDER BY c.n DESC LIMIT 25;""")
res['capitalAreas'] = q(f"""WITH cap AS (SELECT ST_Union_Agg(g) g FROM admin WHERE {capital}),
  c AS (SELECT lid, count(*) n FROM ba JOIN bm USING (id) WHERE ST_Intersects((SELECT g FROM cap), ST_Point(bm.lon, bm.lat)) GROUP BY lid)
  SELECT count(*) areas, round(quantile_cont(n,0.5)) p50, round(quantile_cont(n,0.9)) p90, max(n) max_n,
         count(*) FILTER (WHERE n>4500) over_4500, count(*) FILTER (WHERE n>45000) over_45000 FROM c;""")
json.dump(res, open(os.path.join(outdir, 'areas.json'), 'w'), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False)[:3000])
