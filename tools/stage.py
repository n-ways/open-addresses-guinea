#!/usr/bin/env python3
"""Stage Guinea's buildings, zones, places, enclosures and gates into a
DuckDB file for the zone and building-profile statistics.

  stage.py GN guinea ADMIN_GEOJSONSEQ BARRIERS_GEOJSONSEQ OUT.duckdb

Inputs are read-only: N-Ways data/ (OSM building extract, ML footprints,
routing compounds and gates), the N-Ways database (regions, places) and an
osmium export of Guinea's OSM administrative boundaries and barriers.
DuckDB runs under a 3 GB memory cap.
"""
import csv, json, os, subprocess, sys, tempfile

cc, slug, admin, barriers, out = sys.argv[1:6]
ROOT = os.environ.get('NWAYS_ROOT', '.')
DB = 'postgres:///nmap?host=/tmp'
tmp = tempfile.mkdtemp(prefix=f'stage-{cc}-', dir=os.path.dirname(out))


def psql_csv(sql, path):
    with open(path, 'w') as f:
        subprocess.run(['psql', DB, '-Atc', f'COPY ({sql}) TO STDOUT WITH CSV HEADER'], stdout=f, check=True)


psql_csv(f"SELECT code, name_fr, ST_AsText(geom) wkt FROM regions WHERE country='{cc}'", f'{tmp}/regions.csv')
psql_csv(f"""SELECT p.id, p.name, p.category, p.source, ST_X(p.location::geometry) lon, ST_Y(p.location::geometry) lat
             FROM places p JOIN regions r ON ST_Intersects(r.geom, p.location::geometry) WHERE r.country='{cc}'""",
         f'{tmp}/places.csv')


def seq(path):
    for line in open(path):
        line = line.strip('\x1e\n ')
        if line:
            yield json.loads(line)


with open(f'{tmp}/admin.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['osm', 'level', 'name', 'iso', 'geojson'])
    for o in seq(admin):
        p = o['properties']
        if p.get('admin_level') and o['geometry']['type'] in ('Polygon', 'MultiPolygon'):
            w.writerow([str(p.get('@type', 'x'))[0] + str(p.get('@id', '')), int(p['admin_level']), p.get('name', ''), p.get('ISO3166-2', ''),
                        json.dumps(o['geometry'])])

with open(f'{tmp}/barriers.csv', 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['kind', 'geojson'])
    for o in seq(barriers):
        p, g = o['properties'], o['geometry']
        b = p.get('barrier')
        if b in ('wall', 'fence', 'hedge', 'retaining_wall'):
            if g['type'] == 'LineString' and g['coordinates'][0] == g['coordinates'][-1] and len(g['coordinates']) >= 4:
                g = {'type': 'Polygon', 'coordinates': [g['coordinates']]}
            if g['type'] in ('Polygon', 'MultiPolygon'):
                w.writerow(['enclosure:' + b, json.dumps(g)])
        elif g['type'] == 'Point' and (b in ('gate', 'lift_gate', 'sliding_gate', 'swing_gate', 'entrance') or 'entrance' in p):
            w.writerow(['gate', json.dumps(g)])
        elif p.get('landuse') == 'residential' and g['type'] in ('Polygon', 'MultiPolygon'):
            w.writerow(['landuse:residential', json.dumps(g)])

for name in ('compounds', 'gates'):
    with open(f'{tmp}/nw-{name}.csv', 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['id', 'kind', 'name', 'geojson'])
        for o in seq(f'{ROOT}/data/valhalla/{name}.geojsonseq'):
            p = o['properties']
            w.writerow([p.get('id'), p.get('kind') or p.get('barrier'), p.get('name') or p.get('compoundName') or '',
                        json.dumps(o['geometry'])])

def mls(name):
    return max(len(l) for l in open(f'{tmp}/{name}')) * 2 + 1_000_000


osm = f'{ROOT}/data/detail/countries/{slug}/buildings-src.geojsonseq'
ml = f'{ROOT}/data/detail/ml/{cc}.parquet'
sql = f"""
SET memory_limit='3GB'; SET threads=4; SET preserve_insertion_order=false;
INSTALL spatial; LOAD spatial; SET geometry_always_xy=true;
CREATE OR REPLACE TABLE country AS SELECT ST_Union_Agg(ST_GeomFromText(wkt)) g FROM read_csv('{tmp}/regions.csv', header=true);
CREATE OR REPLACE TABLE regions AS SELECT code, name_fr, ST_GeomFromText(wkt) g FROM read_csv('{tmp}/regions.csv', header=true);
CREATE OR REPLACE TABLE admin AS
  SELECT a.osm, a.level, a."name", a.iso, ST_GeomFromGeoJSON(a.geojson) g
  FROM read_csv('{tmp}/admin.csv', header=true, max_line_size={mls('admin.csv')}) a;
DELETE FROM admin WHERE NOT ST_Intersects(ST_PointOnSurface(g), (SELECT g FROM country));
CREATE OR REPLACE TABLE places AS
  SELECT id, "name", category, source, ST_Point(lon, lat) AS g FROM read_csv('{tmp}/places.csv', header=true);
CREATE OR REPLACE TABLE barriers AS
  SELECT kind, ST_GeomFromGeoJSON(geojson) g FROM read_csv('{tmp}/barriers.csv', header=true, max_line_size={mls('barriers.csv')});
CREATE OR REPLACE TABLE nw_compounds AS
  SELECT id, kind, "name", ST_GeomFromGeoJSON(geojson) AS g FROM read_csv('{tmp}/nw-compounds.csv', header=true, max_line_size={mls('nw-compounds.csv')});
DELETE FROM nw_compounds WHERE NOT ST_Intersects(ST_PointOnSurface(g), (SELECT g FROM country));
CREATE OR REPLACE TABLE nw_gates AS
  SELECT id, kind, "name", ST_GeomFromGeoJSON(geojson) AS g FROM read_csv('{tmp}/nw-gates.csv', header=true);
DELETE FROM nw_gates WHERE NOT ST_Intersects(g, (SELECT g FROM country));
CREATE OR REPLACE TABLE b AS
  WITH o AS (
    SELECT json_extract(ltrim(line, chr(30)), '$') j FROM read_csv('{osm}', columns={{'line': 'VARCHAR'}}, header=false,
      delim=chr(1), quote='', escape='', max_line_size=16000000) WHERE length(line) > 2)
  SELECT 'osm' src, ST_GeomFromGeoJSON(j->'geometry') g,
         j->>'$.properties.building' building, j->>'$.properties."building:levels"' levels, j->>'$.properties.height' height,
         j->>'$.properties.amenity' amenity, j->>'$.properties.shop' shop, j->>'$.properties.office' office,
         j->>'$.properties.tourism' tourism, j->>'$.properties.religion' religion, j->>'$.properties.healthcare' healthcare,
         j->>'$.properties.man_made' man_made, j->>'$.properties.name' AS "name", NULL::DOUBLE h_ml
  FROM o
  UNION ALL
  SELECT 'ml', geometry, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, NULL, h FROM '{ml}';
ALTER TABLE b ADD COLUMN id BIGINT; UPDATE b SET id = rowid;
CREATE OR REPLACE TABLE bm AS
  SELECT id, ST_X(ST_Centroid(g)) lon, ST_Y(ST_Centroid(g)) lat,
         ST_Area(g) * 110574 * 111320 * cos(radians(ST_Y(ST_Centroid(g)))) area_m2,
         ST_Perimeter_Spheroid(g) perim_m
  FROM b;
"""
r = subprocess.run(['duckdb', out], input=sql, capture_output=True, text=True)
print(r.stdout[-3000:], r.stderr)
