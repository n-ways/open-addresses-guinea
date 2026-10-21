#!/usr/bin/env python3
"""N-Ways Guinea address codes: reference engine (standard library only).

Guinea's own engine (engine/SPEC.md); nothing here is shared with another
country.

  python3 engine/reference/gn_codes.py test             test vectors + check proofs
  python3 engine/reference/gn_codes.py encode LAT LON   spot code
  python3 engine/reference/gn_codes.py decode CODE      centre of a spot code's cell
  python3 engine/reference/gn_codes.py bloc LAT LON     the 1.2 km bloc code (code de bloc)
  python3 engine/reference/gn_codes.py home NAME NUMBER   decode a home code nationally (no frame needed)

Codes:
  home code   Hafia 3 · 1230        (plate name + number; unique in all Guinea; remembered)
  plate       HAFIA 3 · 1230        (the same, as painted on the gate)
  machine     GN-<name id>-1230-d   (adds the Damm digit over national name id + number; systems only)
  spot        0 22JV PVQQ            (region digit, bloc, point; an older code's check is still verified)
  bloc        0 22JV                 (the 1.2 km square: Guinea's postcode-like unit)
"""
import json, math, os, sys

ALPHABET = '23456789CFGHJMPQRVWX'
VAL = {c: i for i, c in enumerate(ALPHABET)}
CELL = 3.0           # metres
PER = 20             # cells per carré side, carrés per bloc side ... (each character is one row or one column of 20)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))


def m_per_deg_lat(phi):
    p = math.radians(phi)
    return 111132.954 - 559.822 * math.cos(2 * p) + 1.175 * math.cos(4 * p)


def m_per_deg_lon(phi):
    p = math.radians(phi)
    return 111412.84 * math.cos(p) - 93.5 * math.cos(3 * p) + 0.118 * math.cos(5 * p)


def load_frames(path=None):
    with open(path or os.path.join(REPO, 'model', 'frames.json'), encoding='utf-8') as f:
        d = json.load(f)
    return {f['digit']: f for f in d['frames']}


# ---------------------------------------------------------------- check character over Z5 x Z2 x Z2

def _sig(e, k):
    x, y = e
    for _ in range(k % 12):
        x = 2 * x % 5
        y = ((y & 1) << 1) | (((y >> 1) & 1) ^ (y & 1))
    return x, y


def check_char(values):
    sx, sy = 0, 0
    for i, v in enumerate(values, 1):
        x, y = _sig((v % 5, v // 5), i)
        sx, sy = (sx + x) % 5, sy ^ y
    target = ((-sx) % 5, sy)
    n1 = len(values) + 1
    for v in range(20):
        if _sig((v % 5, v // 5), n1) == target:
            return ALPHABET[v]
    raise AssertionError


# ---------------------------------------------------------------- spot grid: frame -> bloc (1.2 km) -> point (3 m)

def _grid(frame):
    dlat = CELL / m_per_deg_lat(frame['refLat'])
    dlon = CELL / m_per_deg_lon(frame['refLat'])
    return frame['south'], frame['west'], dlat, dlon


def _cell(lat, lon, frame):
    """(row, col) of a point in a frame's grid; either may fall outside 0 .. 159,999."""
    s, w, dlat, dlon = _grid(frame)
    return math.floor((lat - s) / dlat), math.floor((lon - w) / dlon)


def _beyond(row, col):
    """Cells by which (row, col) lies outside the grid on the worse axis (0 inside)."""
    side = PER ** 4
    return max(0, -row, row - (side - 1), -col, col - (side - 1))


def _encode_cell(row, col, frame):
    # bloc = cell // 400 (rows and cols), then secteur/bloc digits; point = cell % 400, then carré/point digits
    br, bc, pr, pc = row // 400, col // 400, row % 400, col % 400
    vals = [br // 20, bc // 20, br % 20, bc % 20, pr // 20, pc // 20, pr % 20, pc % 20]
    body = ''.join(ALPHABET[v] for v in vals)
    # No check character is written, so there is nothing extra to read or type;
    # parse_spot still verifies one when an older code carries it.
    return f"{frame['digit']} {body[:4]} {body[4:]}"


def encode_spot(lat, lon, frame):
    """The spot code of a point in a frame's grid (SPEC 3.2); ValueError when the grid does not hold it."""
    row, col = _cell(lat, lon, frame)
    if _beyond(row, col):                    # 160,000 cells = 480 km a side
        raise ValueError('point outside the frame')
    return _encode_cell(row, col, frame)


def bloc_code(lat, lon, frame):
    return encode_spot(lat, lon, frame)[:6]


def parse_spot(code, frames):
    s = code.upper().replace(' ', '').replace('-', '')
    if len(s) not in (9, 10) or not s[0].isdigit() or int(s[0]) not in frames:
        raise ValueError('a spot code is a region digit 0-4 and 8 grid characters')
    for ch in s[1:]:
        if ch not in VAL:
            raise ValueError(f'character {ch!r} is not in the code alphabet')
    d = int(s[0])
    vals = [VAL[ch] for ch in s[1:9]]
    if len(s) == 10 and check_char([d] + vals) != s[9]:
        raise ValueError('check character does not match: a character is wrong or two are swapped')
    return frames[d], vals


def decode_spot(code, frames):
    f, v = parse_spot(code, frames)
    s, w, dlat, dlon = _grid(f)
    row = (v[0] * 20 + v[2]) * 400 + v[4] * 20 + v[6]
    col = (v[1] * 20 + v[3]) * 400 + v[5] * 20 + v[7]
    return {'frame': f['digit'], 'region': f['name'], 'lat': round(s + (row + 0.5) * dlat, 7),
            'lon': round(w + (col + 0.5) * dlon, 7), 'cellMetres': CELL}


# ---------------------------------------------------------------- which frame (offline lookup)

def _in_ring(x, y, ring):
    inside, j = False, len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]; xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


_SHAPES = {}


def _frame_shapes(path):
    if path not in _SHAPES:
        out = []
        with open(path, encoding='utf-8') as fh:
            features = json.load(fh)['features']
        for f in features:
            g = f['geometry']
            for p in (g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]):
                xs = [c[0] for c in p[0]]; ys = [c[1] for c in p[0]]
                out.append((f['properties']['digit'], (min(xs), min(ys), max(xs), max(ys)), p))
        _SHAPES[path] = out
    return _SHAPES[path]


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    t = 0.0
    l2 = dx * dx + dy * dy
    if l2 > 0:
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def frame_of(lat, lon, frames, shapes=None):
    """The frame of a point (SPEC 2): inside a frozen outline (the lowest digit first, so
    Conakry before the Basse-Guinée outline around it), else the nearest outline within
    0.01 degrees (about 1.1 km: an islet, a sliver between outlines). Abroad: ValueError."""
    sh = _frame_shapes(shapes or os.path.join(REPO, 'model', 'frames.geojson'))
    inside = [d for d, b, p in sh if b[0] <= lon <= b[2] and b[1] <= lat <= b[3]
              and _in_ring(lon, lat, p[0]) and not any(_in_ring(lon, lat, h) for h in p[1:])]
    if inside:
        return frames[min(inside)]
    best, bd = None, 0.01
    for d, b, p in sh:
        if not (b[0] - 0.01 <= lon <= b[2] + 0.01 and b[1] - 0.01 <= lat <= b[3] + 0.01):
            continue
        for ring in p:
            for k in range(1, len(ring)):
                dist = _seg_dist(lon, lat, ring[k - 1][0], ring[k - 1][1], ring[k][0], ring[k][1])
                if dist < bd:
                    best, bd = d, dist
    if best is None:
        raise ValueError('point is not in Guinea')
    return frames[best]


OUTLINE_DEG = 0.01      # SPEC 2: a point in no outline belongs to the nearest outline within this distance
EDGE_CELLS = 350        # SPEC 3.4: no point within OUTLINE_DEG of an outline lies further beyond its frame's grid


def _near_outlines(lat, lon, shapes=None):
    """{digit: distance in degrees (SPEC 2) to the frame's nearest outline}, for outlines within OUTLINE_DEG."""
    sh = _frame_shapes(shapes or os.path.join(REPO, 'model', 'frames.geojson'))
    out = {}
    for d, b, p in sh:
        if not (b[0] - OUTLINE_DEG <= lon <= b[2] + OUTLINE_DEG and b[1] - OUTLINE_DEG <= lat <= b[3] + OUTLINE_DEG):
            continue
        for ring in p:
            for k in range(1, len(ring)):
                dist = _seg_dist(lon, lat, ring[k - 1][0], ring[k - 1][1], ring[k][0], ring[k][1])
                if dist < OUTLINE_DEG and dist < out.get(d, OUTLINE_DEG):
                    out[d] = dist
    return out


def spot_of(lat, lon, frames, shapes=None):
    """The spot code of a point anywhere in Guinea (SPEC 3.4): (code, frame, edge).
    The frame of SPEC 2 when its grid holds the point; else, among the frames whose
    outline lies within 0.01 degrees and whose grid holds the point, the one with the
    nearest outline (ties to the lower digit); else the nearest edge cell of the SPEC 2
    frame's grid (edge True; never more than EDGE_CELLS away). Abroad: ValueError."""
    f = frame_of(lat, lon, frames, shapes)
    row, col = _cell(lat, lon, f)
    if not _beyond(row, col):
        return _encode_cell(row, col, f), f, False
    near = sorted((dist, d) for d, dist in _near_outlines(lat, lon, shapes).items()
                  if d != f['digit'] and not _beyond(*_cell(lat, lon, frames[d])))
    if near:
        g = frames[near[0][1]]
        return _encode_cell(*_cell(lat, lon, g), g), g, False
    if _beyond(row, col) > EDGE_CELLS:
        raise ValueError('point more than %d cells beyond its frame' % EDGE_CELLS)
    side = PER ** 4
    return _encode_cell(min(side - 1, max(0, row)), min(side - 1, max(0, col)), f), f, True


# ---------------------------------------------------------------- the national border (SPEC 2.1)

BORDER_FILE = os.path.join(REPO, 'engine', 'data', 'border.geojson')
BORDER_M = 300.0        # how far outside the national border an entrance may lie


class Border:
    """The national border (engine/data/border.geojson): OpenStreetMap's
    admin_level=2 boundary of Guinea, simplified (tools/border.py). A building
    more than BORDER_M outside it is in a neighbouring country and never has a
    code, whatever the frame outlines say. The file records the largest
    distance between the simplified line and the true one (maxDeviationM); the
    limit applied here is BORDER_M less that deviation, rounded up, so nothing
    it accepts lies more than BORDER_M outside the true border.

    Distances are measured on the local plane at the point (m_per_deg_lat and
    m_per_deg_lon at its latitude), exact to well under a metre at 300 m."""

    CELL = 0.01         # degrees: the grid of the segment index

    def __init__(self, path=None, limit_m=None):
        with open(path or BORDER_FILE, encoding='utf-8') as fh:
            gj = json.load(fh)
        props = gj.get('properties') or {}
        geom = gj['geometry'] if gj.get('type') == 'Feature' else gj
        polys = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
        self.deviation = float(props.get('maxDeviationM', 0.0))
        self.limit = float(limit_m) if limit_m is not None else BORDER_M - math.ceil(self.deviation)
        self.segs = []
        for poly in polys:
            for ring in poly:
                pts = [(float(x), float(y)) for x, y in ring]
                if len(pts) > 1 and pts[0] == pts[-1]:
                    pts = pts[:-1]
                for i in range(len(pts)):
                    self.segs.append((pts[i - 1], pts[i]))
        c = self.CELL
        top = max(abs(y) for s in self.segs for _, y in s) + 0.1
        self.pad_lat = self.limit / m_per_deg_lat(0.0)          # degrees of latitude in the limit, at most
        self.pad_lon = self.limit / m_per_deg_lon(top)          # degrees of longitude in the limit, at most
        self.bands = {}     # latitude band -> segments crossing it (inside test)
        self.cells = {}     # grid cell -> segments within the limit of it (distance)
        for k, ((ax, ay), (bx, by)) in enumerate(self.segs):
            for b in range(int(math.floor(min(ay, by) / c)), int(math.floor(max(ay, by) / c)) + 1):
                self.bands.setdefault(b, []).append(k)
            for gx in range(int(math.floor((min(ax, bx) - self.pad_lon) / c)), int(math.floor((max(ax, bx) + self.pad_lon) / c)) + 1):
                for gy in range(int(math.floor((min(ay, by) - self.pad_lat) / c)), int(math.floor((max(ay, by) + self.pad_lat) / c)) + 1):
                    self.cells.setdefault((gx, gy), []).append(k)

    def inside(self, lat, lon):
        """True for a point inside the border itself."""
        inside = False
        for k in self.bands.get(int(math.floor(lat / self.CELL)), ()):
            (ax, ay), (bx, by) = self.segs[k]
            if (ay > lat) != (by > lat) and lon < (bx - ax) * (lat - ay) / (by - ay) + ax:
                inside = not inside
        return inside

    def outside_m(self, lat, lon):
        """0 inside the border; else the metres to it, or infinity beyond the limit."""
        if self.inside(lat, lon):
            return 0.0
        kx, ky = m_per_deg_lon(lat), m_per_deg_lat(lat)
        best = math.inf
        for k in self.cells.get((int(math.floor(lon / self.CELL)), int(math.floor(lat / self.CELL))), ()):
            (ax, ay), (bx, by) = self.segs[k]
            best = min(best, _seg_dist(0.0, 0.0, (ax - lon) * kx, (ay - lat) * ky, (bx - lon) * kx, (by - lat) * ky))
        return best if best <= self.limit else math.inf

    def holds(self, lat, lon):
        """True for a point inside the border or within the limit of it."""
        return self.outside_m(lat, lon) <= self.limit


# ---------------------------------------------------------------- home codes (remembered): national names

# "Name NNNN" must decode to exactly one place in Guinea, with no frame,
# commune or préfecture. Every area whose name normalises to the same key
# draws its numbers from ONE national range for that name, split into frozen
# blocks (one per area, with spare room). The Damm digit covers the national
# name id and the number; the number's block identifies the area.

import re as _re
import unicodedata as _ud

DAMM = [
    [0, 3, 1, 7, 5, 9, 8, 6, 4, 2], [7, 0, 9, 2, 1, 5, 4, 8, 6, 3], [4, 2, 0, 6, 8, 7, 1, 3, 5, 9],
    [1, 7, 5, 0, 9, 8, 3, 4, 2, 6], [6, 1, 2, 3, 0, 4, 5, 9, 7, 8], [3, 6, 7, 4, 2, 0, 9, 5, 8, 1],
    [5, 8, 6, 9, 7, 2, 0, 1, 3, 4], [8, 9, 4, 5, 3, 6, 2, 0, 1, 7], [9, 4, 3, 8, 6, 1, 7, 2, 0, 5],
    [2, 5, 8, 1, 4, 3, 6, 7, 9, 0]]
BLOCK_STEP = 50          # blocks are multiples of 50 numbers
HEADROOM = 2.0           # each block holds twice today's compounds
RANGES = {4: (1000, 9000), 5: (10000, 90000)}   # (first number, how many numbers)
MAX_NUMBER = 99999       # a name's later blocks continue past its range, never past 5 digits
HILBERT_ORDER = 18       # numbering curve over a frame's 3 m grid (160,000 cells a side < 2^18)


def damm(s):
    i = 0
    for ch in s:
        i = DAMM[i][int(ch)]
    return i


_CONFUSABLE = str.maketrans('АВСЕНКМОРТХаеорсухк', 'ABCEHKMOPTXaeopcyxk')   # Cyrillic look-alikes in map names ("Сondetta")


def normalise_name(s):
    """Spelling-insensitive key: no accents or case, hyphens/apostrophes/
    underscores as spaces, a number glued to a word split off ("Soro2" =
    "Soro 2"), Cyrillic look-alike letters read as Latin, the saint
    abbreviations expanded (St/Ste -> Saint/Sainte), doubled letters single,
    and the usual variants merged (Hafiya→Hafia, Missidé→Miside,
    Tannérie→Tanerie, Dankharan→Dankaran). A trailing number stays part of
    the name ("Hafia 3" ≠ "Hafia")."""
    s = (s or '').translate(_CONFUSABLE)
    s = ''.join(c for c in _ud.normalize('NFKD', s) if not _ud.combining(c)).lower()
    s = _re.sub(r"[-_'’.,/()]+", ' ', s)
    s = _re.sub(r'(?<=[a-z])(?=\d)|(?<=\d)(?=[a-z])', ' ', s)
    s = _re.sub(r'\s+', ' ', s).strip()
    s = _re.sub(r'^(quartier|village|secteur|district|cite) ', '', s)
    s = _re.sub(r'\bste\b', 'sainte', _re.sub(r'\bst\b', 'saint', s))
    s = s.replace('iya', 'ia').replace('kh', 'k')
    return _re.sub(r'(.)\1', r'\1', s)


# ---------------------------------------------------------------- plate names (the remembered name)

sys.path.insert(0, HERE)
import plate_names as _pn  # noqa: E402

PLATE_LANG = 'fr'
_NUMBERED = _re.compile(r'^(.*?\D)\s*(\d{1,2})$')


def split_quartier_number(name):
    """'Hafia 3' -> ('Hafia', '3'); 'Soro2' -> ('Soro', '2'); 'Kaloum' -> ('Kaloum', None)."""
    m = _NUMBERED.match((name or '').strip())
    return (m.group(1).strip(), m.group(2)) if m else ((name or '').strip(), None)


def plate_fits(name):
    """A plate name is at most 12 characters (letters, spaces, hyphens and
    apostrophes; an accented letter is one) and at most 2 words, linking
    words (de, du, des, la, es...) not counted. A quartier's own number
    ("Hafia 3") counts in the 12 characters but not as a word; no other
    digit is allowed."""
    base, num = split_quartier_number(name)
    return (_pn.plate_length(name) <= _pn.MAX_CHARS and _pn.word_count(base, PLATE_LANG) <= _pn.MAX_WORDS
            and not _re.search(r'\d', base))


def block_size(compounds):
    return max(BLOCK_STEP, math.ceil(HEADROOM * compounds / BLOCK_STEP) * BLOCK_STEP)


def allocate(areas_of_name):
    """Blocks for all areas sharing one normalised name, in the given (frozen)
    order. Returns digits, first number, and [(area, start, size)];
    None if the name needs a qualifier (more than 90,000 numbers)."""
    need = sum(block_size(a['compounds']) for a in areas_of_name)
    for digits in (4, 5):
        first, count = RANGES[digits]
        if need <= count:
            out, at = [], first
            for a in areas_of_name:
                size = block_size(a['compounds'])
                out.append((a, at, size))
                at += size
            return {'digits': digits, 'first': first, 'end': first + count, 'nextFree': at, 'blocks': out}
    return None


def home_check(name_id, number, structure=None):
    """Damm digit over the name's national id (5 digits), the number and, for a
    structure of a compound, its structure number."""
    return damm(f'{name_id:05d}{number}' + (str(structure) if structure else ''))


def machine_form(name_id, number, structure=None):
    sub = f'.{structure}' if structure else ''
    return f'GN-{name_id:05d}-{number}{sub}-{home_check(name_id, number, structure)}'


def remembered(name, number, structure=None):
    """'Kalouma 1260'; a name ending in a number takes a '·': 'Hafia 3 · 1230'."""
    sep = ' · ' if _re.search(r'\d$', name) else ' '
    return f'{name}{sep}{number}' + (f'.{structure}' if structure else '')


def plate(name, number, structure=None):
    """What the plate carries: 'HAFIA 3 · 1230'. A plate shows the name and the
    number only; the check digit belongs to the machine form."""
    return f"{name.upper()} · {number}" + (f'.{structure}' if structure else '')


FR_UNITS = ['zéro', 'un', 'deux', 'trois', 'quatre', 'cinq', 'six', 'sept', 'huit', 'neuf', 'dix', 'onze', 'douze', 'treize',
            'quatorze', 'quinze', 'seize', 'dix-sept', 'dix-huit', 'dix-neuf']
FR_TENS = {2: 'vingt', 3: 'trente', 4: 'quarante', 5: 'cinquante', 6: 'soixante', 8: 'quatre-vingt'}


def fr_pair(n):
    """0-99 as said in French: 24 'vingt-quatre', 71 'soixante et onze', 80 'quatre-vingts'."""
    if n < 20:
        return FR_UNITS[n]
    t, u = divmod(n, 10)
    if t in (7, 9):
        base, rest = FR_TENS[t - 1], 10 + u
        return base + (' et ' if rest == 11 and t == 7 else '-') + FR_UNITS[rest]
    if u == 0:
        return FR_TENS[t] + ('s' if t == 8 else '')
    return FR_TENS[t] + (' et ' if u == 1 and t != 8 else '-') + FR_UNITS[u]


def say_pair(t):
    """A pair of digits as said in a phone number: '24' vingt-quatre, '05' zéro cinq."""
    return ('zéro ' + FR_UNITS[int(t[1])]) if t[0] == '0' else fr_pair(int(t))


def spoken(name, number):
    """Numbers are said in pairs, as Guineans say phone numbers: 'Kalouma, douze vingt-cinq';
    a 5-digit number starts with its first digit: 13 471 is 'un, trente-quatre soixante et onze'."""
    t = str(number)
    head = FR_UNITS[int(t[0])] + ', ' if len(t) == 5 else ''
    return f"{name}, {head}{say_pair(t[-4:-2])} {say_pair(t[-2:])}"


def load_names(path=None):
    """The registry keyed by normalised plate name. Official names that map to
    one plate name are aliases (load_names(...)['@aliases']). A plate name
    over the limit is refused unless the registry marks it as a provisional
    name still awaiting the commune's choice."""
    with open(path or os.path.join(REPO, 'model', 'names.json'), encoding='utf-8') as f:
        d = json.load(f)
    by_key = {}
    for n in d['names']:
        for b in n['blocks']:
            if not plate_fits(b['name']) and not b.get('overLimit'):
                raise ValueError(f"plate name {b['name']!r} is over {_pn.MAX_CHARS} characters or {_pn.MAX_WORDS} words")
        by_key[n['key']] = n
    by_key['@aliases'] = d.get('aliases', {})
    return by_key


def _candidates(text):
    """(name text, number, check) splits of a typed or spoken home code.
    '·' separates name and number when present; otherwise the number is
    the last 1–3 digit groups that make 4 or 5 digits (so 'Hafia 3 1230',
    'Hafia 3 12 30' and 'HAFIA 3 · 1230-8' all work)."""
    t = text.strip()
    check = None
    m = _re.search(r'-(\d)$', t)
    if m:
        check, t = int(m.group(1)), t[:m.start()].strip()
    if '·' in t:
        nm, num = t.rsplit('·', 1)
        digits = num.replace(' ', '')
        return [(nm.strip(), int(digits), check)] if digits.isdigit() and len(digits) in (4, 5) else []
    toks = t.split()
    out = []
    for k in (1, 2, 3):
        if len(toks) > k and all(x.isdigit() for x in toks[-k:]):
            digits = ''.join(toks[-k:])
            if len(digits) in (4, 5):
                out.append((' '.join(toks[:-k]), int(digits), check))
    return out


def decode_home(text, names):
    """'Name NNNN' -> the one area it names, nationally. No frame needed."""
    cands = _candidates(text)
    if not cands:
        raise ValueError('a home code is a place name followed by 4 or 5 digits')
    hits, why = [], 'no area of that name in Guinea'
    aliases = names.get('@aliases', {})
    for nm, number, check in cands:
        key = normalise_name(nm)
        n, via = names.get(key), None
        if not n and key in aliases:          # the official (full) name typed instead of the plate name
            n, via = names.get(aliases[key]), key
        if not n:
            continue
        if check is not None and check != home_check(n['id'], number):
            why = 'check digit does not match: a digit is wrong or two are swapped'
            continue
        b = next((b for b in n['blocks'] if any(lo <= number <= hi for lo, hi in b.get('blocks', []))), None)
        if not b:
            why = f'{nm} {number} is not issued (no area of that name holds this number)'
            continue
        if via and normalise_name(b.get('officialName', b['name'])) != via:
            why = f'{nm} {number} is not issued (that number belongs to another {b["name"]})'
            continue
        hits.append({'name': b['name'], 'officialName': b.get('officialName', b['name']), 'nameId': n['id'], 'number': number,
                     'area': b['aid'], 'prefecture': b.get('pref'), 'frame': b['frame'], 'lat': b['lat'], 'lon': b['lon'],
                     'zone': b.get('zone'), 'label': b.get('label'),
                     'plate': plate(b['name'], number), 'machine': machine_form(n['id'], number)})
    if len(hits) > 1:
        raise ValueError('ambiguous: write the number after a "·" (e.g. "Hafia 3 · 1230")')
    if not hits:
        raise ValueError(why)
    return hits[0]


def hilbert_d(order, x, y):
    d, s = 0, 1 << (order - 1)
    while s:
        rx, ry = (1 if x & s else 0), (1 if y & s else 0)
        d += s * s * ((3 * rx) ^ ry)
        if ry == 0:
            if rx:
                x, y = s - 1 - x, s - 1 - y
            x, y = y, x
        s >>= 1
    return d


GUINEA_BOX = (-15.4, 7.1, -7.6, 12.7)


def national_order(lat, lon):
    """Hilbert position of a point over Guinea (orders blocks inside a name range)."""
    w, s, e, n = GUINEA_BOX
    side = (1 << 16) - 1
    span = max(e - w, n - s)
    return hilbert_d(16, int((lon - w) / span * side), int((lat - s) / span * side))


def grid_cell(lat, lon, frame):
    """(row, col) of the 3 m cell holding a point in its frame's grid (SPEC 3.2), clamped to the grid."""
    s, w, dlat, dlon = _grid(frame)
    side = PER ** 4
    return (min(side - 1, max(0, math.floor((lat - s) / dlat))), min(side - 1, max(0, math.floor((lon - w) / dlon))))


def hilbert_of(lat, lon, frame):
    """Position of a point along the numbering curve: a Hilbert curve of order 18 over its
    frame's 3 m grid (column = x, row = y)."""
    row, col = grid_cell(lat, lon, frame)
    return hilbert_d(HILBERT_ORDER, col, row)


def number_area(comps, start, size, frame):
    """First issue in one area (SPEC 5.2): the compounds [{'id', 'lat', 'lon'}] in Hilbert order
    of their points (ties by id), number i of n at start + floor((2i+1) size / 2n), so every gap
    between neighbours stays free for a future home. Returns {id: number}."""
    n = len(comps)
    if n > size:
        raise ValueError('block too small: the area takes an extra block from its name range')
    seq = sorted(comps, key=lambda c: (hilbert_of(c['lat'], c['lon'], frame), c['id']))
    return {c['id']: start + (2 * i + 1) * size // (2 * n) for i, c in enumerate(seq)}


def reserve_number(lat, lon, issued, block, frame):
    """Add my home (SPEC 7, step 4): a new compound's number in one block [lo, hi] of its area.
    issued: [(number, lat, lon)] of the block's codes. Its neighbours along the curve are the
    issued compounds just before and after it; it takes the free number nearest the middle of
    their gap (the block's edges stand in for a missing neighbour). Returns (number, why), with
    number None when the block has no free number left."""
    lo, hi = block
    keyed = sorted((hilbert_of(la, lo_, frame), n) for n, la, lo_ in issued)
    taken = {n for n, _, _ in issued}
    h = hilbert_of(lat, lon, frame)
    before = after = None
    for k, n in keyed:
        if k <= h:
            before = n
        elif after is None:
            after = n
    if before is not None and after is not None and after < before:
        before = None                      # the curve and the numbers disagree here: search the whole lower gap
    a = before if before is not None else lo - 1
    b = after if after is not None else hi + 1
    mid = (a + b) // 2
    for d in range(b - a + 1):
        for c in (mid - d, mid + d):
            if a < c < b and lo <= c <= hi and c not in taken:
                return c, 'gap'
    for c in range(lo, hi + 1):
        if c not in taken:
            return c, 'any'
    return None, 'full'


# ---------------------------------------------------------------- tests

def prove_check():
    import itertools
    miss = {'substitution': 0, 'neighbour swap': 0, 'jump swap': 0}
    for body in itertools.product(range(20), repeat=3):
        good = check_char([2] + list(body))
        for i in range(3):
            for v in range(20):
                if v != body[i]:
                    b = list(body); b[i] = v
                    miss['substitution'] += check_char([2] + b) == good
        for i in range(2):
            if body[i] != body[i + 1]:
                b = list(body); b[i], b[i + 1] = b[i + 1], b[i]
                miss['neighbour swap'] += check_char([2] + b) == good
        if body[0] != body[2]:
            miss['jump swap'] += check_char([2, body[2], body[1], body[0]]) == good
    return miss


def prove_damm():
    miss = 0
    for n in range(1000, 10000):
        s = f'0{n:04d}'
        good = damm(s)
        for i in range(len(s)):
            for d in '0123456789':
                if d != s[i] and damm(s[:i] + d + s[i + 1:]) == good:
                    miss += 1
            if i + 1 < len(s) and s[i] != s[i + 1] and damm(s[:i] + s[i + 1] + s[i] + s[i + 2:]) == good:
                miss += 1
    return miss


def run_tests():
    frames = load_frames()
    with open(os.path.join(HERE, 'test-vectors.json'), encoding='utf-8') as f:
        vec = json.load(f)
    ok = True
    for t in vec['spot']:
        f = frame_of(t['lat'], t['lon'], frames)
        code = encode_spot(t['lat'], t['lon'], f)
        d = decode_spot(code, frames)
        dist = math.hypot((d['lat'] - t['lat']) * m_per_deg_lat(t['lat']), (d['lon'] - t['lon']) * m_per_deg_lon(t['lat']))
        good = code == t['code'] and dist <= CELL * 0.75
        ok &= good
        print('ok  ' if good else 'FAIL', t['name'], code, '' if code == t['code'] else f'(expected {t["code"]})', f'back {dist:.2f} m')
    with open(os.path.join(HERE, 'vectors.json'), encoding='utf-8') as f:
        beyond = json.load(f).get('spotsBeyond', [])
    bad = 0
    for t in beyond:
        try:
            code, fb, edge = spot_of(t['lat'], t['lon'], frames)
            good = 'error' not in t and (code, fb['digit'], edge) == (t['code'], t['frame'], t['edge'])
            d = decode_spot(code, frames)
            good &= [d['lat'], d['lon']] == t['decoded']
        except ValueError as e:
            code, good = str(e), 'error' in t
        ok &= good
        bad += not good
        if not good:
            print('FAIL beyond', t, code)
    print('ok  ' if not bad else 'FAIL', len(beyond), 'points beyond a frame grid or outline (vectors.json spotsBeyond)')
    names = load_names()
    for t in vec.get('home', []):
        d = decode_home(t['code'], names)
        good = d['machine'] == t['machine'] and d['area'] == t['area'] and d['plate'] == t['plate']
        ok &= good
        print('ok  ' if good else 'FAIL', t['code'], '->', d['name'], '|', d.get('prefecture'), '|', d['machine'], '' if good else f"(expected {t['machine']} area {t['area']})")
    for bad in vec.get('homeRejects', []):
        try:
            decode_home(bad, names); print('FAIL accepted', bad); ok = False
        except ValueError as e:
            print('ok   rejected', bad, '-', e)
    pn = vec.get('plateNames', {})
    for nm in pn.get('fit', []):
        good = plate_fits(nm); ok &= good
        print('ok  ' if good else 'FAIL', 'plate name fits', repr(nm))
    for nm in pn.get('over', []):
        good = not plate_fits(nm); ok &= good
        print('ok  ' if good else 'FAIL', 'plate name refused (over 12 characters or 2 words)', repr(nm))
    for bad in vec['rejects']:
        try:
            decode_spot(bad, frames)
            print('FAIL accepted', bad); ok = False
        except ValueError as e:
            print('ok   rejected', bad, '-', e)
    m = prove_check(); dm = prove_damm()
    print('spot check misses (all 3-character bodies):', m, '| Damm misses (all 4-digit numbers):', dm)
    ok &= not any(m.values()) and dm == 0
    print('ALL OK' if ok else 'SOME TESTS FAILED')
    return ok


if __name__ == '__main__':
    a = sys.argv[1:]
    if not a or a[0] == 'test':
        sys.exit(0 if run_tests() else 1)
    fr = load_frames()
    if a[0] in ('encode', 'bloc'):
        lat, lon = float(a[1]), float(a[2])
        code = spot_of(lat, lon, fr)[0]
        print(code if a[0] == 'encode' else code[:6])
    elif a[0] == 'decode':
        print(json.dumps(decode_spot(' '.join(a[1:]), fr), ensure_ascii=False))
    elif a[0] == 'home':
        print(json.dumps(decode_home(' '.join(a[1:]), load_names()), ensure_ascii=False))
