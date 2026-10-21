# N-Ways Addressing for Guinea

**Status: issued on 20 October 2026.** Every compound in Guinea has an N-Ways code: 3,808,784 of them, in all five frames, provisional until residents confirm them in the N-Ways app. Guinea has no location postcode (its postal radicals route P.O. boxes) and, outside the street names of Kaloum, no address system, so these are N-Ways addresses, built to be handed to the state if it wants them. In Kaloum the official street name comes first.

A home's code is **the name of a place people already use plus a number said in pairs**:

| Remembered | Plate | Machine form | What it is |
|---|---|---|---|
| `Hafia 3 · 1230` | `HAFIA 3 · 1230` | `GN-04261-1230-8` | a compound in the quartier Hafia 3, Dixinn, Conakry |
| `Linsan 5389` | `LINSAN · 5389` | `GN-07134-5389-6` | a compound in Linsan, préfecture of Kindia |
| `Linsan 7031` | `LINSAN · 7031` | `GN-07134-7031-6` | a compound in the other Linsan, préfecture of Lélouma |
| `Almamiya 1939` | `ALMAMIYA · 1939` | `GN-00053-1939-4` | Kaloum: shown after its official street, Avenue Dinah Salifou |
| (a link) | | `0 22JV PVQQ` | any 3 m square, computed offline; `0 22JV` is its 1.2 km bloc |

The remembered form is unique in the whole country on its own. Every place with the same name shares one national number range (four digits, or five for the most shared names), split into frozen blocks, one per place, so no commune, préfecture or region is ever needed to tell two Linsans apart. No administrative boundary is part of any code, so Conakry's 13 communes and the 44 préfectures of 2026 change none.

The place is an official quartier where its outline exists, else the nearest named locality, in a short **plate name**: at most 12 characters and 2 words ("Kalouma 1260" for the hamlet whose official name is Missidé Bhoundou Kalouma; the official name still finds it). 746 places wait for their commune to choose a short name; their codes are issued with the provisional name, and the number never changes.

The border decides: a code is only ever issued for a building inside Guinea's national border (OpenStreetMap's admin_level 2 boundary) or within 300 m of it, whatever any frame or zone outline says ([SPEC §2.1](engine/SPEC.md)).

The model, the engine and the registry are Guinea's own, defined here for Guinea alone.

## What is where

| Path | Contents |
|---|---|
| [docs/paper.md](docs/paper.md), [paper.fr.md](docs/paper.fr.md) and the PDFs | the paper in English and French: background, data, the model with every formula and worked examples, implementation, evaluation, the designs considered, and the benefits for citizens, logistics, emergency services and government |
| [docs/paper/](docs/paper/), [docs/figures/](docs/figures/) | the paper's typesetting (pandoc template, styles, references in `references.bib`, `build.sh`) and its figures: TikZ sources, their data tables and the compiled PDF and SVG files |
| [docs/api.md](docs/api.md) | the registry API, endpoint by endpoint, with real requests and responses |
| [docs/existing-systems.md](docs/existing-systems.md) | what postal and address systems exist (no location postcode; Kaloum's streets named in 2024) |
| [docs/model.md](docs/model.md) | the reasons behind every rule, with the supporting measurements |
| [engine/SPEC.md](engine/SPEC.md) | the engine specification (normative) |
| [engine/reference/gn_codes.py](engine/reference/gn_codes.py), [plate_names.py](engine/reference/plate_names.py), [test-vectors.json](engine/reference/test-vectors.json), [vectors.json](engine/reference/vectors.json) | the reference engine (standard library only), the plate-name rule, its tests and the conformance vectors every implementation must reproduce |
| [engine/data/](engine/data/) | what a decoder ships: `register.json` (frames, every place with its plate name, official name, label, name key, national id and frozen blocks, the aliases), the frame and quartier outlines, and `border.geojson`, the national border that decides where a code may be issued |
| [registry/](registry/) | every issued code, one gzip CSV per frame (`CKY.csv.gz` Conakry, `BAS`, `MOY`, `HAU`, `FOR`), the frozen area table `areas.csv.gz` and `MANIFEST.json` (counts and SHA-256 of every file) |
| [server/](server/) | the registry server: a JSON API over the registry, ready to deploy with Docker or plain Python ([server/README.md](server/README.md), [openapi.yaml](server/openapi.yaml)) |
| [model/](model/) | `names.json` (the national name registry, frozen at first issue), `frames.json`, `building-stats.json` (the figures of the paper), `design.json`, `stats/` |
| [tools/](tools/) | the scripts that built the inputs, the compounds, the names and the registry ([tools/README.md](tools/README.md)) |
| [GOVERNANCE.md](GOVERNANCE.md), [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md) | who decides what, the one-issuer rule, how to propose a change and how to report a problem |
| [SOURCES.md](SOURCES.md), [LICENSING.md](LICENSING.md), [NOTICE](NOTICE), [CITATION.cff](CITATION.cff) | sources, licences, how to credit and how to cite the paper |

## The registry

`registry/` holds every issued code: 3,808,784 rows, one per compound, with nothing held back. Each row gives the machine form, the remembered and plate forms, the area, the official name and label, the number and its check digit, the status, the entrance and its kind, the spot code (SPEC §3) and Plus Code, the building profile (class, use, kind, structures, floor area, settlement) and, in Kaloum, the official street. `MANIFEST.json` gives the counts per frame and the SHA-256 of every file uncompressed; `python3 -m server import` checks them all.

## Run the server

```sh
docker compose up -d                                   # imports the registry on first start, then serves on :8080
curl -s 'http://localhost:8080/v1/find?q=Hafia%203%20%C2%B7%201230'
```

or, without Docker:

```sh
python3 -m server import --registry registry --db data/addresses.sqlite
python3 -m server serve --db data/addresses.sqlite --port 8080
python3 -m unittest discover -s server/tests -t .     # the server's tests
```

A deployment is read-only unless it is the country's designated issuer ([server/README.md](server/README.md#one-issuer)). The endpoints are in [docs/api.md](docs/api.md).

## Run the reference engine

```sh
python3 engine/reference/gn_codes.py test                        # vectors and check proofs
python3 engine/reference/gn_codes.py home Hafia 3 · 1230          # decode nationally: place, plate, machine form
python3 engine/reference/gn_codes.py home Linsan 7031             # the Linsan of Lélouma, not the one of Kindia
python3 engine/reference/gn_codes.py encode 9.5682034 -13.6544537 # spot code → 0 22JV PVQQ
python3 engine/reference/gn_codes.py bloc 9.5682034 -13.6544537   # → 0 22JV
python3 engine/reference/gn_codes.py decode "0 22JV PVQQ"
```

Python 3.9 or newer, no packages (see [requirements.txt](requirements.txt)).

## Build the paper

```sh
python3 tools/paper-figures.py   # the figures' data tables, from registry/ and model/ only
sh docs/paper/build.sh           # figures, then docs/paper.md and docs/paper.fr.md to PDF (pandoc 3, tectonic, pdftocairo)
```

The PDFs keep their names: `docs/n-ways-addressing-guinea-en.pdf` and `docs/n-ways-addressing-guinea-fr.pdf`.

## How the registry was made

```sh
python3 tools/prepare-inputs.py <work>                     # enclosures, gates, places, localities, quartiers, labels, Kaloum's streets
python3 tools/extract-buildings.py <work>                  # every footprint with its frame and area (DuckDB, 3 GB cap)
python3 tools/issue_registry.py group <work>               # compounds and profiles, one area at a time
python3 tools/build-register.py <work> --freeze            # plate names, national ranges, blocks
python3 tools/issue_registry.py number <work> <work>/lotes.jsonl.gz
python3 tools/vectors.py                                   # engine/reference/vectors.json
python3 tools/paper-stats.py <work> <work>/lotes.jsonl.gz  # model/building-stats.json
python3 tools/paper-figures.py                             # docs/figures/*.dat
```

The N-Ways issuer then issues the codes, checking every number against the reference's, and exports `registry/`. Since 20 October 2026 the register is frozen: a new run adds codes for new compounds and never renumbers an issued one.

## Licence and credit

Code (engine, server, tools): Apache License 2.0, with [NOTICE](NOTICE). Data (registry, model, engine data): ODbL 1.0. Documents: CC BY 4.0. Credit every use: **"N-Ways Addressing for Guinea, © N-WAYS LIMITED (nways.ng)"**, with a link to this repository ([LICENSING.md](LICENSING.md)). Derived from OpenStreetMap (© OpenStreetMap contributors, ODbL), Google Open Buildings (CC BY 4.0), Microsoft building footprints (ODbL) and GeoNames (CC BY 4.0).
