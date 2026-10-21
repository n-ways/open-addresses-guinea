#!/usr/bin/env python3
"""Guinea's plate names: the short remembered name of each code area.

The rule itself is engine/reference/plate_names.py. This file is Guinea's
configuration of it, used by tools/build-register.py:

  lang      'fr': area names are French or written in French spelling
            (Susu, Pular, Maninka, Kissi, Toma, Kpelle place names).
  numbered  a quartier's own number ("Hafia 3", "Dixinn Port 2") stays: it
            is split off, the name before it is shortened to fit in
            12 - len(" 3") characters, and the number is put back. It counts
            as characters, not as a word.
  generic   French generic words of the shared list, plus "district" and
            "base vie" (a mining camp's housing).
  weak      words that only qualify a name, so a short form that drops them
            needs the commune: Maninka koura (new) and kôrô (old); the
            people's names Foula/Foulbhè, Malinké/Maninka, Soussou, Peul,
            Kissi, Toma, Guerzé, Djallonké, Diakhanké when they tell two
            parts of a village apart; and the landmark words Conakry uses to
            tell sibling quartiers apart (Centre, Marché, Mosquée, École,
            Gare, Port, Plateau, Cité, Minière, Routière, Carrière...).
  avoid     the préfecture and sous-préfecture seats, the region capitals
            (including Beyla and Siguiri, regions since August 2026), the
            new sous-préfectures of the 2026 decree, the 13 communes of
            Conakry and the big towns of the neighbouring countries near the
            border, which people in Guinea know. A town within 20 km of
            the area, or the area's own préfecture seat, is its own town and
            is not avoided.
  known     documented short forms only, each with its source. None is
            asserted for Guinea yet: the communes' quartier lists give full
            names only.
  hyphens   a hyphenated name too long to fit ("Souma-Hassania") is never
            shortened automatically; its halves are offered to the commune.
  doubled   a reduplicated name ("Kélou Kélou") is never split.
"""
import csv, math, os, re, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import gn_codes as g  # noqa: E402
import plate_names as P  # noqa: E402

LANG = 'fr'
GENERIC_EXTRA = ['district', 'base vie']
WEAK_EXTRA = ['koura', 'kura', 'koro', 'foula', 'foulbe', 'foulbhe', 'malinke', 'maninka', 'soussou', 'sousou', 'peul',
              'peulh', 'kissi', 'toma', 'guerze', 'djallonke', 'diakhanke',
              'centre', 'center', 'marche', 'mosquee', 'ecole', 'gare', 'port', 'plateau', 'cite', 'miniere', 'routiere', 'carriere',
              'mission', 'permanence', 'dispensaire', 'hopital', 'imprimerie', 'rails', 'domino', 'village', 'tannerie',
              'foret']
KNOWN = {}   # {official name: (plate name, source)}: documented short forms only
GEONAMES = os.path.join(os.environ.get('NWAYS_ROOT', '.'), 'data', 'places', 'geonames', 'GN.txt')
# Region capitals, and the capitals and big towns of the six neighbouring countries
# (a plate must not equal them unless it is the town itself)
REGION_CITIES = ['Conakry', 'Boké', 'Kindia', 'Mamou', 'Labé', 'Faranah', 'Kankan', 'Siguiri', 'Nzérékoré', 'Beyla',
                 'Dakar', 'Abidjan', 'Bamako', 'Freetown', 'Bissau', 'Monrovia', 'Kayes',
                 'Sikasso', 'Bouaké', 'Man', 'Odienné', 'Kenema', 'Bo', 'Makeni', 'Kédougou', 'Tambacounda', 'Gabú',
                 'Thiès', 'Mbour', "M'Bour", 'Kaolack', 'Ziguinchor', 'Kolda', 'Ségou', 'Mopti']
# New sous-préfectures of the decree of 20 Aug 2026 (billetdujour.com, SOURCES.md no. 12)
NEW_2026 = ['Kamsar', 'Timbo', 'Tokounou', 'Dialakoro', 'Sabadou-Baranama', 'Doko', 'Siguirini', 'Kintinian', 'Sinko',
            'Kouankan', 'Karala']
CONAKRY_COMMUNES = ['Kaloum', 'Dixinn', 'Matam', 'Ratoma', 'Lambanyi', 'Sonfonia', 'Matoto', 'Gbessia', 'Tombolia',
                    'Kassa', 'Manéah', 'Kagbélen', 'Sanoyah']
OWN_KM = 20


def _clean_admin(n):
    return re.sub(r'\s+Sub-Prefecture$', '', n).strip()


def avoid_towns(areas=()):
    """[(name, lat or None, lon or None, kind)] of the towns a plate must not
    equal. A listed town without a GeoNames seat gets the position of a
    GeoNames place or a code area of that name in Guinea."""
    out, pos = [], {}
    rows = list(csv.reader(open(GEONAMES, encoding='utf-8'), delimiter='\t', quoting=csv.QUOTE_NONE)) if os.path.exists(GEONAMES) else []
    for f in rows:
        if len(f) > 7 and f[7] in ('PPLC', 'PPLA', 'PPLA2', 'PPLA3', 'ADM3'):
            out.append((_clean_admin(f[1]), float(f[4]), float(f[5]), f[7]))
    for f in rows:
        if len(f) > 7 and f[6] == 'P':
            pos.setdefault(g.normalise_name(f[1]), (float(f[4]), float(f[5])))
    for a in areas:
        pos.setdefault(g.normalise_name(prepare(a['name'])), (a['lat'], a['lon']))
    seats = {g.normalise_name(n) for n, *_ in out}
    for n in NEW_2026 + CONAKRY_COMMUNES:
        if g.normalise_name(n) not in seats:
            la, lo = pos.get(g.normalise_name(n), (None, None))
            out.append((n, la, lo, 'listed'))
    for n in REGION_CITIES:
        la, lo = pos.get(g.normalise_name(n), (None, None)) if n in ('Conakry', 'Boké', 'Kindia', 'Mamou', 'Labé', 'Faranah', 'Kankan', 'Siguiri', 'Nzérékoré', 'Beyla') else (None, None)
        out.append((n, la, lo, 'city'))
    return out


def _km(lat1, lon1, lat2, lon2):
    return math.hypot((lat1 - lat2) * 111.0, (lon1 - lon2) * 111.0 * math.cos(math.radians(lat1)))


class Deriver:
    def __init__(self, areas):
        self.freq = P.word_freq([g.split_quartier_number(prepare(a['name']))[0] for a in areas], LANG)
        self.towns = avoid_towns(areas)

    def avoid_for(self, area):
        own = {g.normalise_name(area.get('pref') or '')}
        out = set()
        for n, lat, lon, _ in self.towns:
            k = g.normalise_name(n)
            if k in own or (lat is not None and _km(area['lat'], area['lon'], lat, lon) <= OWN_KM):
                continue
            out.add(k)
        return out

    def derive(self, area):
        official = prepare(area['name'])
        base, num = g.split_quartier_number(official)
        suffix = f' {num}' if num else ''
        avoid = self.avoid_for(area)
        old = P.MAX_CHARS
        P.MAX_CHARS = old - len(suffix)
        try:
            r = P.derive(base, LANG, self.freq, known=KNOWN, avoid=avoid, generic_extra=GENERIC_EXTRA,
                         weak_extra=WEAK_EXTRA, avoid_key=g.normalise_name)
            cleaned, _ = P.clean(base, LANG, GENERIC_EXTRA, WEAK_EXTRA)
            _hyphen_halves(r, cleaned, self.freq)
            _quartier_suffix(r, base, area)
            _too_short(r, base)
            _no_split_doubles(r, cleaned)
        finally:
            P.MAX_CHARS = old
        if suffix and r.get('reason', '').startswith('no run of whole words fits'):
            r['reason'] = 'no run of whole words fits %d characters and %d words with its number' % (P.MAX_CHARS, P.MAX_WORDS)
        r['plate'] = r['plate'] + suffix
        r['candidates'] = [c + suffix for c in r['candidates']]
        r['official'] = area['name']
        r['overLimit'] = not g.plate_fits(r['plate'])
        return r


def prepare(name):
    """Map-data slips fixed before anything else: Cyrillic look-alikes,
    underscores, a number glued to the word ("Morikania1")."""
    s = (name or '').translate(g._CONFUSABLE).replace('_', ' ')
    s = re.sub(r'\s+-\s+', '-', s.strip())                  # "Hoorè - Wendou" -> "Hoorè-Wendou"
    s = re.sub(r'(?<=[^\W\d_])(?=\d{1,2}$)', ' ', s)
    return re.sub(r'\s+', ' ', s)


def _hyphen_halves(r, cleaned, freq):
    if r['rule'] != 'council' or r['candidates'] or '-' not in cleaned:
        return
    cs = P.candidates(cleaned.replace('-', ' '), LANG, freq, WEAK_EXTRA)
    if cs:
        r['candidates'] = [c[0] for c in cs[:3]]
        r['plate'] = r['candidates'][0]
        r['reason'] = 'a hyphenated name too long to keep whole: the commune chooses'


def _no_split_doubles(r, cleaned):
    ws = cleaned.split()
    for i in range(len(ws) - 1):
        if P.plain(ws[i]) == P.plain(ws[i + 1]):
            pair = ws[i] + ' ' + ws[i + 1]
            if r['rule'] == 'distinctive' and pair not in r['plate'] and P.plain(ws[i]) in P.plain(r['plate']).split():
                r.update(rule='council', needsCouncilChoice=True, reason='a doubled name ("%s") is never split' % pair)
                if P.plate_length(pair) <= P.MAX_CHARS:
                    r['candidates'] = [pair] + [c for c in r['candidates'] if c != pair][:2]
                r['plate'] = r['candidates'][0]


TRAILING_GENERIC = re.compile(r'\s(cit[eé]|village|zone|secteur|quartier)$', re.I)


def _quartier_suffix(r, base, area):
    """An official quartier named "X Cité" or "X Village" is told apart from
    its sibling quartiers ("Coleah Cité", "Coleah Centre") by that word: it
    is kept when the name fits, and left to the commune when it does not."""
    if area.get('how') != 'quartier' or r['rule'] != 'cleaned' or not TRAILING_GENERIC.search(base):
        return
    if g.plate_fits(base) and P.plate_length(base) <= P.MAX_CHARS:
        r.update(plate=base, rule='as-is', needsCouncilChoice=False, candidates=[])
        r.pop('reason', None)
    else:
        r.update(rule='council', needsCouncilChoice=True, candidates=[r['plate']],
                 reason='a trailing Cité/Village tells sibling quartiers apart')


def _too_short(r, base):
    if r['rule'] == 'cleaned' and sum(ch.isalpha() for ch in r['plate']) < P.MIN_LETTERS:
        r.update(rule='council', needsCouncilChoice=True, candidates=[], plate=base,
                 reason='the name left after dropping generic words is too short to stand alone')
