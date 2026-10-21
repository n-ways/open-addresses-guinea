"""The registry service: lookups, issuing and changes, independent of HTTP.

Every public method returns (HTTP status, JSON-ready body) or raises ApiError.
"""
import hashlib
import json
import math
import queue
import sqlite3
import threading
import time

from . import engine, store
from .engine import ref

STATUSES = ('provisional', 'confirmed', 'retired')
NUMERIC = {'number': int, 'check': int, 'entrance_lat': float, 'entrance_lng': float, 'structures': int,
           'floor_area_m2': float}


class ApiError(Exception):
    def __init__(self, status, code, message, extra=None):
        Exception.__init__(self, message)
        self.status, self.code, self.message, self.extra = status, code, message, extra or {}

    def body(self):
        b = {'error': {'code': self.code, 'message': self.message}}
        b['error'].update(self.extra)
        return b


def _float(params, name, lo, hi):
    v = params.get(name)
    if v is None or v == '':
        raise ApiError(400, 'bad_request', 'The %s parameter is required.' % name)
    if isinstance(v, bool):
        raise ApiError(400, 'bad_request', '%s must be a number.' % name)
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ApiError(400, 'bad_request', '%s must be a number.' % name)
    if not math.isfinite(x) or not lo <= x <= hi:
        raise ApiError(400, 'bad_request', '%s must be between %s and %s.' % (name, lo, hi))
    return x


def _int(params, name, default, lo, hi):
    v = params.get(name)
    if v is None or v == '':
        return default
    try:
        x = int(v)
    except (TypeError, ValueError):
        raise ApiError(400, 'bad_request', '%s must be a whole number.' % name)
    if not lo <= x <= hi:
        raise ApiError(400, 'bad_request', '%s must be between %d and %d.' % (name, lo, hi))
    return x


def key_hash(key):
    return hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]


class Service(object):
    def __init__(self, db_path, issue_keys=(), per_day=5, readers=8):
        self.db_path = db_path
        self.keys = {key_hash(k): k for k in issue_keys if k}
        self.per_day = per_day
        self.lock = threading.Lock()
        self.writer = store.connect(db_path)
        self.writer.isolation_level = None
        self._ensure_tables(self.writer)
        self.pool = queue.Queue()
        for _ in range(readers):
            self.pool.put(store.connect(db_path, readonly=True))
        self.meta = dict(self.writer.execute('SELECT key, value FROM meta').fetchall())
        self.spatial = self.meta.get('spatial', 'grid')
        self.reg = engine.Register([dict(r) for r in self.writer.execute('SELECT * FROM areas')])
        self.counts = {}
        for r in self.writer.execute('SELECT * FROM area_counts'):
            self.counts[r['zone']] = {s: r[s] for s in STATUSES}

    # ------------------------------------------------------------ plumbing

    def _ensure_tables(self, c):
        c.execute('CREATE TABLE IF NOT EXISTS area_counts (zone TEXT PRIMARY KEY, provisional INTEGER NOT NULL DEFAULT 0, '
                  'confirmed INTEGER NOT NULL DEFAULT 0, retired INTEGER NOT NULL DEFAULT 0)')
        if c.execute('SELECT count(*) FROM area_counts').fetchone()[0] == 0:
            rows = c.execute('SELECT "zone", status, count(*) FROM codes GROUP BY "zone", status').fetchall()
            per = {}
            for zone, status, n in rows:
                per.setdefault(zone, dict.fromkeys(STATUSES, 0))[status] = n
            c.execute('BEGIN')
            c.executemany('INSERT INTO area_counts VALUES (?, ?, ?, ?)', [(z, v['provisional'], v['confirmed'], v['retired'])
                                                                         for z, v in per.items()])
            c.execute('COMMIT')

    def _read(self):
        return _Lease(self.pool)

    def close(self):
        self.writer.close()
        while not self.pool.empty():
            self.pool.get().close()

    def _bump(self, c, zone, old, new):
        cur = self.counts.setdefault(zone, dict.fromkeys(STATUSES, 0))
        if old:
            cur[old] -= 1
        if new:
            cur[new] += 1
        c.execute('INSERT OR REPLACE INTO area_counts VALUES (?, ?, ?, ?)', (zone, cur['provisional'], cur['confirmed'], cur['retired']))

    def frame_counts(self):
        out = {}
        for zone, v in self.counts.items():
            a = self.reg.area(zone)
            key = self.reg.frames[a.frame]['key'] if a else '?'
            t = out.setdefault(key, dict.fromkeys(STATUSES, 0))
            for s in STATUSES:
                t[s] += v[s]
        for t in out.values():
            t['total'] = sum(t[s] for s in STATUSES)
        return out

    def total(self):
        return sum(sum(v.values()) for v in self.counts.values())

    # ------------------------------------------------------------ shapes of answers

    def frame_json(self, f):
        return {'key': f['key'], 'digit': f['digit'], 'name': f['name'], 'bbox': f['box']}

    def area_json(self, a, full=False):
        out = {'zone': a.ref, 'area_id': a.aid, 'plate_name': a.name, 'official_name': a.official_name or a.name,
               'kind': a.kind, 'label': a.label, 'place': a.place_line(), 'frame': self.reg.frames[a.frame]['key'],
               'name_id': a.name_id, 'name_needs_council_choice': a.needs_council_choice}
        c = self.counts.get(a.ref, dict.fromkeys(STATUSES, 0))
        out['codes'] = sum(c.values())
        if full:
            out.update({
                'index': a.index, 'name_key': a.name_key, 'lat': a.lat, 'lon': a.lon,
                'blocks': [{'lo': lo, 'hi': hi, 'size': hi - lo + 1} for lo, hi in a.blocks],
                'counts': dict(c, total=sum(c.values())),
                'numbers': {'in_blocks': sum(hi - lo + 1 for lo, hi in a.blocks),
                            'free': sum(hi - lo + 1 for lo, hi in a.blocks) - sum(c.values())},
                'same_name': [o.ref for o in self.reg.families.get(a.name_key, []) if o is not a],
            })
        return out

    def card(self, row):
        """The full record of a code: every registry column, named, and what
        derives from it."""
        rec = {}
        for col in store.CODE_COLUMNS:
            v = row[col]
            if col in NUMERIC and v != '':
                v = NUMERIC[col](v)
            rec[col] = v
        a = self.reg.area(row['zone'])
        forms = self.reg.forms(a, int(row['number']))
        f = self.reg.frames[a.frame]
        rec.update({
            'country': engine.COUNTRY,
            'forms': forms,
            'place': a.place_line(),
            'full_line': forms['remembered'] + ' · ' + a.place_line(),
            'bloc': row['spot'][:6],
            'area': self.area_json(a),
            'frame': self.frame_json(f),
            'registry_file': row['frame'] + '.csv.gz',
            'credit': engine.CREDIT,
        })
        if row['official_street']:
            rec['official_address'] = row['official_street']
        return rec

    def summary(self, row, d=None):
        out = {'machine': row['machine'], 'home': row['home'], 'plate': row['plate'], 'zone': row['zone'],
               'status': row['status'], 'entrance_lat': float(row['entrance_lat']), 'entrance_lng': float(row['entrance_lng']),
               'entrance_kind': row['entrance_kind'], 'use': row['use']}
        if d is not None:
            out['distance_m'] = round(d, 1)
        return out

    # ------------------------------------------------------------ spatial

    def _ids_near(self, c, lat, lng, metres):
        dlat = metres / 110574.0 + 1e-7
        dlng = metres / (111320.0 * max(0.01, math.cos(math.radians(lat)))) + 1e-7
        if self.spatial == 'rtree':
            return [r[0] for r in c.execute(
                'SELECT r.machine FROM codes_rtree t JOIN codes_rid r ON r.id = t.id '
                'WHERE t.min_lat <= ? AND t.max_lat >= ? AND t.min_lng <= ? AND t.max_lng >= ?',
                (lat + dlat, lat - dlat, lng + dlng, lng - dlng))]
        cells = []
        for i in range(int(math.floor((lat - dlat + 90) / store.GRID_DEG)), int(math.floor((lat + dlat + 90) / store.GRID_DEG)) + 1):
            for j in range(int(math.floor((lng - dlng + 180) / store.GRID_DEG)), int(math.floor((lng + dlng + 180) / store.GRID_DEG)) + 1):
                cells.append(i * 100000 + j)
        out = []
        for k in range(0, len(cells), 500):
            part = cells[k:k + 500]
            out += [r[0] for r in c.execute('SELECT machine FROM codes_grid WHERE cell IN (%s)' % ','.join('?' * len(part)), part)]
        return out

    def _rows(self, c, machines):
        out = []
        for k in range(0, len(machines), 500):
            part = machines[k:k + 500]
            out += c.execute('SELECT * FROM codes WHERE machine IN (%s)' % ','.join('?' * len(part)), part).fetchall()
        return out

    def code_at(self, c, lat, lng, max_m):
        """The live code at a point: a code whose drawn outline holds the point,
        else the nearest within max_m of its entrance or outline. (code row, metres) or (None, None)."""
        rows = [r for r in self._rows(c, self._ids_near(c, lat, lng, max(max_m, 300.0))) if r['status'] != 'retired']
        inside = sorted((r for r in rows if r['outline'] and engine.in_ring(lng, lat, json.loads(r['outline']))),
                        key=lambda r: r['machine'])
        if inside:
            return inside[0], 0.0
        best, bd = None, None
        for r in rows:
            d = engine.dist_m(lat, lng, r['lat'], r['lng'])
            if r['outline']:
                d = min(d, engine.ring_distance_m(lat, lng, json.loads(r['outline'])))
            if d <= max_m and (bd is None or d < bd or (d == bd and r['machine'] < best['machine'])):
                best, bd = r, d
        return best, bd

    # ------------------------------------------------------------ read endpoints

    def health(self):
        return 200, {'status': 'ok', 'country': engine.COUNTRY, 'codes': self.total(),
                     'registry_exported': self.meta.get('registry_exported'), 'issuing': bool(self.keys)}

    def info(self):
        fc = self.frame_counts()
        zones = []
        for d in sorted(self.reg.frames):
            f = self.reg.frames[d]
            z = self.frame_json(f)
            z['codes'] = fc.get(f['key'], {}).get('total', 0)
            z['areas'] = sum(1 for a in self.reg.areas if a.frame == d)
            zones.append(z)
        return 200, {
            'country': engine.COUNTRY, 'name': engine.COUNTRY_NAME,
            'codes': self.total(), 'areas': len(self.reg.areas), 'zones': zones,
            'counts': {s: sum(v[s] for v in fc.values()) for s in STATUSES},
            'registry_exported': self.meta.get('registry_exported'), 'imported_at': self.meta.get('imported_at'),
            'licences': {'code': 'Apache-2.0', 'data': 'ODbL-1.0', 'documents': 'CC-BY-4.0'},
            'credit': engine.CREDIT, 'credit_url': engine.CREDIT_URL,
            'engine': {'spec': engine.SPEC, 'reference': 'engine/reference/gn_codes.py'},
            'issuing': {'enabled': bool(self.keys), 'per_key_per_day': self.per_day},
            'example': {'remembered': 'Hafia 3 · 1230', 'machine': 'GN-04261-1230-8', 'spot': '0 22JV PVQQ'},
        }

    def get_code(self, machine):
        p = engine.parse_machine(machine)
        if p is None:
            raise ApiError(400, 'invalid_code', '%r is not a machine form (GN-NNNNN-NNNN-C).' % machine)
        if p[3] != p[4]:
            raise ApiError(422, 'check_mismatch', 'The check digit of %s does not match: a digit is wrong or two are swapped.'
                           % engine.machine_text(machine))
        with self._read() as c:
            row = c.execute('SELECT * FROM codes WHERE machine = ?', (engine.machine_text(machine),)).fetchone()
        if row is None:
            raise ApiError(404, 'not_issued', '%s is a valid machine form, but no such code has been issued.' % engine.machine_text(machine))
        return 200, self.card(row)

    def find(self, params):
        text = (params.get('q') or '').strip()
        if not text:
            raise ApiError(400, 'bad_request', 'The q parameter is required: a home code, a machine form, an official address or a spot code.')
        if len(text) > 200:
            raise ApiError(400, 'bad_request', 'q is longer than 200 characters.')
        if engine.MACHINE_SHAPE.match(engine.machine_text(text)):
            st, card = self.get_code(text)
            return 200, {'query': text, 'kind': 'machine', 'count': 1, 'total': 1, 'truncated': False, 'matches': [card]}
        if engine.looks_spot(text):
            return self._find_spot(text)
        return self._find_home(text, _int(params, 'limit', 20, 1, 50))

    def _find_spot(self, text):
        try:
            d = ref.decode_spot(text, self.reg.frames)
        except ValueError as e:
            code = 'check_mismatch' if 'check' in str(e) else 'invalid_code'
            raise ApiError(422 if code == 'check_mismatch' else 400, code, str(e)[:1].upper() + str(e)[1:] + '.')
        with self._read() as c:
            row, dist = self.code_at(c, d['lat'], d['lon'], engine.SPOT_FOUND_M)
        if row is None:
            raise ApiError(404, 'no_code_here', 'The spot %s is not on an issued compound.' % text.strip(),
                           {'spot': {'lat': d['lat'], 'lng': d['lon']}})
        card = self.card(row)
        card['distance_m'] = round(dist, 1)
        return 200, {'query': text, 'kind': 'spot', 'count': 1, 'total': 1, 'truncated': False, 'matches': [card]}

    def _find_home(self, text, limit=20):
        t = text.split(',')[0].strip()
        try:
            hit = ref.decode_home(t, self.reg.names())
        except ValueError as e:
            msg = str(e)
            via = self._find_street(text, limit)
            if via is not None:
                return via
            if msg.startswith('a home code is'):
                raise ApiError(400, 'invalid_code', 'A home code is a place name followed by 4 or 5 digits, such as "Hafia 3 · 1230".')
            if 'check digit' in msg:
                raise ApiError(422, 'check_mismatch', 'The check digit does not match: a digit is wrong or two are swapped.')
            if msg.startswith('ambiguous'):
                raise ApiError(422, 'ambiguous', 'Write the number after a "·", for example "Hafia 3 · 1230".')
            raise ApiError(404, 'not_found', 'No code matches %r: %s.' % (text, msg))
        with self._read() as c:
            row = c.execute('SELECT * FROM codes WHERE name_id = ? AND num = ?', (hit['nameId'], hit['number'])).fetchone()
        if row is None:
            a = self.reg.area(hit['zone'])
            raise ApiError(404, 'not_issued', 'No compound has %s yet: the number lies in the block of %s (%s) but has not been issued.'
                           % (ref.remembered(a.name, hit['number']), a.name, a.place_line()), {'zone': a.ref})
        if row['status'] == 'retired':
            raise ApiError(410, 'retired', '%s was retired: there is no compound there any more. A code is never reused.' % row['home'],
                           {'machine': row['machine']})
        return 200, {'query': text, 'kind': 'remembered', 'count': 1, 'total': 1, 'truncated': False, 'matches': [self.card(row)]}

    def _street_rows(self, street, limit):
        k = store.street_key(street)
        if not k:
            return []
        with self._read() as c:
            return c.execute('SELECT * FROM codes WHERE street_key = ? AND status <> ? ORDER BY name_id, num LIMIT ?',
                             (k, 'retired', limit)).fetchall()

    def _find_street(self, text, limit):
        """An official address: "<street>, Kaloum", or "<street> · <home code>"."""
        parts = text.split('·')
        for i in range(1, len(parts)):
            street, home = '·'.join(parts[:i]).strip(), '·'.join(parts[i:]).strip()
            k = store.street_key(street)
            if not k or not self._street_rows(street, 1):
                continue
            try:
                hit = ref.decode_home(home, self.reg.names())
            except ValueError:
                continue
            with self._read() as c:
                row = c.execute('SELECT * FROM codes WHERE name_id = ? AND num = ? AND street_key = ?',
                                (hit['nameId'], hit['number'], k)).fetchone()
            if row is not None:
                return 200, {'query': text, 'kind': 'official_address', 'count': 1, 'total': 1, 'truncated': False, 'matches': [self.card(row)]}
        rows = self._street_rows(text, limit)
        if not rows:
            return None
        with self._read() as c:
            total = c.execute('SELECT count(*) FROM codes WHERE street_key = ? AND status <> ?', (store.street_key(text), 'retired')).fetchone()[0]
        return 200, {'query': text, 'kind': 'official_address', 'count': len(rows), 'total': total, 'truncated': total > len(rows),
                     'matches': [self.card(r) for r in rows]}

    def at(self, params):
        lat = _float(params, 'lat', -90, 90)
        lng = _float(params, 'lng', -180, 180)
        f = self.reg.frame_of(lat, lng)
        row = d = None
        if f is not None:
            with self._read() as c:
                row, d = self.code_at(c, lat, lng, engine.AT_FOUND_M)
        if f is None or (row is None and self.reg.in_guinea(lat, lng) is None):
            return 200, {'status': 'outside', 'lat': lat, 'lng': lng,
                         'message': 'This point is outside Guinea.'}
        area = self.reg.place_for(lat, lng)
        out = {'status': 'found' if row else 'none', 'lat': lat, 'lng': lng, 'frame': self.frame_json(f),
               'area': self.area_json(area) if area else None}
        if row:
            out['distance_m'] = round(d, 1)
            out['code'] = self.card(row)
        else:
            out['message'] = 'No issued compound within %d m of this point.' % engine.AT_FOUND_M
        return 200, out

    def near(self, params):
        lat = _float(params, 'lat', -90, 90)
        lng = _float(params, 'lng', -180, 180)
        radius = _float(params, 'radius', 1, 500) if params.get('radius') not in (None, '') else 100.0
        limit = _int(params, 'limit', 20, 1, 100)
        with self._read() as c:
            rows = self._rows(c, self._ids_near(c, lat, lng, radius))
        hits = sorted(((engine.dist_m(lat, lng, r['lat'], r['lng']), r['machine'], r) for r in rows), key=lambda t: (t[0], t[1]))
        hits = [h for h in hits if h[0] <= radius]
        return 200, {'lat': lat, 'lng': lng, 'radius_m': radius, 'count': len(hits[:limit]), 'total': len(hits),
                     'codes': [self.summary(r, d) for d, _, r in hits[:limit]]}

    def verify(self, params):
        code = (params.get('code') or '').strip()
        if not code:
            raise ApiError(400, 'bad_request', 'The code parameter is required.')
        m = engine.machine_text(code)
        p = engine.parse_machine(code)
        out = {'code': code, 'machine': m, 'syntax_ok': p is not None, 'check_ok': False, 'issued': False}
        if p is None:
            out.update(valid=False, reason='not a machine form: GN-<name id, 5 digits>-<number, 4 or 5 digits>-<check digit>')
            return 200, out
        out['check_ok'] = p[3] == p[4]
        if not out['check_ok']:
            out.update(valid=False, reason='the check digit does not match: a digit is wrong or two are swapped',
                       expected_check=p[4])
            return 200, out
        key = self.reg.key_of.get(p[0])
        if key is None:
            out.update(valid=False, reason='no place name has the national id %05d' % p[0])
            return 200, out
        owner = self.reg.owner(key, p[1])
        out['in_block_of'] = owner.ref if owner else None
        with self._read() as c:
            row = c.execute('SELECT machine, home, status FROM codes WHERE machine = ?', (m,)).fetchone()
        if row:
            out.update(valid=row['status'] != 'retired', issued=True, status=row['status'], home=row['home'])
            if row['status'] == 'retired':
                out['reason'] = 'issued, then retired; a code is never reused'
        else:
            out.update(valid=False, reason='well formed, but not issued')
        return 200, out

    def spot(self, params):
        lat = _float(params, 'lat', -90, 90)
        lng = _float(params, 'lng', -180, 180)
        code, f, edge = self.reg.spot_edge(lat, lng)
        if f is None:
            raise ApiError(422, 'outside', 'This point is outside Guinea: it has no spot code.')
        d = ref.decode_spot(code, self.reg.frames)
        return 200, {'spot': code, 'bloc': code[:6], 'frame': self.frame_json(f), 'lat': lat, 'lng': lng,
                     'cell': {'lat': d['lat'], 'lng': d['lon'], 'size_m': ref.CELL}, 'edge': edge}

    def spot_decode(self, params):
        code = (params.get('code') or '').strip()
        if not code:
            raise ApiError(400, 'bad_request', 'The code parameter is required.')
        try:
            d = ref.decode_spot(code, self.reg.frames)
        except ValueError as e:
            c = 'check_mismatch' if 'check' in str(e) else 'invalid_code'
            raise ApiError(422 if c == 'check_mismatch' else 400, c, str(e)[:1].upper() + str(e)[1:] + '.')
        canon = ref.encode_spot(d['lat'], d['lon'], self.reg.frames[d['frame']])
        return 200, {'code': canon, 'bloc': canon[:6], 'frame': self.frame_json(self.reg.frames[d['frame']]),
                     'lat': d['lat'], 'lng': d['lon'], 'size_m': ref.CELL}

    def zones(self):
        fc = self.frame_counts()
        out = []
        for d in sorted(self.reg.frames):
            f = self.reg.frames[d]
            z = self.frame_json(f)
            z['areas'] = sum(1 for a in self.reg.areas if a.frame == d)
            z['codes'] = fc.get(f['key'], {}).get('total', 0)
            z['registry_file'] = f['key'] + '.csv.gz'
            out.append(z)
        return 200, {'count': len(out), 'zones': out}

    def _frame(self, key):
        f = self.reg.frame_by_key.get((key or '').upper())
        if f is None:
            raise ApiError(404, 'not_found', 'No zone %r. The zones are %s.' % (key, ', '.join(sorted(self.reg.frame_by_key))))
        return f

    def zone(self, key):
        f = self._frame(key)
        fc = self.frame_counts().get(f['key'], {})
        z = self.frame_json(f)
        z['counts'] = {s: fc.get(s, 0) for s in STATUSES + ('total',)}
        z['registry_file'] = f['key'] + '.csv.gz'
        z['areas'] = [self.area_json(a) for a in self.reg.areas if a.frame == f['digit']]
        return 200, z

    def zone_codes(self, key, params):
        f = self._frame(key)
        after = (params.get('after') or '').strip().upper()
        limit = _int(params, 'limit', 100, 1, 1000)
        with self._read() as c:
            rows = c.execute('SELECT %s FROM codes WHERE frame = ? AND machine > ? ORDER BY machine LIMIT ?'
                             % ','.join(store.q(x) for x in store.CODE_COLUMNS), (f['key'], after, limit + 1)).fetchall()
        more = len(rows) > limit
        rows = rows[:limit]
        codes = []
        for r in rows:
            rec = {}
            for col in store.CODE_COLUMNS:
                v = r[col]
                rec[col] = NUMERIC[col](v) if col in NUMERIC and v != '' else v
            codes.append(rec)
        return 200, {'zone': f['key'], 'after': after or None, 'count': len(codes),
                     'next': codes[-1]['machine'] if more and codes else None, 'codes': codes}

    def get_area(self, zone):
        a = self.reg.area(zone)
        if a is None:
            raise ApiError(404, 'not_found', 'No area %r. An area is written <frame digit>-<5 digits>, such as 0-00094.' % zone)
        return 200, self.area_json(a, full=True)

    def areas(self, params):
        name = (params.get('name') or '').strip()
        if not name:
            raise ApiError(400, 'bad_request', 'The name parameter is required: a plate name or an official name.')
        k = ref.normalise_name(name)
        hits = list(self.reg.families.get(k, []))
        via = None
        if not hits and k in self.reg.aliases:
            via = 'alias'
            hits = [a for a in self.reg.families.get(self.reg.aliases[k], [])
                    if ref.normalise_name(a.official_name or a.name) == k] or self.reg.families.get(self.reg.aliases[k], [])
        if not hits:
            hits = [a for a in self.reg.areas if a.official_name and ref.normalise_name(a.official_name) == k]
            via = 'official name' if hits else None
        hits = sorted(hits, key=lambda a: a.ref)
        return 200, {'name': name, 'matched_by': via or ('plate name' if hits else None), 'count': len(hits),
                     'areas': [self.area_json(a) for a in hits[:100]]}

    # ------------------------------------------------------------ writes

    def authorise(self, header):
        if not self.keys:
            raise ApiError(403, 'read_only', 'This deployment is read-only: it has not been designated to issue codes.')
        if not header or not header.startswith('Bearer '):
            raise ApiError(401, 'unauthorised', 'Send the issuing key as "Authorization: Bearer <key>".')
        h = key_hash(header[7:].strip())
        if h not in self.keys:
            raise ApiError(401, 'unauthorised', 'That issuing key is not valid here.')
        return h

    def issue(self, body, who):
        if not isinstance(body, dict):
            raise ApiError(400, 'bad_json', 'The body must be a JSON object: {"lat", "lng", "outline"?, "of"?}.')
        lat = _float(body, 'lat', -90, 90)
        lng = _float(body, 'lng', -180, 180)
        of = (body.get('of') or '').strip() if isinstance(body.get('of'), str) else ''
        outline = body.get('outline')
        if outline is not None and not (isinstance(outline, list) and all(
                isinstance(p, (list, tuple)) and len(p) == 2 and all(isinstance(x, (int, float)) for x in p) for p in outline)):
            raise ApiError(400, 'bad_request', 'outline is a list of [lng, lat] pairs.')
        with self.lock:
            since = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - 86400))
            n = self.writer.execute('SELECT count(*) FROM codes WHERE issued_by = ? AND issued_at >= ?', (who, since)).fetchone()[0]
            if n >= self.per_day:
                raise ApiError(429, 'rate_limited', 'This key has issued %d codes in the last 24 hours, its limit. Try again later.' % n)
            if self.reg.in_guinea(lat, lng) is None:
                raise ApiError(422, 'outside', 'That point is outside Guinea, so it cannot have a code.')
            ring, area_m2, per = None, 0.0, 0.0
            c = self.writer
            if not of:
                row, _ = self.code_at(c, lat, lng, engine.EXISTS_M)
                if row is not None:
                    raise ApiError(409, 'exists', 'This building already has its code: %s.' % row['home'], {'existing': self.card(row)})
                if outline and len(outline) >= 3:
                    ring = engine.open_ring(outline)
                    area_m2, per = engine.ring_area(ring), engine.ring_perimeter(ring)
                    if len(ring) < 3 or area_m2 < engine.MIN_AREA_M2 or area_m2 > engine.MAX_AREA_M2:
                        raise ApiError(422, 'bad_outline', "That outline is %.0f m², but a home's is between 6 m² and 2 ha." % area_m2)
                    hit = self._overlap(c, ring, area_m2)
                    if hit is not None:
                        raise ApiError(409, 'exists', 'This building already has its code: %s.' % hit['home'], {'existing': self.card(hit)})
            if of:
                p = engine.parse_machine(of)
                if p is not None and p[3] != p[4]:
                    raise ApiError(422, 'check_mismatch', 'The check digit of %s does not match: a digit is wrong or two are swapped.'
                                   % engine.machine_text(of))
                row = c.execute('SELECT * FROM codes WHERE machine = ?', (engine.machine_text(of),)).fetchone() if p else None
                if row is None:
                    raise ApiError(404, 'not_found', 'There is no code %s to add a door to.' % of)
                if engine.dist_door(float(row['entrance_lat']), float(row['entrance_lng']), lat, lng) > engine.DOOR_MAX_M:
                    raise ApiError(422, 'too_far', 'That door is more than 80 m from %s.' % row['home'])
                area = self.reg.area(row['zone'])
            else:
                area = self.reg.place_for(lat, lng)
            if area is None:
                raise ApiError(422, 'no_area', 'There is no place name for this point.')
            issued = [(r[0], r[1], r[2]) for r in c.execute('SELECT num, anchor_lat, anchor_lng FROM codes WHERE "zone" = ?', (area.ref,))]
            number, block = self.reg.insert(area, issued, lat, lng)
            if number is None:
                raise ApiError(409, 'area_full', '%s has used every number of its name.' % area.name)
            blocks = area.blocks + ([block] if block else [])
            forms = self.reg.forms(area, number)
            spot, _f = self.reg.spot(lat, lng)
            prof = engine.profile(area_m2 if ring else 0.0, per, bool(of))
            frame_key = self.reg.frames[area.frame]['key']
            at = store.now()
            rec = {'machine': forms['machine'], 'home': forms['remembered'], 'plate': forms['plate'], 'zone': area.ref,
                   'official_name': area.official_name, 'label': area.label, 'number': str(number),
                   'check': str(ref.home_check(area.name_id, number)), 'status': 'provisional', 'issued': 'on-demand',
                   'issued_at': at, 'entrance_lat': '%.7f' % lat, 'entrance_lng': '%.7f' % lng,
                   'entrance_kind': 'door' if of else 'centre', 'spot': spot, 'plus_code': engine.plus_code(lat, lng),
                   'class': prof['class'], 'use': prof['use'], 'kind': prof['kind'], 'structures': str(prof['structures']),
                   'floor_area_m2': '%.1f' % prof['floor_area_m2'], 'settlement': '', 'official_street': ''}
            try:
                c.execute('BEGIN IMMEDIATE')
                c.execute('INSERT INTO codes (%s, frame, name_id, num, lat, lng, anchor_lat, anchor_lng, street_key, outline, issued_by, changed) '
                          'VALUES (%s)' % (','.join(store.q(x) for x in store.CODE_COLUMNS), ','.join('?' * (len(store.CODE_COLUMNS) + 11))),
                          [rec[k] for k in store.CODE_COLUMNS] + [frame_key, area.name_id, number, lat, lng, lat, lng, None,
                                                                   json.dumps(ring) if ring else None, who, 1])
                self._index_point(c, rec['machine'], lat, lng)
                if block:
                    c.execute('UPDATE areas SET blocks = ? WHERE "zone" = ?', ('|'.join('%d-%d' % (lo, hi) for lo, hi in blocks), area.ref))
                    c.execute('INSERT INTO blocks_added VALUES (?, ?, ?, ?, ?)', (area.ref, block[0], block[1], at, who))
                c.execute('INSERT INTO changes VALUES (?, ?, ?, ?, ?, ?)', (at, rec['machine'], 'issued', None, 'provisional', who))
                self._bump(c, area.ref, None, 'provisional')
                c.execute('COMMIT')
            except sqlite3.IntegrityError:
                c.execute('ROLLBACK')
                raise ApiError(409, 'conflict', 'That number was taken at the same moment. Try again.')
            except Exception:
                if c.in_transaction:
                    c.execute('ROLLBACK')
                raise
            if block:
                self.reg.add_block(area, block)
            row = c.execute('SELECT * FROM codes WHERE machine = ?', (rec['machine'],)).fetchone()
            card = self.card(row)
        if block:
            card['new_block'] = {'lo': block[0], 'hi': block[1]}
        return 201, card

    def _overlap(self, c, ring, area_m2):
        """An issued compound that the new outline covers: a drawn outline that
        shares more than half of the smaller of the two, or a published
        compound whose entrance lies inside the new outline."""
        lats = [p[1] for p in ring]
        lngs = [p[0] for p in ring]
        clat, clng = (min(lats) + max(lats)) / 2, (min(lngs) + max(lngs)) / 2
        reach = engine.dist_m(min(lats), min(lngs), max(lats), max(lngs)) / 2 + 300
        rows = [r for r in self._rows(c, self._ids_near(c, clat, clng, reach)) if r['status'] != 'retired']
        for r in sorted(rows, key=lambda r: r['machine']):
            if r['outline']:
                other = json.loads(r['outline'])
                if engine.overlap_area(ring, other) > 0.5 * min(engine.ring_area(other), area_m2):
                    return r
            elif engine.in_ring(r['lng'], r['lat'], ring):
                return r
        return None

    def _index_point(self, c, machine, lat, lng, update=False):
        if self.spatial == 'rtree':
            if update:
                rid = c.execute('SELECT id FROM codes_rid WHERE machine = ?', (machine,)).fetchone()[0]
                c.execute('UPDATE codes_rtree SET min_lat = ?, max_lat = ?, min_lng = ?, max_lng = ? WHERE id = ?', (lat, lat, lng, lng, rid))
            else:
                cur = c.execute('INSERT INTO codes_rid (machine) VALUES (?)', (machine,))
                c.execute('INSERT INTO codes_rtree VALUES (?, ?, ?, ?, ?)', (cur.lastrowid, lat, lat, lng, lng))
        else:
            if update:
                c.execute('DELETE FROM codes_grid WHERE machine = ?', (machine,))
            c.execute('INSERT INTO codes_grid VALUES (?, ?)', (store.grid_cell(lat, lng), machine))

    def patch(self, machine, body, who):
        if not isinstance(body, dict) or not body:
            raise ApiError(400, 'bad_json', 'The body must be a JSON object with "status" and/or "entrance".')
        unknown = set(body) - {'status', 'entrance'}
        if unknown:
            raise ApiError(400, 'bad_request', 'Unknown field(s): %s. Only status and entrance can change.' % ', '.join(sorted(unknown)))
        p = engine.parse_machine(machine)
        if p is None:
            raise ApiError(400, 'invalid_code', '%r is not a machine form.' % machine)
        if p[3] != p[4]:
            raise ApiError(422, 'check_mismatch', 'The check digit of %s does not match.' % engine.machine_text(machine))
        m = engine.machine_text(machine)
        with self.lock:
            c = self.writer
            row = c.execute('SELECT * FROM codes WHERE machine = ?', (m,)).fetchone()
            if row is None:
                raise ApiError(404, 'not_issued', 'No code %s has been issued.' % m)
            if row['status'] == 'retired':
                raise ApiError(409, 'retired', '%s is retired. A retired code never changes and is never reused.' % m)
            sets, changes = {}, []
            new_status = body.get('status')
            if new_status is not None:
                if new_status not in STATUSES:
                    raise ApiError(422, 'bad_status', 'status is provisional, confirmed or retired.')
                if new_status != row['status']:
                    sets['status'] = new_status
                    changes.append(('status', row['status'], new_status))
            e = body.get('entrance')
            if e is not None:
                if not isinstance(e, dict):
                    raise ApiError(400, 'bad_request', 'entrance is {"lat", "lng", "kind"?}.')
                lat = _float(e, 'lat', -90, 90)
                lng = _float(e, 'lng', -180, 180)
                kind = e.get('kind') or 'gate'
                if kind not in engine.ENTRANCE_KINDS:
                    raise ApiError(422, 'bad_request', 'kind is one of %s.' % ', '.join(engine.ENTRANCE_KINDS))
                d = engine.dist_door(float(row['entrance_lat']), float(row['entrance_lng']), lat, lng)
                if d > engine.DOOR_MAX_M:
                    raise ApiError(422, 'too_far', 'The new entrance is %.0f m from the old one; an entrance moves at most 80 m.' % d)
                spot, f = self.reg.spot(lat, lng)
                if spot is None or self.reg.in_guinea(lat, lng) is None:
                    raise ApiError(422, 'outside', 'That point is outside Guinea.')
                old = '%s,%s' % (row['entrance_lat'], row['entrance_lng'])
                sets.update({'entrance_lat': '%.7f' % lat, 'entrance_lng': '%.7f' % lng, 'entrance_kind': kind, 'spot': spot,
                             'plus_code': engine.plus_code(lat, lng), 'lat': lat, 'lng': lng})
                changes.append(('entrance', old, '%.7f,%.7f %s' % (lat, lng, kind)))
            if sets:
                at = store.now()
                c.execute('BEGIN IMMEDIATE')
                try:
                    c.execute('UPDATE codes SET %s, changed = 1 WHERE machine = ?' % ', '.join('%s = ?' % store.q(k) for k in sets),
                              list(sets.values()) + [m])
                    if 'lat' in sets:
                        self._index_point(c, m, sets['lat'], sets['lng'], update=True)
                    for field, o, n in changes:
                        c.execute('INSERT INTO changes VALUES (?, ?, ?, ?, ?, ?)', (at, m, field, o, n, who))
                    if 'status' in sets:
                        self._bump(c, row['zone'], row['status'], sets['status'])
                    c.execute('COMMIT')
                except Exception:
                    c.execute('ROLLBACK')
                    raise
            row = c.execute('SELECT * FROM codes WHERE machine = ?', (m,)).fetchone()
            return 200, self.card(row)


class _Lease(object):
    def __init__(self, pool):
        self.pool = pool

    def __enter__(self):
        self.c = self.pool.get()
        return self.c

    def __exit__(self, *exc):
        self.pool.put(self.c)
        return False
