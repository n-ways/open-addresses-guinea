#!/usr/bin/env python3
"""Zone, building-profile and compound statistics from a staged country DB.

  analyze.py DB.duckdb OUTDIR ZONE_LEVELS CAPITAL_SQL [ROUND_HUT_MAX_M2]

ZONE_LEVELS: comma list of OSM admin levels to count buildings in (e.g. 6 or 6,8).
CAPITAL_SQL: predicate on table admin selecting the capital's polygon(s),
             e.g. "level=4 AND name='Conakry'".
"""
import json, os, subprocess, sys

db, outdir, levels, capital = sys.argv[1:5]
hut_max = float(sys.argv[5]) if len(sys.argv) > 5 else 60
os.makedirs(outdir, exist_ok=True)

GOV_RE = r"(?i)(minist|pr[ée]fect|sous-pr[ée]f|mairie|h[ôo]tel de ville|gouvern|ambassade|embassy|consulat|tribunal|cour d|court|direction g[ée]n[ée]rale|assembl[ée]e|s[ée]nat|d[ée]l[ée]gation|delegation|council|commissariat|gendarmerie|douane|tr[ée]sor|imp[ôo]ts|caisse nationale|cnss|cnps|palais)"

SETUP = """LOAD spatial; SET geometry_always_xy=true; SET memory_limit='3GB'; SET threads=4; SET preserve_insertion_order=false;"""

PROFILE = f"""
{SETUP}
-- POIs inside footprints (one per building: the most specific)
CREATE OR REPLACE TABLE poi_in AS
  SELECT b.id, arg_max(p.category, length(p."name")) category, arg_max(p."name", length(p."name")) pname, count(*) n
  FROM places p JOIN b ON ST_Intersects(b.g, p.g) GROUP BY b.id;
CREATE OR REPLACE TABLE gov_in AS
  SELECT b.id, any_value(c.kind) kind FROM nw_compounds c JOIN bm ON ST_Intersects(c.g, ST_Point(bm.lon, bm.lat)) JOIN b ON b.id=bm.id
  WHERE c.kind IN ('government','military','police') GROUP BY b.id;
CREATE OR REPLACE TABLE prof AS
WITH x AS (
  SELECT b.id, b.src, bm.lon, bm.lat, bm.area_m2, bm.perim_m,
         4*pi()*bm.area_m2/nullif(bm.perim_m*bm.perim_m,0) circ,
         lower(b.building) bt, b.amenity, b.shop, b.office, b.tourism, b.religion, b.healthcare, b.man_made, b."name" oname,
         TRY_CAST(regexp_extract(b.height, '[0-9.]+') AS DOUBLE) h_osm, TRY_CAST(regexp_extract(b.levels, '[0-9]+') AS INT) lv_osm, b.h_ml,
         p.category, p.pname, g.kind govkind
  FROM b JOIN bm USING (id) LEFT JOIN poi_in p USING (id) LEFT JOIN gov_in g USING (id))
SELECT *,
  coalesce(h_osm, lv_osm*3.2, h_ml) h_m,
  CASE WHEN h_osm IS NOT NULL THEN 'osm:height' WHEN lv_osm IS NOT NULL THEN 'osm:building:levels' WHEN h_ml IS NOT NULL THEN 'ml:h' END h_src,
  coalesce(lv_osm, greatest(1, floor((coalesce(h_osm, h_ml, 3.0)+0.5)/3.0)))::INT floors,
  CASE
    WHEN bt IN ('construction') THEN 'CON'
    WHEN bt IN ('ruins','collapsed','destroyed') THEN 'RUI'
    WHEN bt IN ('government','public','civic','townhall','police','fire_station','courthouse','military','barracks','embassy') OR amenity IN ('townhall','police','courthouse','fire_station') OR office='government' THEN 'GOV'
    WHEN bt IN ('school','college','university','kindergarten') OR amenity IN ('school','college','university','kindergarten') THEN 'EDU'
    WHEN bt IN ('hospital','clinic') OR amenity IN ('hospital','clinic','doctors','pharmacy','dentist') OR healthcare IS NOT NULL THEN 'HEA'
    WHEN bt IN ('church','cathedral','mosque','chapel','temple','religious','shrine','synagogue','monastery') OR amenity='place_of_worship' THEN 'REL'
    WHEN bt IN ('hotel','motel','hostel') OR tourism IN ('hotel','motel','guest_house','hostel') THEN 'HOS'
    WHEN bt IN ('industrial','factory','manufacture','storage_tank','silo','works') OR man_made IN ('storage_tank','works','silo') THEN 'IND'
    WHEN bt IN ('train_station','transportation','terminal','parking','hangar_airport') OR amenity IN ('bus_station','ferry_terminal') THEN 'TRA'
    WHEN bt IN ('farm','barn','cowshed','granary','greenhouse','farm_auxiliary','stable','sty','poultry_house') THEN 'AGR'
    WHEN bt IN ('retail','commercial','supermarket','kiosk','warehouse','office','bank','market','shop') OR shop IS NOT NULL OR office IS NOT NULL THEN 'COM'
    WHEN bt IN ('house','detached','semidetached_house','residential','apartments','bungalow','terrace','dormitory','hut','villa','cabin','static_caravan','houseboat','stilt_house') THEN 'RES'
    WHEN bt IN ('toilets','shed','garage','garages','kitchen','service','carport','roof','shelter','outbuilding','guardhouse') THEN 'ANX'
    WHEN govkind IS NOT NULL THEN 'GOV'
    WHEN regexp_matches(coalesce(pname,'') || ' ' || coalesce(oname,''), '{GOV_RE}') THEN 'GOV'
    WHEN category IN ('school') THEN 'EDU'
    WHEN category IN ('hospital','pharmacy') THEN 'HEA'
    WHEN category IN ('church','mosque') THEN 'REL'
    WHEN category IN ('hotel') THEN 'HOS'
    WHEN category IN ('police') THEN 'GOV'
    WHEN category IN ('petrol','motorpark','parking','charging') THEN 'TRA'
    WHEN category IS NOT NULL AND category <> 'attraction' THEN 'COM'
    WHEN area_m2 < 12 THEN 'ANX'
    WHEN circ > 0.88 AND area_m2 < {hut_max} THEN 'RES'
    WHEN area_m2 >= 1500 AND coalesce(lv_osm, floor((coalesce(h_osm, h_ml, 3.0)+0.5)/3.0)) <= 2 THEN 'COM'
    ELSE 'RES' END cls,
  CASE
    WHEN bt IS NOT NULL AND bt NOT IN ('yes') THEN 'osm:building'
    WHEN coalesce(amenity, shop, office, tourism, healthcare, man_made) IS NOT NULL THEN 'osm:tags'
    WHEN govkind IS NOT NULL THEN 'n-ways:compound'
    WHEN category IS NOT NULL THEN 'n-ways:place'
    WHEN area_m2 < 12 OR (circ > 0.88 AND area_m2 < {hut_max}) OR area_m2 >= 1500 THEN 'shape'
    ELSE 'default' END cls_src
FROM x;
ALTER TABLE prof ADD COLUMN sub VARCHAR; ALTER TABLE prof ADD COLUMN conf DOUBLE;
UPDATE prof SET conf = CASE cls_src WHEN 'osm:building' THEN 0.9 WHEN 'osm:tags' THEN 0.85 WHEN 'n-ways:place' THEN 0.7
                                     WHEN 'n-ways:compound' THEN 0.7 WHEN 'shape' THEN 0.5 ELSE 0.3 END;
UPDATE prof SET sub = CASE
    WHEN cls='RES' AND circ > 0.88 AND area_m2 < {hut_max} THEN 'round-house'
    WHEN cls='RES' AND floors >= 4 THEN 'apartment-block'
    WHEN cls='RES' AND area_m2 >= 250 THEN 'villa-or-large-house'
    WHEN cls='RES' AND area_m2 < 40 THEN 'small-house'
    WHEN cls='RES' THEN 'house'
    WHEN cls='COM' AND area_m2 >= 1500 THEN 'warehouse-or-hall'
    ELSE NULL END;
"""


def run(sql, json_out=False):
    cmd = ['duckdb', db] + (['-json'] if json_out else [])
    r = subprocess.run(cmd, input=sql, capture_output=True, text=True)
    if r.returncode != 0 or 'Error' in r.stderr:
        sys.exit(r.stderr[-4000:])
    return r.stdout


def q(sql):
    out = run(SETUP + sql, json_out=True).strip()
    # duckdb -json prints one array per statement; take the last
    parts = [p for p in out.split('\n]\n') if p.strip()]
    last = parts[-1] if parts else '[]'
    if not last.rstrip().endswith(']'):
        last += '\n]'
    return json.loads(last[last.index('['):])


def main():
    if 'skip-profile' not in os.environ.get('ANALYZE', ''):
        run(PROFILE)
    lv = ','.join(str(int(x)) for x in levels.split(','))
    # zone assignment
    run(f"""{SETUP}
    CREATE OR REPLACE TABLE zb AS
      SELECT a.level, a.osm, bm.id FROM bm JOIN admin a ON a.level IN ({lv}) AND ST_Intersects(a.g, ST_Point(bm.lon, bm.lat));
    CREATE OR REPLACE TABLE rb AS SELECT r.code, bm.id FROM bm JOIN regions r ON ST_Intersects(r.g, ST_Point(bm.lon, bm.lat));
    """)
    zones = q(f"""
      WITH c AS (SELECT zb.level, zb.osm, count(*) n, count(*) FILTER (WHERE b.src='osm') n_osm FROM zb JOIN b USING (id) GROUP BY ALL),
      reg AS (SELECT a.osm, any_value(r.code) region FROM admin a JOIN regions r ON ST_Intersects(r.g, ST_PointOnSurface(a.g)) WHERE a.level IN ({lv}) GROUP BY a.osm)
      SELECT a.level, a.osm, a."name", a.iso, reg.region,
             round(ST_Area_Spheroid(a.g)/1e6, 1) area_km2,
             round(ST_XMin(a.g),5) w, round(ST_YMin(a.g),5) s, round(ST_XMax(a.g),5) e, round(ST_YMax(a.g),5) n_,
             coalesce(c.n,0) buildings, coalesce(c.n_osm,0) buildings_osm
      FROM admin a LEFT JOIN c USING (level, osm) LEFT JOIN reg USING (osm) WHERE a.level IN ({lv}) ORDER BY a.level, region, a."name";
    """)
    json.dump(zones, open(f'{outdir}/zones.json', 'w'), ensure_ascii=False, indent=1)

    country = {}
    country['classMix'] = q("SELECT cls, count(*) n, round(100.0*count(*)/sum(count(*)) OVER (),2) pct FROM prof GROUP BY cls ORDER BY n DESC;")
    country['classSource'] = q("SELECT cls_src, count(*) n, round(100.0*count(*)/sum(count(*)) OVER (),2) pct FROM prof GROUP BY 1 ORDER BY n DESC;")
    country['heightSource'] = q("SELECT coalesce(h_src,'none') h_src, count(*) n, round(100.0*count(*)/sum(count(*)) OVER (),2) pct FROM prof GROUP BY 1 ORDER BY n DESC;")
    country['size'] = q("""SELECT count(*) n, round(quantile_cont(area_m2,0.1),1) a_p10, round(quantile_cont(area_m2,0.5),1) a_p50,
        round(quantile_cont(area_m2,0.9),1) a_p90, round(quantile_cont(area_m2,0.99),1) a_p99,
        round(quantile_cont(h_m,0.5),1) h_p50, round(quantile_cont(h_m,0.9),1) h_p90, round(sum(area_m2*floors)/1e6,2) floor_area_km2 FROM prof;""")
    country['roundHouses'] = q("SELECT count(*) n FROM prof WHERE sub='round-house';")
    country['byRegion'] = q("""SELECT rb.code, count(*) n, round(100.0*count(*) FILTER (WHERE sub='round-house')/count(*),1) round_pct,
        round(quantile_cont(area_m2,0.5),1) a_p50 FROM prof JOIN rb USING (id) GROUP BY 1 ORDER BY 1;""")
    country['enclosures'] = q("SELECT kind, count(*) n FROM barriers GROUP BY 1 ORDER BY 1;")
    country['nwCompounds'] = q("SELECT kind, count(*) n FROM nw_compounds GROUP BY 1 ORDER BY 1;")
    country['nwGates'] = q("SELECT kind, count(*) n FROM nw_gates GROUP BY 1 ORDER BY 1;")
    json.dump(country, open(f'{outdir}/country-profile.json', 'w'), ensure_ascii=False, indent=1)

    # capital: profile + compounds
    run(f"""{SETUP}
    CREATE OR REPLACE TABLE cap AS SELECT ST_Union_Agg(g) g FROM admin WHERE {capital};
    CREATE OR REPLACE TABLE cb AS SELECT p.*, b.g FROM prof p JOIN b USING (id) WHERE ST_Intersects((SELECT g FROM cap), ST_Point(p.lon, p.lat));
    CREATE OR REPLACE TABLE enc AS
      SELECT row_number() OVER () eid, kind, g, ST_Area(g)*110574*111320*cos(radians(ST_Y(ST_Centroid(g)))) area_m2
      FROM barriers WHERE kind LIKE 'enclosure:%' AND ST_Intersects((SELECT g FROM cap), g);
    DELETE FROM enc WHERE area_m2 < 40 OR area_m2 > 20000;
    -- each structure goes to the smallest enclosure holding its centroid
    CREATE OR REPLACE TABLE cb_enc AS
      SELECT cb.id, arg_min(enc.eid, enc.area_m2) eid FROM cb JOIN enc ON ST_Intersects(enc.g, ST_Point(cb.lon, cb.lat)) GROUP BY cb.id;
    -- unenclosed: an annex (< 40 m2) joins the nearest structure at least twice its size within 8 m
    CREATE OR REPLACE TABLE ub AS SELECT cb.* FROM cb LEFT JOIN cb_enc USING (id) WHERE cb_enc.id IS NULL;
    CREATE OR REPLACE TABLE ub_bin AS SELECT id, area_m2, g, floor(lon/0.0003)::BIGINT bx, floor(lat/0.0003)::BIGINT gy FROM ub;
    CREATE OR REPLACE TABLE annex AS
      WITH cand AS (
        SELECT a.id aid, m.id mid, ST_Distance(a.g, m.g)*111000 d
        FROM ub_bin a JOIN ub_bin m ON m.bx BETWEEN a.bx-1 AND a.bx+1 AND m.gy BETWEEN a.gy-1 AND a.gy+1
        WHERE a.area_m2 < 40 AND m.area_m2 >= 2*a.area_m2 AND a.id <> m.id)
      SELECT aid, arg_min(mid, d) mid FROM cand WHERE d <= 8 GROUP BY aid;
    -- compound id: enclosure, else annex's main structure, else itself
    CREATE OR REPLACE TABLE comp AS
      SELECT cb.id, CASE WHEN e.eid IS NOT NULL THEN 'E' || e.eid WHEN an.mid IS NOT NULL THEN 'B' || an.mid ELSE 'B' || cb.id END cid,
             CASE WHEN e.eid IS NOT NULL THEN 'enclosure' WHEN an.mid IS NOT NULL OR cb.id IN (SELECT mid FROM annex) THEN 'annex-cluster' ELSE 'single' END how
      FROM cb LEFT JOIN cb_enc e USING (id) LEFT JOIN annex an ON an.aid = cb.id;
    """)
    cap = {}
    cap['buildings'] = q("SELECT count(*) n, count(*) FILTER (WHERE src='osm') n_osm FROM cb;")
    cap['classMix'] = q("SELECT cls, count(*) n, round(100.0*count(*)/sum(count(*)) OVER (),2) pct, round(avg(conf),2) avg_conf FROM cb GROUP BY cls ORDER BY n DESC;")
    cap['resSub'] = q("SELECT sub, count(*) n, round(100.0*count(*)/sum(count(*)) OVER (),2) pct FROM cb WHERE cls='RES' GROUP BY 1 ORDER BY n DESC;")
    cap['classSource'] = q("SELECT cls_src, count(*) n, round(100.0*count(*)/sum(count(*)) OVER (),2) pct FROM cb GROUP BY 1 ORDER BY n DESC;")
    cap['size'] = q("""SELECT round(quantile_cont(area_m2,0.1),1) a_p10, round(quantile_cont(area_m2,0.25),1) a_p25, round(quantile_cont(area_m2,0.5),1) a_p50,
        round(quantile_cont(area_m2,0.75),1) a_p75, round(quantile_cont(area_m2,0.9),1) a_p90, round(quantile_cont(area_m2,0.99),1) a_p99,
        round(quantile_cont(perim_m,0.5),1) p_p50, round(quantile_cont(h_m,0.5),1) h_p50, round(quantile_cont(h_m,0.9),1) h_p90,
        round(sum(area_m2*floors)/1e6,2) floor_area_km2, round(sum(area_m2)/1e6,2) footprint_km2 FROM cb;""")
    cap['areaBands'] = q("""SELECT CASE WHEN area_m2<20 THEN 'a <20' WHEN area_m2<50 THEN 'b 20-50' WHEN area_m2<100 THEN 'c 50-100'
        WHEN area_m2<200 THEN 'd 100-200' WHEN area_m2<500 THEN 'e 200-500' WHEN area_m2<2000 THEN 'f 500-2000' ELSE 'g 2000+' END band,
        count(*) n, round(100.0*count(*)/sum(count(*)) OVER (),1) pct FROM cb GROUP BY 1 ORDER BY 1;""")
    cap['floors'] = q("SELECT least(floors,6) floors_cap6, count(*) n, round(100.0*count(*)/sum(count(*)) OVER (),1) pct FROM cb GROUP BY 1 ORDER BY 1;")
    cap['heightSource'] = q("SELECT coalesce(h_src,'none') h_src, count(*) n, round(100.0*count(*)/sum(count(*)) OVER (),1) pct FROM cb GROUP BY 1 ORDER BY n DESC;")
    cap['enclosures'] = q("SELECT count(*) n, round(quantile_cont(area_m2,0.5),0) plot_p50, round(quantile_cont(area_m2,0.9),0) plot_p90 FROM enc;")
    cap['grouping'] = q("SELECT how, count(*) structures, count(DISTINCT cid) compounds FROM comp GROUP BY 1 ORDER BY 1;")
    cap['compounds'] = q("""WITH c AS (SELECT cid, count(*) k FROM comp GROUP BY cid)
        SELECT count(*) compounds, sum(k) structures, round(avg(k),2) avg_structures,
               count(*) FILTER (WHERE k=1) k1, count(*) FILTER (WHERE k=2) k2, count(*) FILTER (WHERE k BETWEEN 3 AND 5) k3_5, count(*) FILTER (WHERE k>5) k6p FROM c;""")
    cap['enclosedStructures'] = q("""WITH c AS (SELECT cid, count(*) k FROM comp WHERE how='enclosure' GROUP BY cid)
        SELECT count(*) compounds, round(avg(k),2) avg_structures, max(k) max_structures,
               count(*) FILTER (WHERE k=1) k1, count(*) FILTER (WHERE k=2) k2, count(*) FILTER (WHERE k BETWEEN 3 AND 5) k3_5, count(*) FILTER (WHERE k>5) k6p FROM c;""")
    cap['enclosureGates'] = q("""SELECT count(DISTINCT e.eid) enclosures_with_gate FROM enc e JOIN barriers g ON g.kind='gate' AND ST_DWithin(ST_Boundary(e.g), g.g, 0.00003);""")
    cap['compoundUse'] = q("""WITH c AS (
          SELECT cid, count(*) k, count(*) FILTER (WHERE cls='RES' AND area_m2>=40) main_res, count(*) FILTER (WHERE cls='ANX' OR area_m2<40) small,
                 count(*) FILTER (WHERE cls IN ('COM','HOS')) com, count(*) FILTER (WHERE cls NOT IN ('RES','ANX','COM','HOS','UNK')) inst
          FROM comp JOIN cb USING (id) GROUP BY cid)
        SELECT CASE WHEN inst>0 THEN 'institutional' WHEN com>0 AND main_res>0 THEN 'mixed' WHEN com>0 THEN 'commercial'
                    WHEN main_res>=3 THEN 'multi-household (presumed)' WHEN main_res>=1 THEN 'one household (presumed)' ELSE 'outbuildings only' END AS use_class,
               count(*) n, round(100.0*count(*)/sum(count(*)) OVER (),1) pct FROM c GROUP BY 1 ORDER BY n DESC;""")
    cap['pois'] = q("SELECT count(*) n FROM cb WHERE category IS NOT NULL;")
    cap['nwCompounds'] = q("SELECT kind, count(*) n FROM nw_compounds WHERE ST_Intersects((SELECT g FROM cap), g) GROUP BY 1 ORDER BY 1;")
    json.dump(cap, open(f'{outdir}/capital-profile.json', 'w'), ensure_ascii=False, indent=1)
    print('ok', outdir)


main()
