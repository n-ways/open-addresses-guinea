#!/usr/bin/env python3
"""Extract every Guinean building footprint with its raw profile facts and its area.

One DuckDB run (memory_limit 3GB, spilling to the work folder) over N-Ways' map
data, read-only:
  data/detail/countries/guinea/buildings-src.geojsonseq  OpenStreetMap buildings (ODbL)
  data/detail/ml/GN.parquet                              Google Open Buildings / Microsoft footprints, with height h (CC BY 4.0 / ODbL)
  model/frames.geojson                                   the five frozen frames
plus the small inputs of tools/prepare-inputs.py in the work folder.

Every footprint gets (engine/SPEC.md 4.1, 8):
  frame     the frame holding its centre; one within 1.1 km of a frame takes the
            nearest (an islet, a sliver between polygons); further out it is
            abroad and dropped
  area      the official quartier holding its centre (admin_level 10), else its
            nearest locality (a Voronoi cell of localities.csv)
  eid       the smallest enclosure holding its centre (walls, fences, hedges,
            farmyards, small residential plots, institutional sites)
  label     the commune (Kaloum, Dixinn, Matam) or préfecture holding it
  street    in Kaloum, the nearest named street within 30 m (official name)

Writes <work>/buildings.csv sorted by area (so tools/issue_registry.py can group
one area at a time), <work>/enclosure-gates.csv and <work>/area-points.csv.

  python3 tools/extract-buildings.py <work folder>
"""
import os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
ROOT = os.environ.get('NWAYS_ROOT', '.')
work = os.path.abspath(sys.argv[1])
osm = os.path.join(ROOT, 'data', 'detail', 'countries', 'guinea', 'buildings-src.geojsonseq')
ml = os.path.join(ROOT, 'data', 'detail', 'ml', 'GN.parquet')
frames = os.path.join(REPO, 'model', 'frames.geojson')
W = lambda f: os.path.join(work, f)

TAGS = ['building', 'amenity', 'shop', 'office', 'religion', 'tourism', 'healthcare', 'man_made',
        'government', 'craft', 'building:levels', 'height', 'name', 'roof:material', 'building:material']
tag_cols = ', '.join(f"json_extract_string(j, '$.properties.\"{t}\"') AS \"{t}\"" for t in TAGS)
null_cols = ', '.join(f"NULL::VARCHAR AS \"{t}\"" for t in TAGS)
# metres on a local equirectangular plane (no projection library needed; Guinea spans 7-13 N)
area_m2 = "ST_Area(g) * 110574.0 * 111320.0 * cos(radians(ST_Y(ST_Centroid(g))))"

sql = f"""
SET memory_limit='3GB'; SET threads=4; SET preserve_insertion_order=false; SET temp_directory='{W('duck-tmp')}';
INSTALL spatial; LOAD spatial;
CREATE TABLE fr AS SELECT digit, geom FROM ST_Read('{frames}');
CREATE TABLE e AS SELECT eid, kind, areaM2, geom FROM ST_Read('{W('enclosures.geojson')}');
CREATE TABLE q AS SELECT qid, "name", geom FROM ST_Read('{W('quartiers.geojson')}');
CREATE TABLE lb AS SELECT lid, level, "name", geom FROM ST_Read('{W('labels.geojson')}');
CREATE TABLE loc AS SELECT id, "name", kind, ST_Point(lon, lat) AS g FROM read_csv('{W('localities.csv')}', header=true,
  columns={{'id':'VARCHAR','src':'VARCHAR','kind':'VARCHAR','name':'VARCHAR','lon':'DOUBLE','lat':'DOUBLE'}});
-- a place over the border names no Guinean home
DELETE FROM loc WHERE NOT EXISTS (SELECT 1 FROM fr WHERE ST_DWithin(fr.geom, loc.g, 0.01));
CREATE TABLE vc AS
  WITH v AS (SELECT unnest(ST_Dump(ST_VoronoiDiagram(ST_Collect(list(g))))).geom AS g FROM loc)
  SELECT loc.id, v.g FROM v JOIN loc ON ST_Intersects(v.g, loc.g);
CREATE TABLE st AS SELECT sid, "name", ST_GeomFromText(wkt) AS g FROM read_csv('{W('streets.csv')}', header=true);
CREATE TABLE p AS SELECT id, "name", category, ST_Point(lon, lat) AS g FROM read_csv('{W('places.csv')}', header=true,
  columns={{'id':'VARCHAR','name':'VARCHAR','category':'VARCHAR','source':'VARCHAR','lon':'DOUBLE','lat':'DOUBLE'}});
CREATE TABLE gt AS SELECT gid, src, barrier, ST_Point(lon, lat) AS g FROM read_csv('{W('gates.csv')}', header=true);
CREATE TABLE raw AS
  SELECT 'osm' AS src, json_extract_string(j, '$.properties."@type"') || '/' || json_extract_string(j, '$.properties."@id"') AS oid,
         ST_GeomFromGeoJSON(json_extract(j, '$.geometry')) AS g, NULL::DOUBLE AS h, {tag_cols}
  FROM (SELECT ltrim(line, chr(30)) AS j FROM read_csv('{osm}', columns={{'line':'VARCHAR'}}, header=false, delim=chr(1), quote='', escape='', max_line_size=16000000) WHERE length(line) > 2)
  UNION ALL
  SELECT 'ml', NULL, geometry, h, {null_cols} FROM '{ml}';
CREATE TABLE b AS SELECT row_number() OVER () AS bid, *, ST_Centroid(g) AS c, {area_m2} AS area,
  ST_Perimeter_Spheroid(ST_FlipCoordinates(g)) AS perim FROM raw;
DROP TABLE raw;
-- frame: inside a frame, else the nearest within 0.01 degrees (about 1.1 km), else abroad
CREATE TABLE bf AS SELECT b.bid, min(fr.digit) AS digit FROM b JOIN fr ON ST_Contains(fr.geom, b.c) GROUP BY b.bid;
CREATE TABLE bf2 AS SELECT bid, arg_min(digit, d) AS digit FROM (
  SELECT b.bid, fr.digit, ST_Distance(fr.geom, b.c) AS d FROM b JOIN fr ON ST_DWithin(fr.geom, b.c, 0.01)
  WHERE b.bid NOT IN (SELECT bid FROM bf)) GROUP BY bid;
CREATE TABLE bfr AS SELECT * FROM bf UNION ALL SELECT * FROM bf2;
DELETE FROM b WHERE bid NOT IN (SELECT bid FROM bfr);
-- area: an official quartier, else the nearest locality
CREATE TABLE bq AS SELECT b.bid, min(q.qid) AS aid FROM b JOIN q ON ST_Contains(q.geom, b.c) GROUP BY b.bid;
CREATE TABLE bv AS SELECT b.bid, min(vc.id) AS aid FROM b JOIN vc ON ST_Intersects(vc.g, b.c) WHERE b.bid NOT IN (SELECT bid FROM bq) GROUP BY b.bid;
CREATE TABLE ba AS SELECT bid, aid, 'quartier' AS how FROM bq UNION ALL SELECT bid, aid, 'locality' FROM bv;
CREATE TABLE be AS SELECT bid, arg_min(eid, areaM2) AS eid FROM (SELECT b.bid, e.eid, e.areaM2 FROM b JOIN e ON ST_Contains(e.geom, b.c)) GROUP BY bid;
CREATE TABLE bl AS SELECT bid, arg_max("name", level) AS label FROM (SELECT b.bid, lb."name", lb.level FROM b JOIN lb ON ST_Contains(lb.geom, b.c)) GROUP BY bid;
CREATE TABLE bp AS SELECT bid, string_agg(DISTINCT category, '|' ORDER BY category) AS poi, string_agg(DISTINCT "name", '|' ORDER BY "name") AS poi_name
  FROM (SELECT b.bid, p.category, p."name" FROM b JOIN p ON ST_Intersects(b.g, ST_Buffer(p.g, 0.00004))) GROUP BY bid;
CREATE TABLE bst AS SELECT bid, arg_min("name", d) AS street FROM (
  SELECT b.bid, st."name", ST_Distance(st.g, b.c) AS d FROM b JOIN bl USING (bid) JOIN st ON ST_DWithin(st.g, b.c, 0.00027)
  WHERE bl.label = 'Kaloum') GROUP BY bid;
COPY (SELECT ba.aid, ba.how, bfr.digit AS frame, b.src, b.oid, round(ST_X(b.c), 7) AS lon, round(ST_Y(b.c), 7) AS lat,
        round(b.area, 1) AS area, round(b.perim, 1) AS perim, b.h, {', '.join(f'b."{t}"' for t in TAGS)},
        be.eid, bl.label, bp.poi, bp.poi_name, bst.street, ST_AsText(ST_ReducePrecision(b.g, 0.0000001)) AS wkt
      FROM b JOIN bfr USING (bid) JOIN ba USING (bid) LEFT JOIN be USING (bid) LEFT JOIN bl USING (bid) LEFT JOIN bp USING (bid) LEFT JOIN bst USING (bid)
      ORDER BY ba.aid, lat, lon, area, b.src, b.oid)
  TO '{W('buildings.csv')}' (HEADER, DELIMITER ',');
COPY (SELECT e.eid, e.kind, e.areaM2, count(gt.gid) AS gates FROM e LEFT JOIN gt ON ST_DWithin(e.geom, gt.g, 0.00005) GROUP BY ALL ORDER BY e.eid)
  TO '{W('enclosure-gates.csv')}' (HEADER, DELIMITER ',');
-- each area's point (the locality node, or a point inside the quartier), its frame and label
COPY (WITH a AS (SELECT id AS aid, 'locality' AS how, "name", g FROM loc
                 UNION ALL SELECT qid, 'quartier', "name", ST_PointOnSurface(geom) FROM q)
      SELECT a.aid, a.how, a."name", round(ST_X(a.g), 6) AS lon, round(ST_Y(a.g), 6) AS lat,
             (SELECT min(digit) FROM fr WHERE ST_Contains(fr.geom, a.g)) AS frame,
             (SELECT arg_max(lb."name", lb.level) FROM lb WHERE ST_Contains(lb.geom, a.g)) AS label
      FROM a ORDER BY a.aid)
  TO '{W('area-points.csv')}' (HEADER, DELIMITER ',');
SELECT count(*) AS footprints, sum(CASE WHEN src='osm' THEN 1 ELSE 0 END) AS osm FROM b;
SELECT how, count(*) FROM ba GROUP BY 1;
SELECT count(*) AS localities FROM loc;
"""
r = subprocess.run(['duckdb', '-csv'], input=sql, capture_output=True, text=True)
print(r.stdout[-2000:], r.stderr[-3000:])
sys.exit(r.returncode)
