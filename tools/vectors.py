#!/usr/bin/env python3
"""Conformance vectors for every port of the engine: engine/reference/vectors.json.

Computed by the reference engine (engine/reference/gn_codes.py) on the frozen register
(model/names.json, engine/data/register.json); a port (the N-Ways backend's
internal/addressing/gn) must reproduce them value for value.

  python3 tools/vectors.py
"""
import json, os, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import gn_codes as g  # noqa: E402


def beyond_case(lat, lon, frames, machine=None):
    """A point in no frame outline, as SPEC 3.4 codes it, or refuses it."""
    t = {'lat': lat, 'lon': lon}
    try:
        code, f, edge = g.spot_of(lat, lon, frames)
    except ValueError as e:
        t['error'] = str(e)
        return t
    d = g.decode_spot(code, frames)
    t.update(frame=f['digit'], frame2=g.frame_of(lat, lon, frames)['digit'], edge=edge, code=code, decoded=[d['lat'], d['lon']])
    if machine:
        t['machine'] = machine
    return t


def spots_beyond(frames):
    """Points in no outline (SPEC 3.4): every issued compound whose entrance lies beyond the
    grid of a frame within reach (from the registry), then points near the outlines drawn
    with their own seed, so the other vectors stay as they were."""
    import csv, gzip
    out = []
    reach = g.OUTLINE_DEG
    for key in ('CKY', 'BAS', 'MOY', 'HAU', 'FOR'):
        with gzip.open(os.path.join(REPO, 'registry', key + '.csv.gz'), 'rt', encoding='utf-8', newline='') as fh:
            rows = csv.reader(fh)
            h = next(rows)
            im, ilat, ilon = h.index('machine'), h.index('entrance_lat'), h.index('entrance_lng')
            for r in rows:
                lat, lon = float(r[ilat]), float(r[ilon])
                if any(f['box'][0] - reach <= lon <= f['box'][2] + reach and f['box'][1] - reach <= lat <= f['box'][3] + reach
                       and g._beyond(*g._cell(lat, lon, f)) for f in frames.values()):
                    t = beyond_case(lat, lon, frames, r[im])
                    if t.get('edge') or t.get('frame') != t.get('frame2'):
                        out.append(t)
    rnd = random.Random(3104)
    shapes = g._frame_shapes(os.path.join(REPO, 'model', 'frames.geojson'))
    verts = [v for _d, _b, p in shapes for ring in p for v in ring]
    want = {'edge': 60, 'other': 4, 'refused': 30}
    got = {k: 0 for k in want}
    for _ in range(2000000):
        if all(got[k] >= want[k] for k in want):
            break
        v = rnd.choice(verts)
        lat, lon = v[1] + rnd.uniform(-0.012, 0.012), v[0] + rnd.uniform(-0.012, 0.012)
        if not any(g._beyond(*g._cell(lat, lon, f)) for f in frames.values()
                   if f['box'][0] - 0.012 <= lon <= f['box'][2] + 0.012 and f['box'][1] - 0.012 <= lat <= f['box'][3] + 0.012):
            continue                                 # every grid within reach holds it
        try:
            f2 = g.frame_of(lat, lon, frames)
        except ValueError:
            f2 = None
        if f2 is not None and not g._beyond(*g._cell(lat, lon, f2)):
            continue                                 # the grid of SPEC 2's frame holds it: SPEC 3.2 alone
        t = beyond_case(lat, lon, frames)
        k = 'refused' if 'error' in t else 'edge' if t['edge'] else 'other'
        if got[k] < want[k]:
            got[k] += 1
            out.append(t)
    return out


def main():
    rnd = random.Random(224)
    with open(os.path.join(REPO, 'engine', 'data', 'register.json'), encoding='utf-8') as f:
        reg = json.load(f)
    names = g.load_names()
    frames = g.load_frames()
    areas = reg['areas']
    used = [a for a in areas if a['blocks']]
    words = sorted({a['name'] for a in areas} | {a['officialName'] for a in areas})
    tricky = ['Сondetta', 'Hafiya 3', 'Hafia3', 'Missidè', 'Missidé', 'Tannérie', 'Dankharan', 'St-Antonin', 'Saint Antonin', 'Ste Marie',
              'Quartier Hafia 3', 'Village Kalouma', "N'Zérékoré", 'Nzérékoré', 'Dar es Salam', 'Dar-Es-Salam', 'Soro2', 'Château d’Eau',
              'Koulé (Ley)', 'Kélou Kélou', 'Lambanyi', 'Secteur 4']
    keys = [[w, g.normalise_name(w)] for w in tricky + rnd.sample(words, 500)]
    forms, found = [], []
    for a in rnd.sample(used, 400):
        lo, hi = a['blocks'][0]
        n = rnd.randint(lo, hi)
        st = rnd.choice([None, None, None, 2, 3])
        forms.append({'zone': f"{a['frame']}-{a['index']:05d}", 'number': n, 'structure': st or 0, 'check': g.home_check(a['family'], n, st),
                      'remembered': g.remembered(a['name'], n, st), 'plate': g.plate(a['name'], n),
                      'machine': g.machine_form(a['family'], n, st), 'spoken': g.spoken(a['name'], n)})
        for text in (g.remembered(a['name'], n), g.remembered(a['name'], n) + f"-{g.home_check(a['family'], n)}",
                     f"{a['name']} {str(n)[:-2]} {str(n)[-2:]}"):
            try:
                found.append({'text': text, 'machine': g.decode_home(text, names)['machine']})
            except ValueError as e:
                found.append({'text': text, 'error': str(e)})
    # official names typed in full, wrong checks, numbers no block holds
    off = [a for a in used if a['officialName'] != a['name']]
    for a in rnd.sample(off, min(80, len(off))):
        n = a['blocks'][0][0] + 1
        text = f"{a['officialName']} {n}"
        try:
            found.append({'text': text, 'machine': g.decode_home(text, names)['machine']})
        except ValueError as e:
            found.append({'text': text, 'error': str(e)})
    for a in rnd.sample(used, 40):
        n = a['blocks'][0][0] + 2
        found.append({'text': g.remembered(a['name'], n) + f"-{(g.home_check(a['family'], n) + 1) % 10}", 'error': 'check'})
    found.append({'text': 'Nowhere Land 1234', 'error': 'no such name'})
    spots = []
    for _ in range(400):
        f = frames[rnd.choice(sorted(frames))]
        x0, y0, x1, y1 = f['box']
        lat, lon = rnd.uniform(y0, y1), rnd.uniform(x0, x1)
        try:
            fr = g.frame_of(lat, lon, frames)
        except ValueError:
            continue
        code = g.encode_spot(lat, lon, fr)
        d = g.decode_spot(code, frames)
        spots.append({'lat': lat, 'lon': lon, 'frame': fr['digit'], 'code': code, 'decoded': [d['lat'], d['lon']],
                      'cell': list(g.grid_cell(lat, lon, fr)), 'hilbert': g.hilbert_of(lat, lon, fr)})
    beyond = spots_beyond(frames)
    # numbering and insertion in a toy area of Conakry
    fr = frames[0]
    lat0, lon0 = 9.5360, -13.6830
    comps = [{'id': f'c{k:02d}', 'lat': lat0 + rnd.uniform(0, 0.004), 'lon': lon0 + rnd.uniform(0, 0.004)} for k in range(18)]
    nums = g.number_area(comps, 1000, 50, fr)
    issued = [(nums[c['id']], c['lat'], c['lon']) for c in comps]
    inserts = []
    for _ in range(50):
        lat, lon = lat0 + rnd.uniform(-0.001, 0.005), lon0 + rnd.uniform(-0.001, 0.005)
        n, why = g.reserve_number(lat, lon, issued, (1000, 1049), fr)
        inserts.append({'lat': lat, 'lon': lon, 'number': n, 'why': why})
    out = {'note': 'Computed by engine/reference/gn_codes.py on the frozen register; every port must match.',
           'nameKeys': keys, 'forms': forms, 'found': found, 'spots': spots, 'spotsBeyond': beyond,
           'numbering': {'frame': 0, 'from': 1000, 'size': 50, 'compounds': comps, 'numbers': nums, 'block': [1000, 1049], 'inserts': inserts},
           'blockSizes': [[n, g.block_size(n)] for n in (0, 1, 24, 25, 26, 49, 50, 51, 499, 4500)],
           'pairs': [[n, g.fr_pair(n)] for n in range(100)]}
    with open(os.path.join(REPO, 'engine', 'reference', 'vectors.json'), 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=0)
    print(len(keys), 'name keys,', len(forms), 'forms,', len(found), 'decodings,', len(spots), 'spots,', len(beyond), 'points beyond a grid or outline,',
          len(inserts), 'inserts')


if __name__ == '__main__':
    main()
