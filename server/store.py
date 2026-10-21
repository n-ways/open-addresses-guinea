"""SQLite storage of the registry: import, export and the queries the API needs.

The database keeps every registry column exactly as published (text), so an
export of an unchanged database reproduces the published files byte for byte.
Typed copies of the columns that are searched (name id, number, coordinates)
sit beside them with their indexes.
"""
import contextlib
import csv
import gzip
import hashlib
import json
import math
import os
import sqlite3
import time

from . import engine

CODE_COLUMNS = ['machine', 'home', 'plate', 'zone', 'official_name', 'label', 'number', 'check', 'status', 'issued',
                'issued_at', 'entrance_lat', 'entrance_lng', 'entrance_kind', 'spot', 'plus_code', 'class', 'use',
                'kind', 'structures', 'floor_area_m2', 'settlement', 'official_street']
AREA_COLUMNS = ['zone', 'frame', 'index', 'area_id', 'plate_name', 'official_name', 'kind', 'label', 'name_key',
                'name_id', 'blocks', 'needs_council_choice', 'lat', 'lon']
FRAME_KEYS = ['CKY', 'BAS', 'MOY', 'HAU', 'FOR']   # registry files, in frame-digit order
GRID_DEG = 0.01                                    # cell of the fallback spatial index (about 1.1 km)
BATCH = 20000


def q(name):
    return '"%s"' % name


SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS areas (%s, PRIMARY KEY ("zone"));
CREATE TABLE IF NOT EXISTS codes (
  %s,
  frame TEXT NOT NULL,          -- registry file (frame key)
  name_id INTEGER NOT NULL,
  num INTEGER NOT NULL,
  lat REAL NOT NULL, lng REAL NOT NULL,                 -- entrance
  anchor_lat REAL NOT NULL, anchor_lng REAL NOT NULL,   -- point on the numbering curve (never moves)
  street_key TEXT,
  outline TEXT,                 -- [[lng, lat], ...] when the code was issued from a drawn outline
  issued_by TEXT,               -- hash of the issuing key
  changed INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY ("machine")
) WITHOUT ROWID;
CREATE TABLE IF NOT EXISTS blocks_added (zone TEXT NOT NULL, lo INTEGER NOT NULL, hi INTEGER NOT NULL, at TEXT NOT NULL, by TEXT);
CREATE TABLE IF NOT EXISTS changes (at TEXT NOT NULL, machine TEXT NOT NULL, field TEXT NOT NULL, old TEXT, new TEXT, by TEXT);
""" % (', '.join('%s TEXT NOT NULL' % q(c) for c in AREA_COLUMNS), ',\n  '.join('%s TEXT NOT NULL' % q(c) for c in CODE_COLUMNS))

INDEXES = """
CREATE UNIQUE INDEX IF NOT EXISTS codes_number ON codes (name_id, num);
CREATE INDEX IF NOT EXISTS codes_home ON codes (home);
CREATE INDEX IF NOT EXISTS codes_street ON codes (street_key) WHERE street_key IS NOT NULL;
CREATE INDEX IF NOT EXISTS codes_zone ON codes ("zone");
CREATE INDEX IF NOT EXISTS codes_frame ON codes (frame, machine);
CREATE INDEX IF NOT EXISTS codes_issued_by ON codes (issued_by, issued_at) WHERE issued_by IS NOT NULL;
CREATE INDEX IF NOT EXISTS areas_key ON areas (name_key);
CREATE INDEX IF NOT EXISTS areas_aid ON areas (area_id);
"""


class RegistryError(Exception):
    pass


def has_rtree():
    try:
        c = sqlite3.connect(':memory:')
        c.execute('CREATE VIRTUAL TABLE t USING rtree(id, a, b, c, d)')
        c.close()
        return True
    except sqlite3.Error:
        return False


def connect(path, readonly=False):
    if not os.path.exists(path) and readonly:
        raise RegistryError('%s does not exist' % path)
    c = sqlite3.connect(path, check_same_thread=False, timeout=30)
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('PRAGMA synchronous=NORMAL')
    if readonly:
        c.execute('PRAGMA query_only=ON')
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys=ON')
    return c


def street_key(street):
    """Search key of an official street address: the street without the commune."""
    if not street:
        return None
    s = street.split(',')[0]
    return engine.ref.normalise_name(s) or None


# ---------------------------------------------------------------- import

def _sha256_plain(path):
    h = hashlib.sha256()
    with gzip.open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def read_manifest(registry):
    p = os.path.join(registry, 'MANIFEST.json')
    if not os.path.exists(p):
        raise RegistryError('%s has no MANIFEST.json' % registry)
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def verify(registry, log=print):
    """Checks every file of a registry against its manifest. Returns the manifest."""
    man = read_manifest(registry)
    if man.get('country') != engine.COUNTRY:
        raise RegistryError('the manifest is for country %r, not %s' % (man.get('country'), engine.COUNTRY))
    for name, want in sorted(man['sha256'].items()):
        p = os.path.join(registry, name + '.gz')
        if not os.path.exists(p):
            raise RegistryError('%s is listed in the manifest but missing' % (name + '.gz'))
        got = _sha256_plain(p)
        if got != want:
            raise RegistryError('%s: SHA-256 %s, manifest says %s' % (name + '.gz', got, want))
        log('  %-12s sha256 ok' % (name + '.gz'))
    return man


def _rows(path):
    with gzip.open(path, 'rt', encoding='utf-8', newline='') as f:
        r = csv.reader(f)
        header = next(r)
        yield header
        for row in r:
            yield row


def import_registry(registry, db_path, log=print, force=False, replace_local=False):
    """Loads a published registry into a new SQLite database and swaps it in.

    Verifies every file's SHA-256 and the counts against MANIFEST.json and
    refuses any mismatch. Safe to re-run: the database is built beside the old
    one and replaces it only when complete. An existing database with codes
    issued or changed locally is kept unless replace_local is set."""
    man = verify(registry, log)
    digest = hashlib.sha256(json.dumps(man['sha256'], sort_keys=True).encode()).hexdigest()
    if os.path.exists(db_path):
        with contextlib.closing(connect(db_path)) as old:
            try:
                same = old.execute("SELECT value FROM meta WHERE key='registry_digest'").fetchone()
                local = old.execute('SELECT count(*) FROM codes WHERE changed <> 0').fetchone()[0]
            except sqlite3.Error:
                same, local = None, 0
        if local and not replace_local:
            raise RegistryError('%s holds %d codes issued or changed here; export them first, or pass '
                                '--replace-local-changes to discard them' % (db_path, local))
        if same and same[0] == digest and not force:
            log('%s already holds this registry (exported %s); nothing to do' % (db_path, man.get('exported')))
            return man
    tmp = db_path + '.importing'
    for suffix in ('', '-wal', '-shm'):
        if os.path.exists(tmp + suffix):
            os.remove(tmp + suffix)
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    c = connect(tmp)
    c.execute('PRAGMA journal_mode=OFF')
    c.execute('PRAGMA synchronous=OFF')
    c.executescript(SCHEMA)
    rtree = has_rtree()
    if rtree:
        c.execute('CREATE VIRTUAL TABLE IF NOT EXISTS codes_rtree USING rtree(id, min_lat, max_lat, min_lng, max_lng)')
        c.execute('CREATE TABLE IF NOT EXISTS codes_rid (id INTEGER PRIMARY KEY, machine TEXT NOT NULL UNIQUE)')
    else:
        c.execute('CREATE TABLE IF NOT EXISTS codes_grid (cell INTEGER NOT NULL, machine TEXT NOT NULL)')
    # areas
    rows = _rows(os.path.join(registry, 'areas.csv.gz'))
    header = next(rows)
    if header != AREA_COLUMNS:
        raise RegistryError('areas.csv.gz: unexpected columns %s' % header)
    areas = list(rows)
    c.executemany('INSERT INTO areas VALUES (%s)' % ','.join('?' * len(AREA_COLUMNS)), areas)
    frame_of_area = {a[0]: int(a[1]) for a in areas}
    log('  areas        %d' % len(areas))
    # codes, frame by frame
    by_frame = man.get('byFrame') or {}
    total = 0
    counts = {}
    names = sorted(n[:-4] for n in man['sha256'] if n != 'areas.csv')
    for key in names:
        path = os.path.join(registry, key + '.csv.gz')
        rows = _rows(path)
        header = next(rows)
        if header != CODE_COLUMNS:
            raise RegistryError('%s.csv.gz: unexpected columns %s' % (key, header))
        n = 0
        batch = []
        for row in rows:
            if len(row) != len(CODE_COLUMNS):
                raise RegistryError('%s.csv.gz line %d: %d fields' % (key, n + 2, len(row)))
            p = engine.parse_machine(row[0])
            if p is None or p[3] != p[4]:
                raise RegistryError('%s.csv.gz line %d: %s is not a valid machine form' % (key, n + 2, row[0]))
            if row[3] not in frame_of_area:
                raise RegistryError('%s.csv.gz line %d: area %s is not in areas.csv' % (key, n + 2, row[3]))
            lat, lng = float(row[11]), float(row[12])
            batch.append(tuple(row) + (key, p[0], p[1], lat, lng, lat, lng, street_key(row[22])))
            n += 1
            if len(batch) >= BATCH:
                _insert_codes(c, batch, rtree)
                batch = []
        if batch:
            _insert_codes(c, batch, rtree)
        if key in by_frame and by_frame[key] != n:
            c.close()
            os.remove(tmp)
            raise RegistryError('%s.csv.gz has %d codes, the manifest says %d' % (key, n, by_frame[key]))
        counts[key] = n
        total += n
        log('  %-12s %d codes' % (key + '.csv.gz', n))
    if man.get('codes') is not None and man['codes'] != total:
        c.close()
        os.remove(tmp)
        raise RegistryError('the registry has %d codes, the manifest says %d' % (total, man['codes']))
    log('  indexing ...')
    c.executescript(INDEXES)
    meta = {'country': engine.COUNTRY, 'registry_exported': man.get('exported', ''), 'registry_digest': digest,
            'manifest': json.dumps(man, ensure_ascii=False, sort_keys=True), 'imported_at': now(),
            'spatial': 'rtree' if rtree else 'grid', 'files': json.dumps(names)}
    c.executemany('INSERT OR REPLACE INTO meta VALUES (?, ?)', meta.items())
    c.commit()
    c.execute('PRAGMA journal_mode=WAL')
    c.execute('ANALYZE')
    c.close()
    for suffix in ('-wal', '-shm'):
        if os.path.exists(db_path + suffix):
            os.remove(db_path + suffix)
    os.replace(tmp, db_path)
    log('imported %d codes into %s' % (total, db_path))
    return man


def _insert_codes(c, batch, rtree):
    c.executemany('INSERT INTO codes (%s, frame, name_id, num, lat, lng, anchor_lat, anchor_lng, street_key) VALUES (%s)'
                  % (','.join(q(x) for x in CODE_COLUMNS), ','.join('?' * (len(CODE_COLUMNS) + 8))), batch)
    if rtree:
        cur = c.execute('SELECT coalesce(max(id), 0) FROM codes_rid').fetchone()[0]
        ids = []
        for i, r in enumerate(batch, 1):
            ids.append((cur + i, r[0]))
        c.executemany('INSERT INTO codes_rid VALUES (?, ?)', ids)
        c.executemany('INSERT INTO codes_rtree VALUES (?, ?, ?, ?, ?)',
                      [(cur + i, r[26], r[26], r[27], r[27]) for i, r in enumerate(batch, 1)])
    else:
        c.executemany('INSERT INTO codes_grid VALUES (?, ?)', [(grid_cell(r[26], r[27]), r[0]) for r in batch])


def grid_cell(lat, lng):
    return int(math.floor((lat + 90) / GRID_DEG)) * 100000 + int(math.floor((lng + 180) / GRID_DEG))


def now():
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


# ---------------------------------------------------------------- export

_SPACE = set('\t\n\v\f\r \x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a'
             '\u2028\u2029\u202f\u205f\u3000')


def _needs_quotes(field):
    """The registry's CSV dialect: a field is quoted when it is the bare
    sequence \\. or holds a comma, a quote or a line break, or when it starts
    with white space."""
    if field == '':
        return False
    if field == '\\.':
        return True
    if any(ch in field for ch in ',"\r\n'):
        return True
    return field[0] in _SPACE


def csv_line(fields):
    out = []
    for f in fields:
        if _needs_quotes(f):
            out.append('"' + f.replace('"', '""') + '"')
        else:
            out.append(f)
    return ','.join(out) + '\n'


class _Hashing(object):
    def __init__(self, raw):
        self.raw = raw
        self.h = hashlib.sha256()

    def write(self, s):
        b = s.encode('utf-8')
        self.h.update(b)
        self.raw.write(b)


def export_registry(db_path, out, log=print):
    """Writes the registry in the published format: areas.csv.gz, one
    <FRAME>.csv.gz per frame (rows by name id, then number), MANIFEST.json."""
    os.makedirs(out, exist_ok=True)
    c = connect(db_path, readonly=True)
    meta = dict(c.execute('SELECT key, value FROM meta').fetchall())
    man_in = json.loads(meta.get('manifest', '{}'))
    changed = c.execute('SELECT count(*) FROM codes WHERE changed <> 0').fetchone()[0]
    added = c.execute('SELECT count(*) FROM blocks_added').fetchone()[0]
    sums, counts, total = {}, {}, 0

    def write(name, header, rows):
        p = os.path.join(out, name + '.gz')
        tmp = p + '.part'
        n = 0
        with open(tmp, 'wb') as raw:
            with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as gz:
                w = _Hashing(gz)
                w.write(csv_line(header))
                for r in rows:
                    w.write(csv_line(r))
                    n += 1
        os.replace(tmp, p)
        sums[name] = w.h.hexdigest()
        return n

    n = write('areas.csv', AREA_COLUMNS,
              (tuple(r) for r in c.execute('SELECT %s FROM areas ORDER BY "zone"' % ','.join(q(x) for x in AREA_COLUMNS))))
    log('  areas.csv.gz  %d areas' % n)
    present = set(r[0] for r in c.execute('SELECT DISTINCT frame FROM codes'))
    for key in FRAME_KEYS + sorted(present - set(FRAME_KEYS)):
        if key not in present:
            continue
        cur = c.execute('SELECT %s FROM codes WHERE frame = ? ORDER BY name_id, num' % ','.join(q(x) for x in CODE_COLUMNS), (key,))
        n = write(key + '.csv', CODE_COLUMNS, (tuple(r) for r in cur))
        counts[key] = n
        total += n
        log('  %-13s %d codes' % (key + '.csv.gz', n))
    c.close()
    exported = man_in.get('exported', '') if not (changed or added) else now()
    man = {'byFrame': counts, 'codes': total, 'country': engine.COUNTRY, 'credit': engine.CREDIT,
           'engine': man_in.get('engine', 'internal/addressing/gn (%s)' % engine.SPEC), 'exported': exported,
           'licence': man_in.get('licence', 'ODbL 1.0 (LICENSE-DATA)'), 'sha256': sums}
    with open(os.path.join(out, 'MANIFEST.json'), 'w', encoding='utf-8') as f:
        f.write(json.dumps(man, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    log('exported %d codes to %s' % (total, out))
    return man
