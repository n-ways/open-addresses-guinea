"""The register in force and the issuing rules (engine/SPEC.md sections 2, 4, 5.2 and 7).

Parsing, check digits, spot codes, plate names and the numbering curve come
from the reference engine (engine/reference/gn_codes.py). This module adds
what a running registry needs on top of it: the areas with their current
blocks, the name ranges' high-water marks, the area of a new compound and the
number it takes.

Coordinates are WGS 84 degrees. Outlines are rings of [lng, lat] pairs, as in
GeoJSON.
"""
import json
import math
import os
import re
import sys

REPO = os.environ.get('ADDRESSES_REPO') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE_DATA = os.path.join(REPO, 'engine', 'data')
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))

import gn_codes as ref  # noqa: E402

COUNTRY = 'GN'
COUNTRY_NAME = 'Guinea'
CREDIT = 'N-Ways Addressing for Guinea, © N-WAYS LIMITED (nways.ng)'
CREDIT_URL = 'https://github.com/n-ways/open-addresses-guinea'
SPEC = 'SPEC v1.0'

# Issuing limits (SPEC 7). The distances are those of the N-Ways issuer.
AT_FOUND_M = 12.0        # /v1/at: a code within this distance of the point is "found"
SPOT_FOUND_M = 15.0      # a spot code names a compound within this distance of its cell centre
EXISTS_M = 3.0           # a new compound within this distance of an issued one already has its code
DOOR_MAX_M = 80.0        # another door of a compound stands within this distance of its entrance
MIN_AREA_M2 = 6.0        # a drawn outline is a home's: 6 m² ...
MAX_AREA_M2 = 20000.0    # ... to 2 ha
MAX_NUMBER = ref.MAX_NUMBER

# Local plane for distances and areas at a compound's scale (metres per degree).
M_LAT = 110574.0
M_LON_EQ = 111320.0
ENTRANCE_KINDS = ('gate', 'door', 'shopfront', 'landing', 'service', 'centre')


def hypot(p, q):
    """math.Hypot as the N-Ways issuer computes it, so that equal distances tie
    in the same way (the nearest-locality rule compares distances exactly)."""
    p, q = abs(p), abs(q)
    if p < q:
        p, q = q, p
    if p == 0:
        return 0.0
    q = q / p
    return p * math.sqrt(1 + q * q)


def dist_plane(lat1, lon1, lat2, lon2):
    """Distance in metres on the local plane at the second point's latitude."""
    return hypot((lat1 - lat2) * M_LAT, (lon1 - lon2) * M_LON_EQ * math.cos(lat2 * math.pi / 180))


def dist_door(lat1, lng1, lat2, lng2):
    """Distance in metres used for the door and entrance-move limits."""
    dy = (lat2 - lat1) * 111320
    dx = (lng2 - lng1) * 111320 * math.cos((lat1 + lat2) / 2 * math.pi / 180)
    return hypot(dx, dy)


def dist_m(lat1, lng1, lat2, lng2):
    """Ground distance in metres (haversine on the mean Earth radius)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371008.8 * math.asin(min(1.0, math.sqrt(a)))


# ---------------------------------------------------------------- outlines

def open_ring(ring):
    """A ring without its closing vertex."""
    ring = [(float(p[0]), float(p[1])) for p in ring]
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    return ring


def ring_area(ring):
    """Area in m² of a ring of (lng, lat) on the local plane at its first vertex."""
    if len(ring) < 3:
        return 0.0
    k = math.cos(ring[0][1] * math.pi / 180)
    a = 0.0
    for i in range(len(ring)):
        j = (i + 1) % len(ring)
        xi, yi = ring[i][0] * M_LON_EQ * k, ring[i][1] * M_LAT
        xj, yj = ring[j][0] * M_LON_EQ * k, ring[j][1] * M_LAT
        a += xi * yj - xj * yi
    return abs(a) / 2


def ring_perimeter(ring):
    per = 0.0
    for i in range(len(ring)):
        j = (i + 1) % len(ring)
        per += dist_door(ring[i][1], ring[i][0], ring[j][1], ring[j][0])
    return per


def in_ring(lng, lat, ring):
    return ref._in_ring(lng, lat, ring)


def _signed2(ring):
    return sum(ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1] for i in range(len(ring)))


def _triangles(ring):
    """Ear-clipping triangulation of a simple polygon."""
    pts = list(ring)
    if _signed2(pts) < 0:
        pts.reverse()
    idx = list(range(len(pts)))
    out = []

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    guard = 0
    while len(idx) > 3 and guard < 10000:
        guard += 1
        cut = False
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = pts[i0], pts[i1], pts[i2]
            if cross(a, b, c) <= 0:
                continue
            if any(cross(a, b, pts[j]) >= 0 and cross(b, c, pts[j]) >= 0 and cross(c, a, pts[j]) >= 0
                   for j in idx if j not in (i0, i1, i2)):
                continue
            out.append((a, b, c))
            idx.pop(k)
            cut = True
            break
        if not cut:
            break
    if len(idx) == 3:
        out.append(tuple(pts[i] for i in idx))
    return out


def _clip(subject, tri):
    """Sutherland-Hodgman: the part of a polygon inside a counter-clockwise triangle."""
    out = list(subject)
    for i in range(3):
        a, b = tri[i], tri[(i + 1) % 3]
        inp, out = out, []
        if not inp:
            break

        def inside(p):
            return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0]) >= 0

        def meet(p, q):
            x1, y1, x2, y2 = p[0], p[1], q[0], q[1]
            x3, y3, x4, y4 = a[0], a[1], b[0], b[1]
            d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
            if d == 0:
                return q
            t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / d
            return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))

        for j in range(len(inp)):
            p, q = inp[j - 1], inp[j]
            if inside(q):
                if not inside(p):
                    out.append(meet(p, q))
                out.append(q)
            elif inside(p):
                out.append(meet(p, q))
    return out


def overlap_area(r1, r2):
    """Area in m² shared by two simple rings of (lng, lat)."""
    if len(r1) < 3 or len(r2) < 3:
        return 0.0
    lat0 = r1[0][1]
    k = math.cos(lat0 * math.pi / 180)

    def plane(r):
        return [(p[0] * M_LON_EQ * k, p[1] * M_LAT) for p in r]

    a, b = plane(r1), plane(r2)
    total = 0.0
    for t in _triangles(b):
        part = _clip(a, t)
        if len(part) >= 3:
            total += abs(_signed2(part)) / 2
    return total


def ring_distance_m(lat, lng, ring):
    """Distance from a point to a ring (0 inside)."""
    if in_ring(lng, lat, ring):
        return 0.0
    k = math.cos(lat * math.pi / 180)
    best = float('inf')
    for i in range(len(ring)):
        a, b = ring[i - 1], ring[i]
        d = ref._seg_dist(lng * M_LON_EQ * k, lat * M_LAT, a[0] * M_LON_EQ * k, a[1] * M_LAT, b[0] * M_LON_EQ * k, b[1] * M_LAT)
        best = min(best, d)
    return best


# ---------------------------------------------------------------- Open Location Code

_OLC = '23456789CFGHJMPQRVWX'


def plus_code(lat, lng):
    """The 11-character Open Location Code of a point, as the registry gives it."""
    def r6(x):
        return round(x * 1e6) / 1e6
    lat = min(max(lat, -90.0), 90.0)
    lng = math.fmod(math.fmod(lng + 180, 360) + 360, 360) - 180
    lat_v = int(math.floor(r6((lat + 90) * 25000000)))
    lng_v = int(math.floor(r6((lng + 180) * 8192000)))
    if lat_v >= 180 * 25000000:
        lat_v = 180 * 25000000 - 1
    code = ''
    for _ in range(5):
        code = _OLC[(lat_v % 5) * 4 + lng_v % 4] + code
        lat_v //= 5
        lng_v //= 4
    for _ in range(5):
        code = _OLC[lng_v % 20] + code
        code = _OLC[lat_v % 20] + code
        lat_v //= 20
        lng_v //= 20
    return code[:8] + '+' + code[8:11]


# ---------------------------------------------------------------- machine form

MACHINE_RE = re.compile(r'^GN-(\d{5})-(\d{4,5})(?:\.(\d{1,2}))?-(\d)$')
MACHINE_SHAPE = re.compile(r'^GN-?\d')


def machine_text(text):
    return re.sub(r'\s+', '', (text or '').strip()).upper()


def parse_machine(text):
    """(name id, number, structure, check given, check expected) of a machine form, or None."""
    m = MACHINE_RE.match(machine_text(text))
    if not m:
        return None
    nid, num = int(m.group(1)), int(m.group(2))
    sub = int(m.group(3)) if m.group(3) else None
    if m.group(3) and m.group(3)[0] == '0':
        return None
    return nid, num, sub, int(m.group(4)), ref.home_check(nid, num, sub)


def looks_spot(text):
    s = re.sub(r'[\s-]', '', (text or '').upper())
    return bool(re.match(r'^[0-4][23456789CFGHJMPQRVWX]{8}[23456789CFGHJMPQRVWX]?$', s))


# ---------------------------------------------------------------- the register

class Area(object):
    __slots__ = ('ref', 'frame', 'index', 'aid', 'name', 'official_name', 'kind', 'label', 'name_key', 'name_id',
                 'blocks', 'needs_council_choice', 'lat', 'lon', 'lat_text', 'lon_text')

    def in_blocks(self, n):
        return any(lo <= n <= hi for lo, hi in self.blocks)

    def blocks_text(self):
        return '|'.join('%d-%d' % (lo, hi) for lo, hi in self.blocks)

    def place_line(self):
        """What is shown beside a code: the commune in Kaloum, Dixinn and Matam,
        Conakry elsewhere in the capital, else the préfecture."""
        if self.label in ('Kaloum', 'Dixinn', 'Matam'):
            return self.label + ', Conakry'
        if self.label == '':
            return 'Conakry' if self.frame == 0 else 'Guinée'
        return self.label


def parse_blocks(text):
    out = []
    for part in (text or '').split('|'):
        if part:
            lo, hi = part.split('-')
            out.append([int(lo), int(hi)])
    return out


class Register(object):
    """Frames, areas with their current blocks, aliases, name ids and the
    high-water marks of the name ranges."""

    def __init__(self, area_rows, data_dir=None):
        data_dir = data_dir or ENGINE_DATA
        with open(os.path.join(data_dir, 'register.json'), encoding='utf-8') as f:
            reg = json.load(f)
        self.frames_path = os.path.join(data_dir, 'frames.geojson')
        self.quartiers_path = os.path.join(data_dir, 'quartiers.geojson')
        self.border = ref.Border(os.path.join(data_dir, 'border.geojson'))
        self.frames = {f['digit']: f for f in reg['frames']}
        self.frame_by_key = {f['key']: f for f in reg['frames']}
        self.aliases = reg.get('aliases', {})
        self.next_free = reg.get('nextFree', {})
        precise = {a['aid']: (a['lat'], a['lon']) for a in reg['areas']}
        self.areas = []
        self.by_ref, self.by_aid, self.families, self.ids = {}, {}, {}, dict(reg.get('ids', {}))
        for r in area_rows:
            a = Area()
            a.ref, a.frame, a.index, a.aid = r['zone'], int(r['frame']), int(r['index']), r['area_id']
            a.name, a.official_name, a.kind, a.label = r['plate_name'], r['official_name'], r['kind'], r['label']
            a.name_key, a.name_id = r['name_key'], int(r['name_id'])
            a.blocks = parse_blocks(r['blocks'])
            a.needs_council_choice = r['needs_council_choice'] == 'true'
            a.lat_text, a.lon_text = r['lat'], r['lon']
            a.lat, a.lon = precise.get(a.aid, (float(r['lat']), float(r['lon'])))
            self.areas.append(a)
            self.by_ref[a.ref] = a
            self.by_aid[a.aid] = a
            self.families.setdefault(a.name_key, []).append(a)
            self.ids.setdefault(a.name_key, a.name_id)
        self.areas.sort(key=lambda a: a.ref)
        self.key_of = {v: k for k, v in self.ids.items()}
        self._quartiers = None
        self._names = None

    # -- lookups

    def area(self, ref_):
        return self.by_ref.get(ref_)

    def frame_of(self, lat, lng):
        """The frame of a point, or None abroad or at sea (SPEC 2)."""
        try:
            return ref.frame_of(lat, lng, self.frames, self.frames_path)
        except ValueError:
            return None

    def in_guinea(self, lat, lng):
        """The frame of a point that may have a code, or None: in no frame (SPEC 2), or
        more than 300 m outside the national border whatever the frames say (SPEC 2.1)."""
        f = self.frame_of(lat, lng)
        if f is None or not self.border.holds(lat, lng):
            return None
        return f

    def owner(self, name_key, number):
        for a in self.families.get(name_key, ()):
            if a.in_blocks(number):
                return a
        return None

    def high_water(self, name_key):
        """The first number after every block of a name: its next block starts here."""
        top = self.next_free.get(name_key) or 1000
        for a in self.families.get(name_key, ()):
            for lo, hi in a.blocks:
                top = max(top, hi + 1)
        return top

    def names(self):
        """The national name table in the shape the reference decoder reads."""
        if self._names is None:
            out = {}
            for key, fam in self.families.items():
                out[key] = {'id': self.ids[key], 'key': key, 'blocks': [
                    {'name': a.name, 'officialName': a.official_name or a.name, 'aid': a.aid, 'frame': a.frame,
                     'lat': a.lat, 'lon': a.lon, 'zone': a.ref, 'label': a.label, 'blocks': [list(b) for b in a.blocks]}
                    for a in fam]}
            out['@aliases'] = self.aliases
            self._names = out
        return self._names

    def plate_key(self, text):
        """The name key of a plate name, or of an official name that points to one."""
        k = ref.normalise_name(text)
        if k in self.families:
            return k
        return self.aliases.get(k, k)

    # -- the area of a new compound (SPEC 4.1)

    def _load_quartiers(self):
        if self._quartiers is None:
            with open(self.quartiers_path, encoding='utf-8') as f:
                fc = json.load(f)
            out = []
            for feat in fc['features']:
                g = feat['geometry']
                polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
                for p in polys:
                    if not p:
                        continue
                    xs = [c[0] for c in p[0]]
                    ys = [c[1] for c in p[0]]
                    out.append((feat['properties']['qid'], (min(xs), min(ys), max(xs), max(ys)), p))
            self._quartiers = out
        return self._quartiers

    def quartier_at(self, lat, lng):
        """The official quartier holding a point, by its area id, or None."""
        best = None
        for qid, box, p in self._load_quartiers():
            if not (box[0] <= lng <= box[2] and box[1] <= lat <= box[3]):
                continue
            if in_ring(lng, lat, p[0]) and not any(in_ring(lng, lat, h) for h in p[1:]):
                if best is None or qid < best:
                    best = qid
        return best

    def place_for(self, lat, lng):
        """The area a new compound takes: the official quartier holding it, else
        the nearest locality."""
        q = self.quartier_at(lat, lng)
        if q and q in self.by_aid:
            return self.by_aid[q]
        best, bd = None, float('inf')
        for a in self.areas:
            if a.kind != 'locality':
                continue
            d = dist_plane(a.lat, a.lon, lat, lng)
            if d < bd or (d == bd and best is not None and a.aid < best.aid):
                best, bd = a, d
        return best

    # -- numbering (SPEC 4.2 step 4 and SPEC 7)

    def insert(self, area, issued, lat, lng):
        """The number of a new compound in an area. issued: [(number, lat, lng)]
        of every code of the area, retired ones included (a number is never
        reused). Tries the area's blocks in turn, then opens an extension block
        at the name's high-water mark. Returns (number, new block or None), or
        (None, None) when the name has no room below 100,000."""
        frame = self.frames[area.frame]
        for lo, hi in area.blocks:
            inside = [(n, la, lo_) for n, la, lo_ in issued if lo <= n <= hi]
            n, _why = ref.reserve_number(lat, lng, inside, (lo, hi), frame)
            if n is not None:
                return n, None
        size = ref.block_size(len(issued) + 1)
        start = self.high_water(area.name_key)
        if start + size - 1 > MAX_NUMBER:
            return None, None
        return start + size // 2, [start, start + size - 1]

    def add_block(self, area, block):
        area.blocks.append(list(block))
        self._names = None

    # -- forms (SPEC 4.3, 4.4)

    def forms(self, area, number):
        return {
            'remembered': ref.remembered(area.name, number),
            'written': '%s · %d' % (area.name, number),
            'plate': '%s · %d' % (area.name.upper(), number),
            'spoken': ref.spoken(area.name, number),
            'machine': ref.machine_form(area.name_id, number),
        }

    def spot(self, lat, lng):
        """(spot code, frame) of a point by SPEC 3.4, or (None, None) abroad or at sea."""
        code, f, _edge = self.spot_edge(lat, lng)
        return code, f

    def spot_edge(self, lat, lng):
        """(spot code, frame, edge) by SPEC 3.4: edge is True when the point lies beyond
        every grid within reach and takes its frame's nearest edge cell."""
        try:
            return ref.spot_of(lat, lng, self.frames, self.frames_path)
        except ValueError:
            return None, None, False


def round1(x):
    return round(x * 10) / 10


def profile(outline_area, outline_perimeter, door):
    """The building profile of a compound issued on request (SPEC 6): one
    residential structure when an outline is given, none otherwise."""
    if outline_area > 0:
        fa = round1(round1(outline_area))   # the structure's floor area (one floor), then the compound's sum
        return {'class': 'residential.house', 'use': 'residential', 'kind': 'door' if door else 'building',
                'structures': 1, 'floor_area_m2': fa}
    return {'class': '', 'use': 'residential', 'kind': 'door' if door else 'building', 'structures': 0, 'floor_area_m2': 0.0}
