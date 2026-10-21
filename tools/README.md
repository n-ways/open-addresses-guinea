# Tools: Guinea's registry

All inputs are read-only:

- the N-Ways data folder (`NWAYS_ROOT`, holding `data/osm`, `data/detail`, `data/places` and `data/valhalla`): the OpenStreetMap building extract, the Google/Microsoft footprints, the routing compounds and gates, GeoNames;
- the N-Ways database (`NWAYS_DB`, default `postgres:///nmap?host=/tmp`): tables `regions` and `places`.

Run one heavy step at a time: DuckDB runs with `memory_limit='3GB'` and spills to the work folder, and the grouping reads the footprints one area at a time, so no step holds the 5 million footprints in memory.

## Issue

| Step | Script | Writes |
|---|---|---|
| 0 | `border.py build <extract.osm.pbf>` | `engine/data/border.geojson`, the national border (below); re-run when OpenStreetMap corrects it |
| 1 | osmium exports (below) | `admin`, `bar`, `place`, `hw`, `site` `.geojsonseq` in the work folder |
| 2 | `prepare-inputs.py <work>` | `enclosures.geojson`, `gates.csv`, `places.csv`, `localities.csv`, `quartiers.geojson`, `labels.geojson`, `streets.csv` |
| 3 | `extract-buildings.py <work>` | `buildings.csv` (every footprint with its frame, area, enclosure, label and Kaloum street, sorted by area), `enclosure-gates.csv`, `area-points.csv` |
| 4 | `issue_registry.py group <work>` | `compounds.jsonl.gz` (compounds and profiles, SPEC 5.1 and 6), `area-counts.json`, `group-stats.json`; nothing across the national border |
| 5 | `build-register.py <work> --freeze` | `model/names.json`, `engine/data/register.json`, `model/stats/national-names.json` (SPEC 4) |
| 6 | `issue_registry.py number <work> <work>/lotes.jsonl.gz` | the lotes, frame by frame, with the reference's numbers (SPEC 5.2) |
| 7 | the N-Ways backend: `homecodes issue -country GN -lotes <work>/lotes.jsonl.gz` | the codes, after checking every number against the reference's; then `homecodes export -country GN -out <dir>`, each file compressed with `gzip -n -9` into `registry/` (`MANIFEST.json` as written) |
| 7a | `border.py check` | the published codes whose entrance lies more than 300 m outside the border (below) |
| 7b | `name-stats.py` | `model/stats/national-names.json`, the name registry's summary counted on `registry/` |
| 8 | `vectors.py` | `engine/reference/vectors.json` (every port must reproduce it) |
| 9 | `paper-stats.py <work> <work>/lotes.jsonl.gz` | `model/building-stats.json` (the statistics of the paper); without `<work>/buildings.csv` the grouping check is kept from the previous file |
| 10 | `paper-figures.py` | `docs/figures/*.dat`, the data behind the paper's figures, from `registry/` and `model/` only |

`plates_gn.py` is Guinea's configuration of the plate-name rule (`engine/reference/plate_names.py`), used by `build-register.py`. `build-frames.py` built the five frozen frames (`model/frames.json`, `model/frames.geojson`) and is not run again. `build-design.py` writes `model/design.json`.

Since the first issue (20 October 2026) `build-register.py` keeps every frozen id, block and index and only adds; a later issue run keeps every code and only numbers new compounds.

### osmium exports

```
P=data/osm/guinea-latest.osm.pbf
osmium tags-filter -o gn-b.osm.pbf $P r/boundary=administrative
osmium export -a type,id -f geojsonseq --geometry-types=polygon -o admin.geojsonseq gn-b.osm.pbf
osmium tags-filter -o gn-bar.osm.pbf $P w/barrier=wall,fence,hedge,retaining_wall a/landuse=residential,farmyard n/barrier=gate,entrance,lift_gate,sliding_gate,swing_gate n/entrance
osmium export -a type,id -f geojsonseq -o bar.geojsonseq gn-bar.osm.pbf
osmium tags-filter -o gn-place.osm.pbf $P n/place=city,town,village,hamlet,suburb,quarter,neighbourhood,isolated_dwelling,locality
osmium export -a type,id -f geojsonseq -o place.geojsonseq gn-place.osm.pbf
osmium tags-filter -o gn-hw.osm.pbf $P w/highway
osmium export -a type,id -f geojsonseq --geometry-types=linestring -o hw.geojsonseq gn-hw.osm.pbf
osmium tags-filter -o gn-site.osm.pbf $P a/amenity=school,university,college,hospital,clinic,place_of_worship,marketplace,police,townhall,courthouse a/landuse=military,industrial,commercial,retail,religious
osmium export -a type,id -f geojsonseq --geometry-types=polygon -o site.geojsonseq gn-site.osm.pbf
```

## The border decides

A code is only ever issued for a building whose entrance lies inside the national border, OpenStreetMap's admin_level=2 boundary of Guinea (relation 192778), or within 300 m of it (engine/SPEC.md 2.1). The frame outlines, the 0.01° reach around them and outlines from any other source (geoBoundaries, GADM and the like) may cross the border; none of them decides.

`border.py build` filters the extract's admin_level=2 relations with osmium, has osmium assemble the one tagged `ISO3166-1=GN`, simplifies its rings by Douglas-Peucker at 5 m and writes `engine/data/border.geojson` (about 0.6 MB, coordinates to 1e-5 degrees). The extract must hold the relation whole: one clipped at the country's own outline may miss border ways, and the tool then stops. `data/osm/westafrica-admin.osm.pbf` (every administrative boundary of the region) always holds it; the Guinea extract of 20 October 2026 does too, and both give the same file. The file records the largest distance between the simplified line and the true one, measured both ways (`maxDeviationM`, 5.5 m), and the limit the engine applies, 300 m less that deviation rounded up (`limitM`, 294 m), so a point accepted is never more than 300 m outside the true border. `--full FILE` also writes the unsimplified border.

`issue_registry.py group` loads that border (`gn_codes.Border`) and drops every structure whose centre lies beyond it, then every compound whose centre (its entrance at issue) lies beyond it, before any place or number is given; `group-stats.json` counts them (`abroadStructure`, `abroadCompound`). The N-Ways issuer refuses any code more than 300 m outside the border, and the registry server refuses to issue a code or move an entrance there (`422 outside`).

`border.py check` streams `registry/` and counts the codes whose entrance lies beyond the border. With the shipped file it reports the codes certainly more than 300 m outside (beyond 300 m plus the deviation) and those it cannot settle (within the deviation of 300 m); with `--border FILE` and the unsimplified border it is exact.

## Design statistics (18 October 2026)

`stage.py`, `analyze.py`, `areas.py` and `areas-gn.py` produced the design-time statistics in `model/stats/` (zones, the building profile, Conakry's compounds, the first area counts). They are kept for the record; the issued figures are in `model/building-stats.json` and `model/stats/national-names.json`.
