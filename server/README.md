# Registry server

A ready-to-deploy HTTP service for Guinea's addresses. It serves exactly the published registry (`registry/`, 3,808,784 codes) as a JSON API, and the deployment designated as the country's issuer can issue new codes by the same rules as the N-Ways issuer, so every deployment gives the same answers.

- Python 3.9 or newer, standard library only: `http.server`, `sqlite3`, `json`, `gzip`, `hashlib`.
- It uses the reference engine (`engine/reference/gn_codes.py`) for parsing, check digits, spot codes and plate names, and the decoder data in `engine/data/`.
- The API is documented endpoint by endpoint, with real requests and responses, in [docs/api.md](../docs/api.md), and described in [openapi.yaml](openapi.yaml) (OpenAPI 3.1).

## Deploy with Docker

From the root of the repository:

```sh
docker compose up -d
curl -s http://localhost:8080/v1/health
```

On first start the container imports the bundled registry into the `addresses-data` volume (about two minutes and 2 GB of disk for the whole country), then serves. Later starts serve at once. The image runs as an unprivileged user and has a health check on `/v1/health`.

Without Compose:

```sh
docker build -t n-ways/addresses-guinea .
docker run -d --name addresses -p 8080:8080 -v addresses-data:/data n-ways/addresses-guinea
```

## Deploy with plain Python

```sh
python3 -m server import --registry registry --db data/addresses.sqlite
python3 -m server serve  --db data/addresses.sqlite --port 8080
```

`import` checks the SHA-256 of every file against `registry/MANIFEST.json` and the code counts against its totals, and refuses any mismatch. It builds the database beside the old one and swaps it in only when it is complete, so it can be re-run safely; it does nothing when the database already holds the same registry (`--force` re-imports). It refuses to replace a database that holds codes issued or changed locally unless `--replace-local-changes` is given.

`python3 -m server start` does both: it imports when the database does not exist yet, then serves. The container runs this.

To run it as a service under systemd:

```ini
[Unit]
Description=Guinea addresses registry
After=network.target

[Service]
User=addresses
WorkingDirectory=/opt/open-addresses-guinea
Environment=ADDRESSES_DB=/var/lib/addresses/addresses.sqlite PORT=8080
ExecStart=/usr/bin/python3 -m server start
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## Configure

| Variable | Default | |
|---|---|---|
| `ADDRESSES_DB` | `data/addresses.sqlite` (`/data/addresses.sqlite` in the container) | the SQLite database |
| `PORT` | `8080` | the HTTP port |
| `HOST` | `0.0.0.0` | the address to listen on |
| `REGISTRY_DIR` | `registry` (`/app/registry` in the container) | the registry `start` imports on first start |
| `ISSUE_KEYS` | empty: read-only | comma-separated bearer keys allowed to issue and change codes |
| `ISSUE_PER_DAY` | `5` | codes each key may issue in any 24 hours |
| `CORS_ORIGINS` | empty (`*` in the Compose file) | origins allowed to call the API from a browser; `*` for any |

Keys are compared by their SHA-256; the database records which key (by a short hash) issued or changed each code. Make a key with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"` and keep it out of version control (a `.env` file next to `docker-compose.yml` is read by Compose and ignored by git).

## Behind a reverse proxy with TLS

Serve the API over HTTPS only. The server speaks plain HTTP on its port; put a proxy in front of it. With Caddy, which obtains and renews the certificate itself:

```
addresses.example.gov.gn {
    reverse_proxy 127.0.0.1:8080
}
```

With nginx:

```nginx
server {
    listen 443 ssl http2;
    server_name addresses.example.gov.gn;
    ssl_certificate     /etc/letsencrypt/live/addresses.example.gov.gn/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/addresses.example.gov.gn/privkey.pem;
    client_max_body_size 64k;
    location /v1/ {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

When publishing the container behind a proxy on the same host, bind it to the loopback address (`"127.0.0.1:8080:8080"` in `docker-compose.yml`).

## Back up

The database is one SQLite file in WAL mode. Take a consistent copy while the server runs:

```sh
sqlite3 /var/lib/addresses/addresses.sqlite ".backup '/backups/addresses-$(date +%F).sqlite'"
```

or, in the container, `docker compose exec addresses python3 -c "import sqlite3; s=sqlite3.connect('/data/addresses.sqlite'); d=sqlite3.connect('/data/backup.sqlite'); s.backup(d)"`.

An issuing deployment should also export the registry regularly, in the published format, and keep the exports:

```sh
python3 -m server export --db data/addresses.sqlite --out exports/$(date +%F)
```

The export holds `areas.csv.gz`, one `<ZONE>.csv.gz` per zone and `MANIFEST.json` with the counts and SHA-256 of each file. Codes issued here, their new blocks and every status or entrance change are in it. An export of a database that has not changed since import is byte-identical (uncompressed) to the registry it was imported from.

## Update to a newer registry

A read-only deployment follows the published registry:

```sh
git pull                                   # or download the new registry/ folder
python3 -m server import --registry registry --db data/addresses.sqlite
```

then restart the server. With Docker, rebuild the image (`docker compose build`), remove the volume's database file and start again, or run the import inside the container. The import refuses a registry whose files do not match their manifest.

An issuing deployment is the source of the registry, so it does not import over its own database: its exports are what everyone else imports.

## One issuer

A code is a number taken from a name's national range. Two deployments that issue independently would each take the next free number of the same gap and give one number to two different homes, and nothing could later tell which was meant. So, for the whole of Guinea, **exactly one deployment issues codes**:

- A deployment issues only when the State or N-WAYS LIMITED has designated it as the issuer. Only that deployment is given `ISSUE_KEYS`.
- Every other deployment (a ministry's mirror, a post office, a company, a developer) runs read-only, without `ISSUE_KEYS`. `POST` and `PATCH` then answer `403 read_only`.
- The issuer runs a single server process on a single database, so that numbers are allocated one at a time. Scale reads by adding read-only deployments that import its exports.
- If the issuer moves (for example from N-WAYS LIMITED to a public body), the new issuer imports the last export of the old one, the old one stops issuing, and only then does the new one receive keys.

## What the server answers, and how

- **Codes** are found by machine form, by remembered or plate form (any case, spacing or accents; an official name works in place of the plate name), by spot code, and in Kaloum by official street address.
- **In Guinea** means inside a frame outline, or in no outline but within 0.01° of one: exactly the points the spot-code rule gives a code (`engine/SPEC.md` sections 2 and 3.4). A compound in a gap between outlines is found at its entrance, can take a code or another door there, and an entrance can move there; further out a point is `outside`.
- **The border decides** (`engine/SPEC.md` section 2.1). A point more than 300 m outside the national border, OpenStreetMap's admin_level=2 boundary of Guinea shipped simplified in `engine/data/border.geojson`, is in a neighbouring country, whatever the frame outlines say: issuing there and moving an entrance there answer `422 outside`, and `GET /v1/at` answers `outside` where no issued code lies within 12 m. The file records its largest deviation from the true line (5.5 m), which the server takes off the 300 m, so it accepts nothing more than 300 m outside the true border. Spot codes are not affected: they are computed for every point a frame holds.
- **At a point**, a code is "found" when an issued entrance lies within 12 m, or the point is inside an outline drawn when a code was issued on this server. The N-Ways service first tests the published compound against its building footprints, which are not part of the registry; at an entrance the two agree for about 94 points in 100, and the rest differ only between neighbouring compounds.
- **Issuing** follows `engine/SPEC.md` sections 4 and 7 and the N-Ways issuer exactly: a point within 3 m of an issued compound, or an outline that shares more than half of a drawn outline, already has its code (`409 exists`); since the registry carries entrances rather than footprints, an outline that contains a published compound's entrance also counts as that compound. Outlines must be 6 m² to 2 ha. The area is the official quartier holding the point, else the nearest locality; another door (`of`) takes its compound's area and must stand within 80 m. The number is the free number nearest the middle of the gap between the new compound's neighbours on the area's Hilbert curve, in each of the area's blocks in turn; when they are full, the area opens an extension block at its name's next free number, sized to twice its compounds. Retired numbers stay taken. New codes are `provisional` and `issued: on-demand`.
- **Changes**: a status moves between `provisional` and `confirmed`, or to `retired`, which is final; an entrance moves by at most 80 m, and its spot code and Plus Code follow it. The point on the numbering curve never moves.

## Tests

```sh
python3 -m unittest discover -s server/tests -t .
```

The tests run on a test registry built from the published one (`server/testdata/registry`: the complete area table and every code of Kaloum, 5,646 codes; `server/testdata/make_fixture.py` rebuilds it). They cover the import and export round trip, the refusal of altered files and wrong counts, every endpoint and its errors, the duplicate and outline rules, doors, the daily limit, status and entrance changes, points in no frame outline (`server/testdata/gaps.csv`: 24 published codes whose entrances lie in gaps between outlines, each found at its entrance, plus issuing, a door and an entrance move there, and points beyond 0.01° refused), the national border (points on one line across it: a code and an entrance move 260 m outside allowed, 330 m and 1 km outside refused), and issuing parity: `server/testdata/parity.json` holds 146 issue requests applied in order (new compounds across Kaloum and the rest of the country, and doors that fill two areas' blocks and open extension blocks) with the result the N-Ways issuer gives for each, which the server must reproduce number for number and form for form.

## Resources

The full registry takes about 2 GB of disk once imported and the import takes one to two minutes. The server needs about 150 MB of memory. A small virtual machine (1 vCPU, 1 GB of memory, 10 GB of disk) is enough for a national read-only deployment.
