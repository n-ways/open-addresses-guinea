# The registry API

This is the HTTP API of the registry server (`server/`, see [server/README.md](../server/README.md)), version `v1`. Every request and response below was made against a server holding the complete published registry of Guinea (3,808,784 codes); the responses are copied as they came, with long lists shortened (marked "… n more"). The host `addresses.example.gov.gn` stands for your deployment, which was started as the designated issuer with `ISSUE_PER_DAY=50`; `$ISSUE_KEY` stands for one of its `ISSUE_KEYS`. The machine-readable description is [server/openapi.yaml](../server/openapi.yaml).

## Conventions

- Every response is JSON (`application/json; charset=utf-8`) with stable field names. Coordinates are WGS 84 decimal degrees; outlines are rings of `[lng, lat]` pairs, as in GeoJSON.
- A **zone** is one of the five frames of the code and one registry file (`CKY.csv.gz` for Conakry, and `BAS`, `MOY`, `HAU`, `FOR`). An **area** is a named place that owns blocks of numbers (an official quartier or a locality); its reference, such as `0-00026`, is the `zone` column of the registry rows.
- A code card carries every registry column under its registry name (`machine`, `home`, `plate`, `zone`, `official_name`, `label`, `number`, `check`, `status`, `issued`, `issued_at`, `entrance_lat`, `entrance_lng`, `entrance_kind`, `spot`, `plus_code`, `class`, `use`, `kind`, `structures`, `floor_area_m2`, `settlement`, `official_street`), then the derived fields.
- People never see the check digit. It is part of the machine form only (`GN-04261-1230-8`); the remembered, written and plate forms carry the name and the number.
- Reading needs no key. Issuing and changing codes need `Authorization: Bearer <key>`, and only a deployment designated as the country's issuer has keys (see [server/README.md](../server/README.md#one-issuer)).

## Errors

Every error has the same shape and an HTTP status that says what kind of error it is:

```json
{"error": {"code": "check_mismatch", "message": "The check digit of GN-04261-1230-7 does not match: a digit is wrong or two are swapped."}}
```

| Status | `code` | Meaning |
|---|---|---|
| 400 | `bad_request`, `invalid_code`, `bad_json` | a parameter is missing or malformed; the text is not a code |
| 401 | `unauthorised` | no issuing key, or not a valid one |
| 403 | `read_only` | this deployment does not issue codes |
| 404 | `not_found`, `not_issued`, `no_code_here` | no such endpoint, name, zone or area; a valid code that was never issued; no compound at a spot |
| 405 | `method_not_allowed` | the path exists, the method does not |
| 409 | `exists`, `retired`, `area_full`, `conflict` | the building already has a code (returned in `existing`); the code is retired; the name has no numbers left; a concurrent issue |
| 410 | `retired` | `find` on a code that has been retired |
| 413 | `too_large` | a body over 64 KB |
| 422 | `check_mismatch`, `ambiguous`, `outside`, `bad_outline`, `too_far`, `bad_status`, `no_area` | the request is well formed but cannot be accepted |
| 429 | `rate_limited` | the key has reached its daily limit |
| 500 | `internal` | a fault in the server; the log has the details |

## Endpoints

A point is in Guinea when it lies inside a frame outline, or in no outline but within 0.01° of one (a sliver between outlines, a border village, an islet), which is also every point the spot-code rule gives a code (SPEC 2, 3.4); further out it is outside. This decides `outside` for `/v1/at`, `/v1/spot`, `POST /v1/codes` and a moved entrance (`PATCH`).

The border decides (SPEC 2.1): a point more than 300 m outside the national border, OpenStreetMap's admin_level=2 boundary of Guinea, is in a neighbouring country whatever the frame outlines say. `POST /v1/codes` and a moved entrance answer `422 outside` there, and `/v1/at` answers `outside` unless an issued code lies within 12 m. The server checks the border shipped in `engine/data/border.geojson`, simplified to within 5.5 m of the true line, with that deviation taken off the 300 m (294 m), so it accepts no point more than 300 m outside the true border. `/v1/spot` is not affected.

| Method and path | Purpose |
|---|---|
| [`GET /v1/health`](#get-v1health) | Liveness and the registry in use. |
| [`GET /v1/info`](#get-v1info) | The country, the five zones with their counts, the licences, the credit line and the engine specification. |
| [`GET /v1/codes/{machine}`](#get-v1codesmachine) | The full card of one code: every registry column under its registry name, the forms people use (remembered, written, plate, spoken), the place line, the bloc, the area and the zone. |
| [`GET /v1/find?q=`](#get-v1findq) | Resolves what a person types or says: a remembered or plate form in any case, spacing or accents ("hafia 3 12 30", "HAFIA 3 · 1230"), an official name in place of the plate name, a machine form, a spot code, or an official street address in Kaloum (alone, or followed by "· <home code>"). |
| [`GET /v1/at?lat=&lng=`](#get-v1atlatlng) | The code of the compound at a point. |
| [`GET /v1/near?lat=&lng=&radius=`](#get-v1nearlatlngradius) | The codes whose entrance lies within `radius` metres, nearest first. |
| [`GET /v1/verify?code=`](#get-v1verifycode) | Checks a machine form: its syntax, its check digit, whether it falls in a block of its name, and whether it is issued. |
| [`GET /v1/spot?lat=&lng=`](#get-v1spotlatlng) | The spot code of the 3 m cell holding a point, its bloc code (1.2 km) and the centre of the cell. |
| [`GET /v1/spot/decode?code=`](#get-v1spotdecodecode) | The centre of a spot code's cell. |
| [`GET /v1/zones`](#get-v1zones) | The five zones (the frames of the code: Conakry, Basse-Guinée, Moyenne-Guinée, Haute-Guinée, Guinée forestière), one registry file each. |
| [`GET /v1/zones/{key}`](#get-v1zoneskey) | One zone with its counts and every area in it. |
| [`GET /v1/zones/{key}/codes?after=&limit=`](#get-v1zoneskeycodesafterlimit) | Every code of a zone, in machine-form order, a page at a time. |
| [`GET /v1/areas/{id}`](#get-v1areasid) | One area: its plate and official names, its blocks of numbers, its counts and the other areas that share its name range. |
| [`GET /v1/areas?name=`](#get-v1areasname) | The areas with a plate name, or with an official name (directly or through an alias). |
| [`POST /v1/codes`](#post-v1codes) | Issues a code for a new compound, or for another door of a compound (`of`). |
| [`PATCH /v1/codes/{machine}`](#patch-v1codesmachine) | Changes the status of a code (`provisional`, `confirmed`, `retired`) or moves its entrance by at most 80 m. |

## `GET /v1/health`

Liveness and the registry in use. Use it for load-balancer and container health checks.

Request:

```sh
curl -s 'https://addresses.example.gov.gn/v1/health'
```

`200`

```json
{
  "status": "ok",
  "country": "GN",
  "codes": 3808784,
  "registry_exported": "2026-10-21T18:50:00Z",
  "issuing": true
}
```


## `GET /v1/info`

The country, the five zones with their counts, the licences, the credit line and the engine specification.

Request:

```sh
curl -s 'https://addresses.example.gov.gn/v1/info'
```

`200`

```json
{
  "country": "GN",
  "name": "Guinea",
  "codes": 3808784,
  "areas": 17044,
  "zones": [
    {
      "key": "CKY",
      "digit": 0,
      "name": "Conakry",
      "bbox": [
        -13.8403,
        9.4322,
        -13.4738,
        9.7534
      ],
      "codes": 258080,
      "areas": 228
    },
    {
      "key": "BAS",
      "digit": 1,
      "name": "Basse-Guinée",
      "bbox": [
        -15.3667,
        9.0341,
        -12.1101,
        12.6756
      ],
      "codes": 1003774,
      "areas": 4951
    },
    "… 3 more"
  ],
  "counts": {
    "provisional": 3808784,
    "confirmed": 0,
    "retired": 0
  },
  "registry_exported": "2026-10-21T18:50:00Z",
  "imported_at": "2026-10-21T19:27:04Z",
  "licences": {
    "code": "Apache-2.0",
    "data": "ODbL-1.0",
    "documents": "CC-BY-4.0"
  },
  "credit": "N-Ways Addressing for Guinea, © N-WAYS LIMITED (nways.ng)",
  "credit_url": "https://github.com/n-ways/open-addresses-guinea",
  "engine": {
    "spec": "SPEC v1.0",
    "reference": "engine/reference/gn_codes.py"
  },
  "issuing": {
    "enabled": true,
    "per_key_per_day": 50
  },
  "example": {
    "remembered": "Hafia 3 · 1230",
    "machine": "GN-04261-1230-8",
    "spot": "0 22JV PVQQ"
  }
}
```


## `GET /v1/codes/{machine}`

The full card of one code: every registry column under its registry name, the forms people use (remembered, written, plate, spoken), the place line, the bloc, the area and the zone. The check digit appears only in `machine` and `check`; plates and written forms never carry it.

| Parameter | In | |
|---|---|---|
| `machine` | path | machine form, e.g. `GN-04261-1230-8` (case and spaces ignored) |

A compound in Hafia 3, Dixinn:

```sh
curl -s 'https://addresses.example.gov.gn/v1/codes/GN-04261-1230-8'
```

`200`

```json
{
  "machine": "GN-04261-1230-8",
  "home": "Hafia 3 · 1230",
  "plate": "HAFIA 3 · 1230",
  "zone": "0-00026",
  "official_name": "Hafia 3",
  "label": "Dixinn",
  "number": 1230,
  "check": 8,
  "status": "provisional",
  "issued": "bulk",
  "issued_at": "2026-10-20T12:12:34Z",
  "entrance_lat": 9.5682034,
  "entrance_lng": -13.6544537,
  "entrance_kind": "centre",
  "spot": "0 22JV PVQQ",
  "plus_code": "6CX8H89W+76M",
  "class": "residential.house",
  "use": "residential",
  "kind": "compound",
  "structures": 2,
  "floor_area_m2": 206.4,
  "settlement": "town",
  "official_street": "",
  "country": "GN",
  "forms": {
    "remembered": "Hafia 3 · 1230",
    "written": "Hafia 3 · 1230",
    "plate": "HAFIA 3 · 1230",
    "spoken": "Hafia 3, douze trente",
    "machine": "GN-04261-1230-8"
  },
  "place": "Dixinn, Conakry",
  "full_line": "Hafia 3 · 1230 · Dixinn, Conakry",
  "bloc": "0 22JV",
  "area": {
    "zone": "0-00026",
    "area_id": "osm:relation/5582738",
    "plate_name": "Hafia 3",
    "official_name": "Hafia 3",
    "kind": "quartier",
    "label": "Dixinn",
    "place": "Dixinn, Conakry",
    "frame": "CKY",
    "name_id": 4261,
    "name_needs_council_choice": false,
    "codes": 645
  },
  "frame": {
    "key": "CKY",
    "digit": 0,
    "name": "Conakry",
    "bbox": [
      -13.8403,
      9.4322,
      -13.4738,
      9.7534
    ]
  },
  "registry_file": "CKY.csv.gz",
  "credit": "N-Ways Addressing for Guinea, © N-WAYS LIMITED (nways.ng)"
}
```

A compound in Kaloum, where the official street comes first (`official_address`):

```sh
curl -s 'https://addresses.example.gov.gn/v1/codes/GN-00053-1939-4'
```

`200`

```json
{
  "machine": "GN-00053-1939-4",
  "home": "Almamiya 1939",
  "plate": "ALMAMIYA · 1939",
  "zone": "0-00208",
  "official_name": "Almamiya",
  "label": "Kaloum",
  "number": 1939,
  "check": 4,
  "status": "provisional",
  "issued": "bulk",
  "issued_at": "2026-10-20T12:12:28Z",
  "entrance_lat": 9.5102034,
  "entrance_lng": -13.7118986,
  "entrance_kind": "centre",
  "spot": "0 229J 9JRM",
  "plus_code": "6CX8G76Q+36Q",
  "class": "residential.house",
  "use": "residential",
  "kind": "building",
  "structures": 1,
  "floor_area_m2": 299.1,
  "settlement": "town",
  "official_street": "Avenue Dinah Salifou, Kaloum",
  "country": "GN",
  "forms": {
    "remembered": "Almamiya 1939",
    "written": "Almamiya · 1939",
    "plate": "ALMAMIYA · 1939",
    "spoken": "Almamiya, dix-neuf trente-neuf",
    "machine": "GN-00053-1939-4"
  },
  "place": "Kaloum, Conakry",
  "full_line": "Almamiya 1939 · Kaloum, Conakry",
  "bloc": "0 229J",
  "area": {
    "zone": "0-00208",
    "area_id": "osm:node/5551459713",
    "plate_name": "Almamiya",
    "official_name": "Almamiya",
    "kind": "locality",
    "label": "Kaloum",
    "place": "Kaloum, Conakry",
    "frame": "CKY",
    "name_id": 53,
    "name_needs_council_choice": false,
    "codes": 917
  },
  "frame": {
    "key": "CKY",
    "digit": 0,
    "name": "Conakry",
    "bbox": [
      -13.8403,
      9.4322,
      -13.4738,
      9.7534
    ]
  },
  "registry_file": "CKY.csv.gz",
  "credit": "N-Ways Addressing for Guinea, © N-WAYS LIMITED (nways.ng)",
  "official_address": "Avenue Dinah Salifou, Kaloum"
}
```

A wrong check digit is refused, never corrected:

```sh
curl -s 'https://addresses.example.gov.gn/v1/codes/GN-04261-1230-7'
```

`422`

```json
{
  "error": {
    "code": "check_mismatch",
    "message": "The check digit of GN-04261-1230-7 does not match: a digit is wrong or two are swapped."
  }
}
```

A well-formed code that was never issued:

```sh
curl -s 'https://addresses.example.gov.gn/v1/codes/GN-04261-1231-9'
```

`404`

```json
{
  "error": {
    "code": "not_issued",
    "message": "GN-04261-1231-9 is a valid machine form, but no such code has been issued."
  }
}
```

Not a machine form:

```sh
curl -s 'https://addresses.example.gov.gn/v1/codes/HAFIA-1230'
```

`400`

```json
{
  "error": {
    "code": "invalid_code",
    "message": "'HAFIA-1230' is not a machine form (GN-NNNNN-NNNN-C)."
  }
}
```


## `GET /v1/find?q=`

Resolves what a person types or says: a remembered or plate form in any case, spacing or accents ("hafia 3 12 30", "HAFIA 3 · 1230"), an official name in place of the plate name, a machine form, a spot code, or an official street address in Kaloum (alone, or followed by "· <home code>"). Text after a comma is context and is ignored for home codes.

| Parameter | In | |
|---|---|---|
| `q` | query | the text, at most 200 characters |
| `limit` | query | for a street address, the number of codes returned (1–50, default 20) |

Typed in pairs, lower case:

```sh
curl -s 'https://addresses.example.gov.gn/v1/find?q=hafia%203%2012%2030'
```

`200`

```json
{
  "query": "hafia 3 12 30",
  "kind": "remembered",
  "count": 1,
  "total": 1,
  "truncated": false,
  "matches": [
    {
      "machine": "GN-04261-1230-8",
      "home": "Hafia 3 · 1230",
      "plate": "HAFIA 3 · 1230",
      "zone": "0-00026",
      "official_name": "Hafia 3",
      "label": "Dixinn",
      "number": 1230,
      "check": 8,
      "status": "provisional",
      "issued": "bulk",
      "issued_at": "2026-10-20T12:12:34Z",
      "entrance_lat": 9.5682034,
      "entrance_lng": -13.6544537,
      "entrance_kind": "centre",
      "spot": "0 22JV PVQQ",
      "plus_code": "6CX8H89W+76M",
      "class": "residential.house",
      "use": "residential",
      "kind": "compound",
      "structures": 2,
      "floor_area_m2": 206.4,
      "settlement": "town",
      "official_street": "",
      "country": "GN",
      "forms": {
        "remembered": "Hafia 3 · 1230",
        "written": "Hafia 3 · 1230",
        "plate": "HAFIA 3 · 1230",
        "spoken": "Hafia 3, douze trente",
        "machine": "GN-04261-1230-8"
      },
      "place": "Dixinn, Conakry",
      "full_line": "Hafia 3 · 1230 · Dixinn, Conakry",
      "bloc": "0 22JV",
      "area": {
        "zone": "0-00026",
        "area_id": "osm:relation/5582738",
        "plate_name": "Hafia 3",
        "official_name": "Hafia 3",
        "kind": "quartier",
        "label": "Dixinn",
        "place": "Dixinn, Conakry",
        "frame": "CKY",
        "name_id": 4261,
        "name_needs_council_choice": false,
        "codes": 645
      },
      "frame": {
        "key": "CKY",
        "digit": 0,
        "name": "Conakry",
        "bbox": [
          -13.8403,
          9.4322,
          -13.4738,
          9.7534
        ]
      },
      "registry_file": "CKY.csv.gz",
      "credit": "N-Ways Addressing for Guinea, © N-WAYS LIMITED (nways.ng)"
    }
  ]
}
```

Two places share the name Linsan; the number alone says which one:

```sh
curl -s 'https://addresses.example.gov.gn/v1/find?q=Linsan%207031'
```

`200`

```json
{
  "query": "Linsan 7031",
  "kind": "remembered",
  "count": 1,
  "total": 1,
  "truncated": false,
  "matches": [
    {
      "machine": "GN-07134-7031-6",
      "home": "Linsan 7031",
      "plate": "LINSAN · 7031",
      "zone": "2-06747",
      "official_name": "Linsan",
      "label": "Lelouma",
      "number": 7031,
      "check": 6,
      "status": "provisional",
      "issued": "bulk",
      "issued_at": "2026-10-20T12:18:14Z",
      "entrance_lat": 11.7683558,
      "entrance_lng": -12.6816439,
      "entrance_kind": "centre",
      "spot": "2 C3PC X3R9",
      "plus_code": "7C39Q899+88X",
      "class": "residential.house",
      "use": "residential",
      "kind": "building",
      "structures": 1,
      "floor_area_m2": 32.6,
      "settlement": "rural",
      "official_street": "",
      "country": "GN",
      "forms": {
        "remembered": "Linsan 7031",
        "written": "Linsan · 7031",
        "plate": "LINSAN · 7031",
        "spoken": "Linsan, soixante-dix trente et un",
        "machine": "GN-07134-7031-6"
      },
      "place": "Lelouma",
      "full_line": "Linsan 7031 · Lelouma",
      "bloc": "2 C3PC",
      "area": {
        "zone": "2-06747",
        "area_id": "geonames:2418118",
        "plate_name": "Linsan",
        "official_name": "Linsan",
        "kind": "locality",
        "label": "Lelouma",
        "place": "Lelouma",
        "frame": "MOY",
        "name_id": 7134,
        "name_needs_council_choice": false,
        "codes": 591
      },
      "frame": {
        "key": "MOY",
        "digit": 2,
        "name": "Moyenne-Guinée",
        "bbox": [
          -12.9821,
          9.8723,
          -11.0508,
          12.4526
        ]
      },
      "registry_file": "MOY.csv.gz",
      "credit": "N-Ways Addressing for Guinea, © N-WAYS LIMITED (nways.ng)"
    }
  ]
}
```

The official name typed instead of the plate name:

```sh
curl -s 'https://addresses.example.gov.gn/v1/find?q=Missid%C3%A9%20Bhoundou%20Kalouma%201260'
```

`200`

```json
{
  "query": "Missidé Bhoundou Kalouma 1260",
  "kind": "remembered",
  "count": 1,
  "total": 1,
  "truncated": false,
  "matches": [
    {
      "machine": "GN-04730-1260-1",
      "home": "Kalouma 1260",
      "plate": "KALOUMA · 1260",
      "zone": "1-04049",
      "official_name": "Missidé Bhoundou Kalouma",
      "label": "Télimélé",
      "number": 1260,
      "check": 1,
      "status": "provisional",
      "issued": "bulk",
      "issued_at": "2026-10-20T12:14:08Z",
      "entrance_lat": 11.0046058,
      "entrance_lng": -13.5925833,
      "entrance_kind": "centre",
      "spot": "1 FC43 2X84",
      "plus_code": "7C382C34+RXV",
      "class": "residential.house",
      "use": "residential",
      "kind": "compound",
      "structures": 3,
      "floor_area_m2": 142.6,
      "settlement": "town",
      "official_street": "",
      "country": "GN",
      "forms": {
        "remembered": "Kalouma 1260",
        "written": "Kalouma · 1260",
        "plate": "KALOUMA · 1260",
        "spoken": "Kalouma, douze soixante",
        "machine": "GN-04730-1260-1"
      },
      "place": "Télimélé",
      "full_line": "Kalouma 1260 · Télimélé",
      "bloc": "1 FC43",
      "area": {
        "zone": "1-04049",
        "area_id": "osm:node/5402630185",
        "plate_name": "Kalouma",
        "official_name": "Missidé Bhoundou Kalouma",
        "kind": "locality",
        "label": "Télimélé",
        "place": "Télimélé",
        "frame": "BAS",
        "name_id": 4730,
        "name_needs_council_choice": false,
        "codes": 70
      },
      "frame": {
        "key": "BAS",
        "digit": 1,
        "name": "Basse-Guinée",
        "bbox": [
          -15.3667,
          9.0341,
          -12.1101,
          12.6756
        ]
      },
      "registry_file": "BAS.csv.gz",
      "credit": "N-Ways Addressing for Guinea, © N-WAYS LIMITED (nways.ng)"
    }
  ]
}
```

A spot code on a compound:

```sh
curl -s 'https://addresses.example.gov.gn/v1/find?q=0%2022JV%20PVQQ'
```

`200`

```json
{
  "query": "0 22JV PVQQ",
  "kind": "spot",
  "count": 1,
  "total": 1,
  "truncated": false,
  "matches": [
    {
      "machine": "GN-04261-1230-8",
      "home": "Hafia 3 · 1230",
      "plate": "HAFIA 3 · 1230",
      "zone": "0-00026",
      "official_name": "Hafia 3",
      "label": "Dixinn",
      "number": 1230,
      "check": 8,
      "status": "provisional",
      "issued": "bulk",
      "issued_at": "2026-10-20T12:12:34Z",
      "entrance_lat": 9.5682034,
      "entrance_lng": -13.6544537,
      "entrance_kind": "centre",
      "spot": "0 22JV PVQQ",
      "plus_code": "6CX8H89W+76M",
      "class": "residential.house",
      "use": "residential",
      "kind": "compound",
      "structures": 2,
      "floor_area_m2": 206.4,
      "settlement": "town",
      "official_street": "",
      "country": "GN",
      "forms": {
        "remembered": "Hafia 3 · 1230",
        "written": "Hafia 3 · 1230",
        "plate": "HAFIA 3 · 1230",
        "spoken": "Hafia 3, douze trente",
        "machine": "GN-04261-1230-8"
      },
      "place": "Dixinn, Conakry",
      "full_line": "Hafia 3 · 1230 · Dixinn, Conakry",
      "bloc": "0 22JV",
      "area": {
        "zone": "0-00026",
        "area_id": "osm:relation/5582738",
        "plate_name": "Hafia 3",
        "official_name": "Hafia 3",
        "kind": "quartier",
        "label": "Dixinn",
        "place": "Dixinn, Conakry",
        "frame": "CKY",
        "name_id": 4261,
        "name_needs_council_choice": false,
        "codes": 645
      },
      "frame": {
        "key": "CKY",
        "digit": 0,
        "name": "Conakry",
        "bbox": [
          -13.8403,
          9.4322,
          -13.4738,
          9.7534
        ]
      },
      "registry_file": "CKY.csv.gz",
      "credit": "N-Ways Addressing for Guinea, © N-WAYS LIMITED (nways.ng)",
      "distance_m": 0.8
    }
  ]
}
```

An official street address (Kaloum):

```sh
curl -s 'https://addresses.example.gov.gn/v1/find?q=Avenue%20Dinah%20Salifou%2C%20Kaloum&limit=2'
```

`200`

```json
{
  "query": "Avenue Dinah Salifou, Kaloum",
  "kind": "official_address",
  "count": 2,
  "total": 32,
  "truncated": true,
  "matches": [
    {
      "machine": "GN-00053-1630-9",
      "home": "Almamiya 1630",
      "plate": "ALMAMIYA · 1630",
      "zone": "0-00208",
      "official_name": "Almamiya",
      "label": "Kaloum",
      "number": 1630,
      "check": 9,
      "status": "provisional",
      "issued": "bulk",
      "issued_at": "2026-10-20T12:12:28Z",
      "entrance_lat": 9.5122752,
      "entrance_lng": -13.7111065,
      "entrance_kind": "centre",
      "spot": "0 229J HPM4",
      "plus_code": "6CX8G76Q+WH6",
      "class": "residential.house",
      "use": "residential",
      "kind": "building",
      "structures": 1,
      "floor_area_m2": 61.8,
      "settlement": "town",
      "official_street": "Avenue Dinah Salifou, Kaloum",
      "country": "GN",
      "forms": {
        "remembered": "Almamiya 1630",
        "written": "Almamiya · 1630",
        "plate": "ALMAMIYA · 1630",
        "spoken": "Almamiya, seize trente",
        "machine": "GN-00053-1630-9"
      },
      "place": "Kaloum, Conakry",
      "full_line": "Almamiya 1630 · Kaloum, Conakry",
      "bloc": "0 229J",
      "area": {
        "zone": "0-00208",
        "area_id": "osm:node/5551459713",
        "plate_name": "Almamiya",
        "official_name": "Almamiya",
        "kind": "locality",
        "label": "Kaloum",
        "place": "Kaloum, Conakry",
        "frame": "CKY",
        "name_id": 53,
        "name_needs_council_choice": false,
        "codes": 917
      },
      "frame": {
        "key": "CKY",
        "digit": 0,
        "name": "Conakry",
        "bbox": [
          -13.8403,
          9.4322,
          -13.4738,
          9.7534
        ]
      },
      "registry_file": "CKY.csv.gz",
      "credit": "N-Ways Addressing for Guinea, © N-WAYS LIMITED (nways.ng)",
      "official_address": "Avenue Dinah Salifou, Kaloum"
    },
    {
      "machine": "GN-00053-1634-6",
      "home": "Almamiya 1634",
      "plate": "ALMAMIYA · 1634",
      "zone": "0-00208",
      "official_name": "Almamiya",
      "label": "Kaloum",
      "number": 1634,
      "check": 6,
      "status": "provisional",
      "issued": "bulk",
      "issued_at": "2026-10-20T12:12:28Z",
      "entrance_lat": 9.5123227,
      "entrance_lng": -13.711217,
      "entrance_kind": "centre",
      "spot": "0 229J HMQW",
      "plus_code": "6CX8G76Q+WGF",
      "class": "residential.house",
      "use": "residential",
      "kind": "building",
      "structures": 1,
      "floor_area_m2": 49.4,
      "settlement": "town",
      "official_street": "Avenue Dinah Salifou, Kaloum",
      "country": "GN",
      "forms": {
        "remembered": "Almamiya 1634",
        "written": "Almamiya · 1634",
        "plate": "ALMAMIYA · 1634",
        "spoken": "Almamiya, seize trente-quatre",
        "machine": "GN-00053-1634-6"
      },
      "place": "Kaloum, Conakry",
      "full_line": "Almamiya 1634 · Kaloum, Conakry",
      "bloc": "0 229J",
      "area": {
        "zone": "0-00208",
        "area_id": "osm:node/5551459713",
        "plate_name": "Almamiya",
        "official_name": "Almamiya",
        "kind": "locality",
        "label": "Kaloum",
        "place": "Kaloum, Conakry",
        "frame": "CKY",
        "name_id": 53,
        "name_needs_council_choice": false,
        "codes": 917
      },
      "frame": {
        "key": "CKY",
        "digit": 0,
        "name": "Conakry",
        "bbox": [
          -13.8403,
          9.4322,
          -13.4738,
          9.7534
        ]
      },
      "registry_file": "CKY.csv.gz",
      "credit": "N-Ways Addressing for Guinea, © N-WAYS LIMITED (nways.ng)",
      "official_address": "Avenue Dinah Salifou, Kaloum"
    }
  ]
}
```

A street with the home code after it:

```sh
curl -s 'https://addresses.example.gov.gn/v1/find?q=Avenue%20Dinah%20Salifou%20%C2%B7%20Almamiya%201939'
```

`200`

```json
{
  "query": "Avenue Dinah Salifou · Almamiya 1939",
  "kind": "official_address",
  "count": 1,
  "total": 1,
  "truncated": false,
  "matches": [
    {
      "machine": "GN-00053-1939-4",
      "home": "Almamiya 1939",
      "plate": "ALMAMIYA · 1939",
      "zone": "0-00208",
      "official_name": "Almamiya",
      "label": "Kaloum",
      "number": 1939,
      "check": 4,
      "status": "provisional",
      "issued": "bulk",
      "issued_at": "2026-10-20T12:12:28Z",
      "entrance_lat": 9.5102034,
      "entrance_lng": -13.7118986,
      "entrance_kind": "centre",
      "spot": "0 229J 9JRM",
      "plus_code": "6CX8G76Q+36Q",
      "class": "residential.house",
      "use": "residential",
      "kind": "building",
      "structures": 1,
      "floor_area_m2": 299.1,
      "settlement": "town",
      "official_street": "Avenue Dinah Salifou, Kaloum",
      "country": "GN",
      "forms": {
        "remembered": "Almamiya 1939",
        "written": "Almamiya · 1939",
        "plate": "ALMAMIYA · 1939",
        "spoken": "Almamiya, dix-neuf trente-neuf",
        "machine": "GN-00053-1939-4"
      },
      "place": "Kaloum, Conakry",
      "full_line": "Almamiya 1939 · Kaloum, Conakry",
      "bloc": "0 229J",
      "area": {
        "zone": "0-00208",
        "area_id": "osm:node/5551459713",
        "plate_name": "Almamiya",
        "official_name": "Almamiya",
        "kind": "locality",
        "label": "Kaloum",
        "place": "Kaloum, Conakry",
        "frame": "CKY",
        "name_id": 53,
        "name_needs_council_choice": false,
        "codes": 917
      },
      "frame": {
        "key": "CKY",
        "digit": 0,
        "name": "Conakry",
        "bbox": [
          -13.8403,
          9.4322,
          -13.4738,
          9.7534
        ]
      },
      "registry_file": "CKY.csv.gz",
      "credit": "N-Ways Addressing for Guinea, © N-WAYS LIMITED (nways.ng)",
      "official_address": "Avenue Dinah Salifou, Kaloum"
    }
  ]
}
```

A machine form with a wrong check digit:

```sh
curl -s 'https://addresses.example.gov.gn/v1/find?q=GN-04261-1230-7'
```

`422`

```json
{
  "error": {
    "code": "check_mismatch",
    "message": "The check digit of GN-04261-1230-7 does not match: a digit is wrong or two are swapped."
  }
}
```

A number inside a block that has not been issued:

```sh
curl -s 'https://addresses.example.gov.gn/v1/find?q=Hafia%203%20%C2%B7%201231'
```

`404`

```json
{
  "error": {
    "code": "not_issued",
    "message": "No compound has Hafia 3 · 1231 yet: the number lies in the block of Hafia 3 (Dixinn, Conakry) but has not been issued.",
    "zone": "0-00026"
  }
}
```

A name that is not in the register:

```sh
curl -s 'https://addresses.example.gov.gn/v1/find?q=Atlantis%201230'
```

`404`

```json
{
  "error": {
    "code": "not_found",
    "message": "No code matches 'Atlantis 1230': no area of that name in Guinea."
  }
}
```

A name with no number:

```sh
curl -s 'https://addresses.example.gov.gn/v1/find?q=Hafia'
```

`400`

```json
{
  "error": {
    "code": "invalid_code",
    "message": "A home code is a place name followed by 4 or 5 digits, such as \"Hafia 3 · 1230\"."
  }
}
```

No query:

```sh
curl -s 'https://addresses.example.gov.gn/v1/find'
```

`400`

```json
{
  "error": {
    "code": "bad_request",
    "message": "The q parameter is required: a home code, a machine form, an official address or a spot code."
  }
}
```


## `GET /v1/at?lat=&lng=`

The code of the compound at a point. `found` when an issued entrance lies within 12 m (or the point is inside an outline drawn when a code was issued here); otherwise `none`, with the area a new compound at this point would take. Points outside Guinea return `outside`: in no frame outline and more than 0.01° from one, or more than 300 m outside the national border with no issued code within 12 m (SPEC 2.1). A point in no frame outline but within 0.01° of one, and within the border, is in Guinea and is found or takes a code like any other.

| Parameter | In | |
|---|---|---|
| `lat` | query | latitude, WGS 84 |
| `lng` | query | longitude, WGS 84 |

On a compound:

```sh
curl -s 'https://addresses.example.gov.gn/v1/at?lat=9.5682034&lng=-13.6544537'
```

`200`

```json
{
  "status": "found",
  "lat": 9.5682034,
  "lng": -13.6544537,
  "frame": {
    "key": "CKY",
    "digit": 0,
    "name": "Conakry",
    "bbox": [
      -13.8403,
      9.4322,
      -13.4738,
      9.7534
    ]
  },
  "area": {
    "zone": "0-00026",
    "area_id": "osm:relation/5582738",
    "plate_name": "Hafia 3",
    "official_name": "Hafia 3",
    "kind": "quartier",
    "label": "Dixinn",
    "place": "Dixinn, Conakry",
    "frame": "CKY",
    "name_id": 4261,
    "name_needs_council_choice": false,
    "codes": 645
  },
  "distance_m": 0.0,
  "code": {
    "machine": "GN-04261-1230-8",
    "home": "Hafia 3 · 1230",
    "plate": "HAFIA 3 · 1230",
    "zone": "0-00026",
    "official_name": "Hafia 3",
    "label": "Dixinn",
    "number": 1230,
    "check": 8,
    "status": "provisional",
    "issued": "bulk",
    "issued_at": "2026-10-20T12:12:34Z",
    "entrance_lat": 9.5682034,
    "entrance_lng": -13.6544537,
    "entrance_kind": "centre",
    "spot": "0 22JV PVQQ",
    "plus_code": "6CX8H89W+76M",
    "class": "residential.house",
    "use": "residential",
    "kind": "compound",
    "structures": 2,
    "floor_area_m2": 206.4,
    "settlement": "town",
    "official_street": "",
    "country": "GN",
    "forms": {
      "remembered": "Hafia 3 · 1230",
      "written": "Hafia 3 · 1230",
      "plate": "HAFIA 3 · 1230",
      "spoken": "Hafia 3, douze trente",
      "machine": "GN-04261-1230-8"
    },
    "place": "Dixinn, Conakry",
    "full_line": "Hafia 3 · 1230 · Dixinn, Conakry",
    "bloc": "0 22JV",
    "area": {
      "zone": "0-00026",
      "area_id": "osm:relation/5582738",
      "plate_name": "Hafia 3",
      "official_name": "Hafia 3",
      "kind": "quartier",
      "label": "Dixinn",
      "place": "Dixinn, Conakry",
      "frame": "CKY",
      "name_id": 4261,
      "name_needs_council_choice": false,
      "codes": 645
    },
    "frame": {
      "key": "CKY",
      "digit": 0,
      "name": "Conakry",
      "bbox": [
        -13.8403,
        9.4322,
        -13.4738,
        9.7534
      ]
    },
    "registry_file": "CKY.csv.gz",
    "credit": "N-Ways Addressing for Guinea, © N-WAYS LIMITED (nways.ng)"
  }
}
```

Between compounds:

```sh
curl -s 'https://addresses.example.gov.gn/v1/at?lat=9.5605&lng=-13.6591'
```

`200`

```json
{
  "status": "none",
  "lat": 9.5605,
  "lng": -13.6591,
  "frame": {
    "key": "CKY",
    "digit": 0,
    "name": "Conakry",
    "bbox": [
      -13.8403,
      9.4322,
      -13.4738,
      9.7534
    ]
  },
  "area": {
    "zone": "0-00062",
    "area_id": "osm:relation/5582736",
    "plate_name": "Hafia 1",
    "official_name": "Hafia 1",
    "kind": "quartier",
    "label": "Dixinn",
    "place": "Dixinn, Conakry",
    "frame": "CKY",
    "name_id": 4259,
    "name_needs_council_choice": false,
    "codes": 909
  },
  "message": "No issued compound within 12 m of this point."
}
```

At sea:

```sh
curl -s 'https://addresses.example.gov.gn/v1/at?lat=9.2000&lng=-14.3000'
```

`200`

```json
{
  "status": "outside",
  "lat": 9.2,
  "lng": -14.3,
  "message": "This point is outside Guinea."
}
```

In a neighbouring country, 1 km beyond the national border, though inside Guinée forestière's frame outline (SPEC 2.1):

```sh
curl -s 'https://addresses.example.gov.gn/v1/at?lat=8.5308106&lng=-10.6295492'
```

`200`

```json
{
  "status": "outside",
  "lat": 8.5308106,
  "lng": -10.6295492,
  "message": "This point is outside Guinea."
}
```

A missing parameter:

```sh
curl -s 'https://addresses.example.gov.gn/v1/at?lat=9.5605'
```

`400`

```json
{
  "error": {
    "code": "bad_request",
    "message": "The lng parameter is required."
  }
}
```


## `GET /v1/near?lat=&lng=&radius=`

The codes whose entrance lies within `radius` metres, nearest first.

| Parameter | In | |
|---|---|---|
| `lat, lng` | query | the point |
| `radius` | query | metres, 1–500 (default 100) |
| `limit` | query | at most this many codes, 1–100 (default 20) |

Request:

```sh
curl -s 'https://addresses.example.gov.gn/v1/near?lat=9.5682034&lng=-13.6544537&radius=25&limit=3'
```

`200`

```json
{
  "lat": 9.5682034,
  "lng": -13.6544537,
  "radius_m": 25.0,
  "count": 3,
  "total": 8,
  "codes": [
    {
      "machine": "GN-04261-1230-8",
      "home": "Hafia 3 · 1230",
      "plate": "HAFIA 3 · 1230",
      "zone": "0-00026",
      "status": "provisional",
      "entrance_lat": 9.5682034,
      "entrance_lng": -13.6544537,
      "entrance_kind": "centre",
      "use": "residential",
      "distance_m": 0.0
    },
    {
      "machine": "GN-04261-1184-2",
      "home": "Hafia 3 · 1184",
      "plate": "HAFIA 3 · 1184",
      "zone": "0-00026",
      "status": "provisional",
      "entrance_lat": 9.5682328,
      "entrance_lng": -13.6546042,
      "entrance_kind": "centre",
      "use": "residential",
      "distance_m": 16.8
    },
    {
      "machine": "GN-04261-1232-4",
      "home": "Hafia 3 · 1232",
      "plate": "HAFIA 3 · 1232",
      "zone": "0-00026",
      "status": "provisional",
      "entrance_lat": 9.5680508,
      "entrance_lng": -13.6544428,
      "entrance_kind": "centre",
      "use": "residential",
      "distance_m": 17.0
    }
  ]
}
```

A radius over 500 m:

```sh
curl -s 'https://addresses.example.gov.gn/v1/near?lat=9.5682034&lng=-13.6544537&radius=900'
```

`400`

```json
{
  "error": {
    "code": "bad_request",
    "message": "radius must be between 1 and 500."
  }
}
```


## `GET /v1/verify?code=`

Checks a machine form: its syntax, its check digit, whether it falls in a block of its name, and whether it is issued. Always `200` when `code` is given; `valid` is true only for an issued code that is not retired.

| Parameter | In | |
|---|---|---|
| `code` | query | the machine form |

An issued code:

```sh
curl -s 'https://addresses.example.gov.gn/v1/verify?code=GN-04261-1230-8'
```

`200`

```json
{
  "code": "GN-04261-1230-8",
  "machine": "GN-04261-1230-8",
  "syntax_ok": true,
  "check_ok": true,
  "issued": true,
  "in_block_of": "0-00026",
  "valid": true,
  "status": "provisional",
  "home": "Hafia 3 · 1230"
}
```

Two digits swapped:

```sh
curl -s 'https://addresses.example.gov.gn/v1/verify?code=GN-04261-1320-8'
```

`200`

```json
{
  "code": "GN-04261-1320-8",
  "machine": "GN-04261-1320-8",
  "syntax_ok": true,
  "check_ok": false,
  "issued": false,
  "valid": false,
  "reason": "the check digit does not match: a digit is wrong or two are swapped",
  "expected_check": 5
}
```

Well formed but not issued:

```sh
curl -s 'https://addresses.example.gov.gn/v1/verify?code=GN-04261-1231-9'
```

`200`

```json
{
  "code": "GN-04261-1231-9",
  "machine": "GN-04261-1231-9",
  "syntax_ok": true,
  "check_ok": true,
  "issued": false,
  "in_block_of": "0-00026",
  "valid": false,
  "reason": "well formed, but not issued"
}
```

Without a code:

```sh
curl -s 'https://addresses.example.gov.gn/v1/verify'
```

`400`

```json
{
  "error": {
    "code": "bad_request",
    "message": "The code parameter is required."
  }
}
```


## `GET /v1/spot?lat=&lng=`

The spot code of the 3 m cell holding a point, its bloc code (1.2 km) and the centre of the cell. Computed from the coordinates alone; works where nothing is built.

`edge` is `true` for a point just beyond its frame's grid, outside every frame outline and within 0.01° of it (no issued compound lies there): the code then names the grid's nearest edge cell, and `cell` is that cell's centre, not the point (SPEC 3.4).

| Parameter | In | |
|---|---|---|
| `lat, lng` | query | the point |

Request:

```sh
curl -s 'https://addresses.example.gov.gn/v1/spot?lat=9.5682034&lng=-13.6544537'
```

`200`

```json
{
  "spot": "0 22JV PVQQ",
  "bloc": "0 22JV",
  "frame": {
    "key": "CKY",
    "digit": 0,
    "name": "Conakry",
    "bbox": [
      -13.8403,
      9.4322,
      -13.4738,
      9.7534
    ]
  },
  "lat": 9.5682034,
  "lng": -13.6544537,
  "cell": {
    "lat": 9.5682079,
    "lng": -13.6544482,
    "size_m": 3.0
  },
  "edge": false
}
```

Beyond a frame's grid: a point in no outline but within 0.01° of Basse-Guinée's, south of that frame's grid, takes the grid's nearest edge cell, whose centre is 274 m away:

```sh
curl -s 'https://addresses.example.gov.gn/v1/spot?lat=9.0275327&lng=-13.2964538'
```

`200`

```json
{
  "spot": "1 2F2C 2W2Q",
  "bloc": "1 2F2C",
  "frame": {
    "key": "BAS",
    "digit": 1,
    "name": "Basse-Guinée",
    "bbox": [
      -15.3667,
      9.0341,
      -12.1101,
      12.6756
    ]
  },
  "lat": 9.0275327,
  "lng": -13.2964538,
  "cell": {
    "lat": 9.0300136,
    "lng": -13.2964541,
    "size_m": 3.0
  },
  "edge": true
}
```

Outside Guinea:

```sh
curl -s 'https://addresses.example.gov.gn/v1/spot?lat=9.2000&lng=-14.3000'
```

`422`

```json
{
  "error": {
    "code": "outside",
    "message": "This point is outside Guinea: it has no spot code."
  }
}
```


## `GET /v1/spot/decode?code=`

The centre of a spot code's cell. Accepts any spacing and case; an older code that ends in a check character is verified.

| Parameter | In | |
|---|---|---|
| `code` | query | the spot code |

Request:

```sh
curl -s 'https://addresses.example.gov.gn/v1/spot/decode?code=0%2022JV%20PVQQ'
```

`200`

```json
{
  "code": "0 22JV PVQQ",
  "bloc": "0 22JV",
  "frame": {
    "key": "CKY",
    "digit": 0,
    "name": "Conakry",
    "bbox": [
      -13.8403,
      9.4322,
      -13.4738,
      9.7534
    ]
  },
  "lat": 9.5682079,
  "lng": -13.6544482,
  "size_m": 3.0
}
```

A character outside the code alphabet:

```sh
curl -s 'https://addresses.example.gov.gn/v1/spot/decode?code=0%2022JV%20PVQ0'
```

`400`

```json
{
  "error": {
    "code": "invalid_code",
    "message": "Character '0' is not in the code alphabet."
  }
}
```


## `GET /v1/zones`

The five zones (the frames of the code: Conakry, Basse-Guinée, Moyenne-Guinée, Haute-Guinée, Guinée forestière), one registry file each.

Request:

```sh
curl -s 'https://addresses.example.gov.gn/v1/zones'
```

`200`

```json
{
  "count": 5,
  "zones": [
    {
      "key": "CKY",
      "digit": 0,
      "name": "Conakry",
      "bbox": [
        -13.8403,
        9.4322,
        -13.4738,
        9.7534
      ],
      "areas": 228,
      "codes": 258080,
      "registry_file": "CKY.csv.gz"
    },
    {
      "key": "BAS",
      "digit": 1,
      "name": "Basse-Guinée",
      "bbox": [
        -15.3667,
        9.0341,
        -12.1101,
        12.6756
      ],
      "areas": 4951,
      "codes": 1003774,
      "registry_file": "BAS.csv.gz"
    },
    "… 3 more"
  ]
}
```


## `GET /v1/zones/{key}`

One zone with its counts and every area in it.

| Parameter | In | |
|---|---|---|
| `key` | path | `CKY`, `BAS`, `MOY`, `HAU` or `FOR` |

Request (the list of 228 areas is shortened here):

```sh
curl -s 'https://addresses.example.gov.gn/v1/zones/CKY'
```

`200`

```json
{
  "key": "CKY",
  "digit": 0,
  "name": "Conakry",
  "bbox": [
    -13.8403,
    9.4322,
    -13.4738,
    9.7534
  ],
  "counts": {
    "provisional": 258080,
    "confirmed": 0,
    "retired": 0,
    "total": 258080
  },
  "registry_file": "CKY.csv.gz",
  "areas": [
    {
      "zone": "0-00001",
      "area_id": "geonames:2593088",
      "plate_name": "Donka",
      "official_name": "Donka",
      "kind": "locality",
      "label": "Dixinn",
      "place": "Dixinn, Conakry",
      "frame": "CKY",
      "name_id": 2643,
      "name_needs_council_choice": false,
      "codes": 0
    },
    {
      "zone": "0-00002",
      "area_id": "osm:relation/5582729",
      "plate_name": "Camayenne",
      "official_name": "Camayenne",
      "kind": "quartier",
      "label": "Dixinn",
      "place": "Dixinn, Conakry",
      "frame": "CKY",
      "name_id": 1596,
      "name_needs_council_choice": false,
      "codes": 1412
    },
    "… 226 more"
  ]
}
```

An unknown zone:

```sh
curl -s 'https://addresses.example.gov.gn/v1/zones/XYZ'
```

`404`

```json
{
  "error": {
    "code": "not_found",
    "message": "No zone 'XYZ'. The zones are BAS, CKY, FOR, HAU, MOY."
  }
}
```


## `GET /v1/zones/{key}/codes?after=&limit=`

Every code of a zone, in machine-form order, a page at a time. Pass the `next` value of a page as `after` to get the following one; `next` is null on the last page.

| Parameter | In | |
|---|---|---|
| `key` | path | the zone |
| `after` | query | the last machine form of the previous page |
| `limit` | query | 1–1000 (default 100) |

The first page:

```sh
curl -s 'https://addresses.example.gov.gn/v1/zones/CKY/codes?limit=2'
```

`200`

```json
{
  "zone": "CKY",
  "after": null,
  "count": 2,
  "next": "GN-00023-1003-9",
  "codes": [
    {
      "machine": "GN-00023-1001-8",
      "home": "Airport 1001",
      "plate": "AIRPORT · 1001",
      "zone": "0-00094",
      "official_name": "Airport",
      "label": "Conakry",
      "number": 1001,
      "check": 8,
      "status": "provisional",
      "issued": "bulk",
      "issued_at": "2026-10-20T12:12:28Z",
      "entrance_lat": 9.5669,
      "entrance_lng": -13.6266895,
      "entrance_kind": "centre",
      "spot": "0 23J2 JC9H",
      "plus_code": "6CX8H98F+Q87",
      "class": "residential.house",
      "use": "residential",
      "kind": "building",
      "structures": 1,
      "floor_area_m2": 63.2,
      "settlement": "rural",
      "official_street": ""
    },
    {
      "machine": "GN-00023-1003-9",
      "home": "Airport 1003",
      "plate": "AIRPORT · 1003",
      "zone": "0-00094",
      "official_name": "Airport",
      "label": "Conakry",
      "number": 1003,
      "check": 9,
      "status": "provisional",
      "issued": "bulk",
      "issued_at": "2026-10-20T12:12:28Z",
      "entrance_lat": 9.5667691,
      "entrance_lng": -13.6276181,
      "entrance_kind": "centre",
      "spot": "0 23J2 J84V",
      "plus_code": "6CX8H98C+PX2",
      "class": "residential.house",
      "use": "residential",
      "kind": "building",
      "structures": 1,
      "floor_area_m2": 61.5,
      "settlement": "rural",
      "official_street": ""
    }
  ]
}
```

The next page:

```sh
curl -s 'https://addresses.example.gov.gn/v1/zones/CKY/codes?limit=2&after=GN-00023-1003-9'
```

`200`

```json
{
  "zone": "CKY",
  "after": "GN-00023-1003-9",
  "count": 2,
  "next": "GN-00023-1007-1",
  "codes": [
    {
      "machine": "GN-00023-1005-2",
      "home": "Airport 1005",
      "plate": "AIRPORT · 1005",
      "zone": "0-00094",
      "official_name": "Airport",
      "label": "Conakry",
      "number": 1005,
      "check": 2,
      "status": "provisional",
      "issued": "bulk",
      "issued_at": "2026-10-20T12:12:28Z",
      "entrance_lat": 9.5671036,
      "entrance_lng": -13.6275168,
      "entrance_kind": "centre",
      "spot": "0 23J2 J9P2",
      "plus_code": "6CX8H98C+RXX",
      "class": "residential.house",
      "use": "residential",
      "kind": "compound",
      "structures": 2,
      "floor_area_m2": 51.3,
      "settlement": "rural",
      "official_street": ""
    },
    {
      "machine": "GN-00023-1007-1",
      "home": "Airport 1007",
      "plate": "AIRPORT · 1007",
      "zone": "0-00094",
      "official_name": "Airport",
      "label": "Conakry",
      "number": 1007,
      "check": 1,
      "status": "provisional",
      "issued": "bulk",
      "issued_at": "2026-10-20T12:12:28Z",
      "entrance_lat": 9.5677237,
      "entrance_lng": -13.6274275,
      "entrance_kind": "centre",
      "spot": "0 23J2 M9V6",
      "plus_code": "6CX8H99F+32P",
      "class": "residential.house",
      "use": "residential",
      "kind": "building",
      "structures": 1,
      "floor_area_m2": 109.0,
      "settlement": "rural",
      "official_street": ""
    }
  ]
}
```


## `GET /v1/areas/{id}`

One area: its plate and official names, its blocks of numbers, its counts and the other areas that share its name range.

| Parameter | In | |
|---|---|---|
| `id` | path | the area reference, `<zone digit>-<5 digits>`, as in the registry's `zone` column |

Request:

```sh
curl -s 'https://addresses.example.gov.gn/v1/areas/0-00026'
```

`200`

```json
{
  "zone": "0-00026",
  "area_id": "osm:relation/5582738",
  "plate_name": "Hafia 3",
  "official_name": "Hafia 3",
  "kind": "quartier",
  "label": "Dixinn",
  "place": "Dixinn, Conakry",
  "frame": "CKY",
  "name_id": 4261,
  "name_needs_council_choice": false,
  "codes": 645,
  "index": 26,
  "name_key": "hafia 3",
  "lat": 9.568214,
  "lon": -13.654443,
  "blocks": [
    {
      "lo": 1000,
      "hi": 2299,
      "size": 1300
    }
  ],
  "counts": {
    "provisional": 645,
    "confirmed": 0,
    "retired": 0,
    "total": 645
  },
  "numbers": {
    "in_blocks": 1300,
    "free": 655
  },
  "same_name": []
}
```

An unknown area:

```sh
curl -s 'https://addresses.example.gov.gn/v1/areas/7-00001'
```

`404`

```json
{
  "error": {
    "code": "not_found",
    "message": "No area '7-00001'. An area is written <frame digit>-<5 digits>, such as 0-00094."
  }
}
```


## `GET /v1/areas?name=`

The areas with a plate name, or with an official name (directly or through an alias).

| Parameter | In | |
|---|---|---|
| `name` | query | a plate name or an official name |

A shared plate name:

```sh
curl -s 'https://addresses.example.gov.gn/v1/areas?name=Linsan'
```

`200`

```json
{
  "name": "Linsan",
  "matched_by": "plate name",
  "count": 2,
  "areas": [
    {
      "zone": "1-01421",
      "area_id": "osm:node/1750704667",
      "plate_name": "Linsan",
      "official_name": "Linsan",
      "kind": "locality",
      "label": "Kindia",
      "place": "Kindia",
      "frame": "BAS",
      "name_id": 7134,
      "name_needs_council_choice": false,
      "codes": 2707
    },
    {
      "zone": "2-06747",
      "area_id": "geonames:2418118",
      "plate_name": "Linsan",
      "official_name": "Linsan",
      "kind": "locality",
      "label": "Lelouma",
      "place": "Lelouma",
      "frame": "MOY",
      "name_id": 7134,
      "name_needs_council_choice": false,
      "codes": 591
    }
  ]
}
```

An official name:

```sh
curl -s 'https://addresses.example.gov.gn/v1/areas?name=Missid%C3%A9%20Bhoundou%20Kalouma'
```

`200`

```json
{
  "name": "Missidé Bhoundou Kalouma",
  "matched_by": "alias",
  "count": 1,
  "areas": [
    {
      "zone": "1-04049",
      "area_id": "osm:node/5402630185",
      "plate_name": "Kalouma",
      "official_name": "Missidé Bhoundou Kalouma",
      "kind": "locality",
      "label": "Télimélé",
      "place": "Télimélé",
      "frame": "BAS",
      "name_id": 4730,
      "name_needs_council_choice": false,
      "codes": 70
    }
  ]
}
```

Without a name:

```sh
curl -s 'https://addresses.example.gov.gn/v1/areas'
```

`400`

```json
{
  "error": {
    "code": "bad_request",
    "message": "The name parameter is required: a plate name or an official name."
  }
}
```


## `POST /v1/codes`

Issues a code for a new compound, or for another door of a compound (`of`). Requires an issuing key. The rules are those of the N-Ways issuer: a point within 3 m of an issued compound, or an outline over one, already has its code (`409 exists`, with that code); the point must be in Guinea (inside a frame outline, or within 0.01° of one) and not more than 300 m outside the national border (SPEC 2.1), else `422 outside`; an outline is 6 m² to 2 ha; the area is the official quartier holding the point, else the nearest locality; the number is the free number nearest the middle of the gap between its neighbours on the area's Hilbert curve, else an extension block at the name's next free number. New codes are `provisional`, `issued: on-demand`. Each key may issue `ISSUE_PER_DAY` codes in any 24 hours.

| Parameter | In | |
|---|---|---|
| `lat, lng` | body | the entrance of the compound |
| `outline` | body | optional: the building, a ring of `[lng, lat]` pairs |
| `of` | body | optional: the machine form of the compound this is another door of (within 80 m) |

A new compound with its outline (`201`):

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 9.5605, "lng": -13.6591, "outline": [[-13.6591366, 9.5604548], [-13.6590634, 9.5604548], [-13.6590634, 9.5605452], [-13.6591366, 9.5605452]]}' 'https://addresses.example.gov.gn/v1/codes'
```

`201`

```json
{
  "machine": "GN-04259-2905-7",
  "home": "Hafia 1 · 2905",
  "plate": "HAFIA 1 · 2905",
  "zone": "0-00062",
  "official_name": "Hafia 1",
  "label": "Dixinn",
  "number": 2905,
  "check": 7,
  "status": "provisional",
  "issued": "on-demand",
  "issued_at": "2026-10-21T19:27:31Z",
  "entrance_lat": 9.5605,
  "entrance_lng": -13.6591,
  "entrance_kind": "centre",
  "spot": "0 22JV 2FH7",
  "plus_code": "6CX8H86R+692",
  "class": "residential.house",
  "use": "residential",
  "kind": "building",
  "structures": 1,
  "floor_area_m2": 80.3,
  "settlement": "",
  "official_street": "",
  "country": "GN",
  "forms": {
    "remembered": "Hafia 1 · 2905",
    "written": "Hafia 1 · 2905",
    "plate": "HAFIA 1 · 2905",
    "spoken": "Hafia 1, vingt-neuf zéro cinq",
    "machine": "GN-04259-2905-7"
  },
  "place": "Dixinn, Conakry",
  "full_line": "Hafia 1 · 2905 · Dixinn, Conakry",
  "bloc": "0 22JV",
  "area": {
    "zone": "0-00062",
    "area_id": "osm:relation/5582736",
    "plate_name": "Hafia 1",
    "official_name": "Hafia 1",
    "kind": "quartier",
    "label": "Dixinn",
    "place": "Dixinn, Conakry",
    "frame": "CKY",
    "name_id": 4259,
    "name_needs_council_choice": false,
    "codes": 910
  },
  "frame": {
    "key": "CKY",
    "digit": 0,
    "name": "Conakry",
    "bbox": [
      -13.8403,
      9.4322,
      -13.4738,
      9.7534
    ]
  },
  "registry_file": "CKY.csv.gz",
  "credit": "N-Ways Addressing for Guinea, © N-WAYS LIMITED (nways.ng)"
}
```

The same building again:

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 9.5605, "lng": -13.65909}' 'https://addresses.example.gov.gn/v1/codes'
```

`409`

```json
{
  "error": {
    "code": "exists",
    "message": "This building already has its code: Hafia 1 · 2905.",
    "existing": {
      "machine": "GN-04259-2905-7",
      "home": "Hafia 1 · 2905",
      "plate": "HAFIA 1 · 2905",
      "zone": "0-00062",
      "official_name": "Hafia 1",
      "label": "Dixinn",
      "number": 2905,
      "check": 7,
      "status": "provisional",
      "issued": "on-demand",
      "issued_at": "2026-10-21T19:27:31Z",
      "entrance_lat": 9.5605,
      "entrance_lng": -13.6591,
      "entrance_kind": "centre",
      "spot": "0 22JV 2FH7",
      "plus_code": "6CX8H86R+692",
      "class": "residential.house",
      "use": "residential",
      "kind": "building",
      "structures": 1,
      "floor_area_m2": 80.3,
      "settlement": "",
      "official_street": "",
      "country": "GN",
      "forms": {
        "remembered": "Hafia 1 · 2905",
        "written": "Hafia 1 · 2905",
        "plate": "HAFIA 1 · 2905",
        "spoken": "Hafia 1, vingt-neuf zéro cinq",
        "machine": "GN-04259-2905-7"
      },
      "place": "Dixinn, Conakry",
      "full_line": "Hafia 1 · 2905 · Dixinn, Conakry",
      "bloc": "0 22JV",
      "area": {
        "zone": "0-00062",
        "area_id": "osm:relation/5582736",
        "plate_name": "Hafia 1",
        "official_name": "Hafia 1",
        "kind": "quartier",
        "label": "Dixinn",
        "place": "Dixinn, Conakry",
        "frame": "CKY",
        "name_id": 4259,
        "name_needs_council_choice": false,
        "codes": 910
      },
      "frame": {
        "key": "CKY",
        "digit": 0,
        "name": "Conakry",
        "bbox": [
          -13.8403,
          9.4322,
          -13.4738,
          9.7534
        ]
      },
      "registry_file": "CKY.csv.gz",
      "credit": "N-Ways Addressing for Guinea, © N-WAYS LIMITED (nways.ng)"
    }
  }
}
```

Another door of it:

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 9.5606085, "lng": -13.6591, "of": "GN-04259-2905-7"}' 'https://addresses.example.gov.gn/v1/codes'
```

`201`

```json
{
  "machine": "GN-04259-2150-8",
  "home": "Hafia 1 · 2150",
  "plate": "HAFIA 1 · 2150",
  "zone": "0-00062",
  "official_name": "Hafia 1",
  "label": "Dixinn",
  "number": 2150,
  "check": 8,
  "status": "provisional",
  "issued": "on-demand",
  "issued_at": "2026-10-21T19:27:31Z",
  "entrance_lat": 9.5606085,
  "entrance_lng": -13.6591,
  "entrance_kind": "door",
  "spot": "0 22JV 2FQ7",
  "plus_code": "6CX8H86R+69R",
  "class": "",
  "use": "residential",
  "kind": "door",
  "structures": 0,
  "floor_area_m2": 0.0,
  "settlement": "",
  "official_street": "",
  "country": "GN",
  "forms": {
    "remembered": "Hafia 1 · 2150",
    "written": "Hafia 1 · 2150",
    "plate": "HAFIA 1 · 2150",
    "spoken": "Hafia 1, vingt et un cinquante",
    "machine": "GN-04259-2150-8"
  },
  "place": "Dixinn, Conakry",
  "full_line": "Hafia 1 · 2150 · Dixinn, Conakry",
  "bloc": "0 22JV",
  "area": {
    "zone": "0-00062",
    "area_id": "osm:relation/5582736",
    "plate_name": "Hafia 1",
    "official_name": "Hafia 1",
    "kind": "quartier",
    "label": "Dixinn",
    "place": "Dixinn, Conakry",
    "frame": "CKY",
    "name_id": 4259,
    "name_needs_council_choice": false,
    "codes": 911
  },
  "frame": {
    "key": "CKY",
    "digit": 0,
    "name": "Conakry",
    "bbox": [
      -13.8403,
      9.4322,
      -13.4738,
      9.7534
    ]
  },
  "registry_file": "CKY.csv.gz",
  "credit": "N-Ways Addressing for Guinea, © N-WAYS LIMITED (nways.ng)"
}
```

A door too far from its compound:

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 9.5625, "lng": -13.6591, "of": "GN-04259-2905-7"}' 'https://addresses.example.gov.gn/v1/codes'
```

`422`

```json
{
  "error": {
    "code": "too_far",
    "message": "That door is more than 80 m from Hafia 1 · 2905."
  }
}
```

A door for a code whose check digit is wrong is refused, never guessed:

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 9.5606085, "lng": -13.6591, "of": "GN-04259-2905-6"}' 'https://addresses.example.gov.gn/v1/codes'
```

`422`

```json
{
  "error": {
    "code": "check_mismatch",
    "message": "The check digit of GN-04259-2905-6 does not match: a digit is wrong or two are swapped."
  }
}
```

An outline too small to be a home:

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 9.5612, "lng": -13.658, "outline": [[-13.658, 9.5612], [-13.65799, 9.5612], [-13.65799, 9.56121]]}' 'https://addresses.example.gov.gn/v1/codes'
```

`422`

```json
{
  "error": {
    "code": "bad_outline",
    "message": "That outline is 1 m², but a home's is between 6 m² and 2 ha."
  }
}
```

A point outside Guinea:

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 9.2, "lng": -14.3}' 'https://addresses.example.gov.gn/v1/codes'
```

`422`

```json
{
  "error": {
    "code": "outside",
    "message": "That point is outside Guinea, so it cannot have a code."
  }
}
```

A point in a neighbouring country, 1 km beyond the national border though inside a frame outline, is outside too (SPEC 2.1):

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 8.5308106, "lng": -10.6295492}' 'https://addresses.example.gov.gn/v1/codes'
```

`422`

```json
{
  "error": {
    "code": "outside",
    "message": "That point is outside Guinea, so it cannot have a code."
  }
}
```

Without a key:

```sh
curl -s -X POST -H 'Content-Type: application/json' -d '{"lat": 9.5605, "lng": -13.6591}' 'https://addresses.example.gov.gn/v1/codes'
```

`401`

```json
{
  "error": {
    "code": "unauthorised",
    "message": "Send the issuing key as \"Authorization: Bearer <key>\"."
  }
}
```

On a read-only deployment (no `ISSUE_KEYS`):

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 9.5605, "lng": -13.6591}' 'https://addresses.example.gov.gn/v1/codes'
```

`403`

```json
{
  "error": {
    "code": "read_only",
    "message": "This deployment is read-only: it has not been designated to issue codes."
  }
}
```

Over the daily limit of the key (this request was made on a deployment started with `ISSUE_PER_DAY=2`):

```sh
curl -s -X POST -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"lat": 9.562, "lng": -13.66}' 'https://addresses.example.gov.gn/v1/codes'
```

`429`

```json
{
  "error": {
    "code": "rate_limited",
    "message": "This key has issued 2 codes in the last 24 hours, its limit. Try again later."
  }
}
```


## `PATCH /v1/codes/{machine}`

Changes the status of a code (`provisional`, `confirmed`, `retired`) or moves its entrance by at most 80 m, to a point in Guinea (inside a frame outline, or within 0.01° of one, and not more than 300 m outside the national border; else `422 outside`). A retired code never changes again and its number is never reused. Requires an issuing key; every change is kept in the `changes` table of the database.

| Parameter | In | |
|---|---|---|
| `status` | body | optional: the new status |
| `entrance` | body | optional: `{"lat", "lng", "kind"}`, kind one of gate, door, shopfront, landing, service, centre (default gate) |

Confirm a code:

```sh
curl -s -X PATCH -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"status": "confirmed"}' 'https://addresses.example.gov.gn/v1/codes/GN-04259-2905-7'
```

`200`

```json
{
  "machine": "GN-04259-2905-7",
  "home": "Hafia 1 · 2905",
  "plate": "HAFIA 1 · 2905",
  "zone": "0-00062",
  "official_name": "Hafia 1",
  "label": "Dixinn",
  "number": 2905,
  "check": 7,
  "status": "confirmed",
  "issued": "on-demand",
  "issued_at": "2026-10-21T19:27:31Z",
  "entrance_lat": 9.5605,
  "entrance_lng": -13.6591,
  "entrance_kind": "centre",
  "spot": "0 22JV 2FH7",
  "plus_code": "6CX8H86R+692",
  "class": "residential.house",
  "use": "residential",
  "kind": "building",
  "structures": 1,
  "floor_area_m2": 80.3,
  "settlement": "",
  "official_street": "",
  "country": "GN",
  "forms": {
    "remembered": "Hafia 1 · 2905",
    "written": "Hafia 1 · 2905",
    "plate": "HAFIA 1 · 2905",
    "spoken": "Hafia 1, vingt-neuf zéro cinq",
    "machine": "GN-04259-2905-7"
  },
  "place": "Dixinn, Conakry",
  "full_line": "Hafia 1 · 2905 · Dixinn, Conakry",
  "bloc": "0 22JV",
  "area": {
    "zone": "0-00062",
    "area_id": "osm:relation/5582736",
    "plate_name": "Hafia 1",
    "official_name": "Hafia 1",
    "kind": "quartier",
    "label": "Dixinn",
    "place": "Dixinn, Conakry",
    "frame": "CKY",
    "name_id": 4259,
    "name_needs_council_choice": false,
    "codes": 911
  },
  "frame": {
    "key": "CKY",
    "digit": 0,
    "name": "Conakry",
    "bbox": [
      -13.8403,
      9.4322,
      -13.4738,
      9.7534
    ]
  },
  "registry_file": "CKY.csv.gz",
  "credit": "N-Ways Addressing for Guinea, © N-WAYS LIMITED (nways.ng)"
}
```

Move its entrance to the gate:

```sh
curl -s -X PATCH -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"entrance": {"lat": 9.5604457, "lng": -13.6591, "kind": "gate"}}' 'https://addresses.example.gov.gn/v1/codes/GN-04259-2905-7'
```

`200`

```json
{
  "machine": "GN-04259-2905-7",
  "home": "Hafia 1 · 2905",
  "plate": "HAFIA 1 · 2905",
  "zone": "0-00062",
  "official_name": "Hafia 1",
  "label": "Dixinn",
  "number": 2905,
  "check": 7,
  "status": "confirmed",
  "issued": "on-demand",
  "issued_at": "2026-10-21T19:27:31Z",
  "entrance_lat": 9.5604457,
  "entrance_lng": -13.6591,
  "entrance_kind": "gate",
  "spot": "0 22JV 2FF7",
  "plus_code": "6CX8H86R+59C",
  "class": "residential.house",
  "use": "residential",
  "kind": "building",
  "structures": 1,
  "floor_area_m2": 80.3,
  "settlement": "",
  "official_street": "",
  "country": "GN",
  "forms": {
    "remembered": "Hafia 1 · 2905",
    "written": "Hafia 1 · 2905",
    "plate": "HAFIA 1 · 2905",
    "spoken": "Hafia 1, vingt-neuf zéro cinq",
    "machine": "GN-04259-2905-7"
  },
  "place": "Dixinn, Conakry",
  "full_line": "Hafia 1 · 2905 · Dixinn, Conakry",
  "bloc": "0 22JV",
  "area": {
    "zone": "0-00062",
    "area_id": "osm:relation/5582736",
    "plate_name": "Hafia 1",
    "official_name": "Hafia 1",
    "kind": "quartier",
    "label": "Dixinn",
    "place": "Dixinn, Conakry",
    "frame": "CKY",
    "name_id": 4259,
    "name_needs_council_choice": false,
    "codes": 911
  },
  "frame": {
    "key": "CKY",
    "digit": 0,
    "name": "Conakry",
    "bbox": [
      -13.8403,
      9.4322,
      -13.4738,
      9.7534
    ]
  },
  "registry_file": "CKY.csv.gz",
  "credit": "N-Ways Addressing for Guinea, © N-WAYS LIMITED (nways.ng)"
}
```

A move over 80 m:

```sh
curl -s -X PATCH -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"entrance": {"lat": 9.561499999999999, "lng": -13.6591}}' 'https://addresses.example.gov.gn/v1/codes/GN-04259-2905-7'
```

`422`

```json
{
  "error": {
    "code": "too_far",
    "message": "The new entrance is 117 m from the old one; an entrance moves at most 80 m."
  }
}
```

Retire a code:

```sh
curl -s -X PATCH -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"status": "retired"}' 'https://addresses.example.gov.gn/v1/codes/GN-04259-2150-8'
```

`200`

```json
{
  "machine": "GN-04259-2150-8",
  "home": "Hafia 1 · 2150",
  "plate": "HAFIA 1 · 2150",
  "zone": "0-00062",
  "official_name": "Hafia 1",
  "label": "Dixinn",
  "number": 2150,
  "check": 8,
  "status": "retired",
  "issued": "on-demand",
  "issued_at": "2026-10-21T19:27:31Z",
  "entrance_lat": 9.5606085,
  "entrance_lng": -13.6591,
  "entrance_kind": "door",
  "spot": "0 22JV 2FQ7",
  "plus_code": "6CX8H86R+69R",
  "class": "",
  "use": "residential",
  "kind": "door",
  "structures": 0,
  "floor_area_m2": 0.0,
  "settlement": "",
  "official_street": "",
  "country": "GN",
  "forms": {
    "remembered": "Hafia 1 · 2150",
    "written": "Hafia 1 · 2150",
    "plate": "HAFIA 1 · 2150",
    "spoken": "Hafia 1, vingt et un cinquante",
    "machine": "GN-04259-2150-8"
  },
  "place": "Dixinn, Conakry",
  "full_line": "Hafia 1 · 2150 · Dixinn, Conakry",
  "bloc": "0 22JV",
  "area": {
    "zone": "0-00062",
    "area_id": "osm:relation/5582736",
    "plate_name": "Hafia 1",
    "official_name": "Hafia 1",
    "kind": "quartier",
    "label": "Dixinn",
    "place": "Dixinn, Conakry",
    "frame": "CKY",
    "name_id": 4259,
    "name_needs_council_choice": false,
    "codes": 911
  },
  "frame": {
    "key": "CKY",
    "digit": 0,
    "name": "Conakry",
    "bbox": [
      -13.8403,
      9.4322,
      -13.4738,
      9.7534
    ]
  },
  "registry_file": "CKY.csv.gz",
  "credit": "N-Ways Addressing for Guinea, © N-WAYS LIMITED (nways.ng)"
}
```

Change a retired code:

```sh
curl -s -X PATCH -H "Authorization: Bearer $ISSUE_KEY" -H 'Content-Type: application/json' -d '{"status": "confirmed"}' 'https://addresses.example.gov.gn/v1/codes/GN-04259-2150-8'
```

`409`

```json
{
  "error": {
    "code": "retired",
    "message": "GN-04259-2150-8 is retired. A retired code never changes and is never reused."
  }
}
```


## Unknown paths and methods

Every other path answers `404`, and a known path with another method answers `405` with an `Allow` header.

An unknown path:

```sh
curl -s 'https://addresses.example.gov.gn/v1/addresses'
```

`404`

```json
{
  "error": {
    "code": "not_found",
    "message": "No endpoint /v1/addresses. See /v1/info and the API documentation."
  }
}
```

A method that is not allowed:

```sh
curl -s -X DELETE 'https://addresses.example.gov.gn/v1/codes/GN-04261-1230-8'
```

`405`

```json
{
  "error": {
    "code": "method_not_allowed",
    "message": "DELETE is not allowed here. Allowed: GET, PATCH."
  }
}
```

A read-only path written to:

```sh
curl -s -X POST -H 'Content-Type: application/json' -d '{}' 'https://addresses.example.gov.gn/v1/health'
```

`405`

```json
{
  "error": {
    "code": "method_not_allowed",
    "message": "POST is not allowed here. Allowed: GET."
  }
}
```
