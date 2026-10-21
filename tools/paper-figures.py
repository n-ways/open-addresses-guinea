#!/usr/bin/env python3
"""Data tables behind the paper's figures (docs/figures/*.dat).

Reads only the published files (registry/, model/), so anyone can rebuild the
figures from a clone of the repository:

  python3 tools/paper-figures.py            # writes docs/figures/*.dat
  sh docs/paper/build.sh                    # compiles the figures and the paper
"""
import csv, gzip, json, math, os, collections

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(REPO, 'docs', 'figures')
FRAMES = ['CKY', 'BAS', 'MOY', 'HAU', 'FOR']          # frame digits 0..4
CELL_DEG = 0.1                                         # density grid of the national map


def rows(name):
    with gzip.open(os.path.join(REPO, 'registry', name), 'rt', encoding='utf-8', newline='') as f:
        yield from csv.DictReader(f)


def write(name, header, data):
    with open(os.path.join(OUT, name), 'w', encoding='utf-8') as f:
        f.write(' '.join(header) + '\n')
        for r in data:
            f.write(' '.join(str(v) for v in r) + '\n')


def simplify(ring, tol):
    """Douglas-Peucker on a ring of (lon, lat), tolerance in degrees."""
    if len(ring) < 4:
        return ring
    keep = [False] * len(ring)
    keep[0] = keep[-1] = True
    stack = [(0, len(ring) - 1)]
    while stack:
        a, b = stack.pop()
        (ax, ay), (bx, by) = ring[a], ring[b]
        dx, dy = bx - ax, by - ay
        L = math.hypot(dx, dy)
        best, at = -1.0, None
        for i in range(a + 1, b):
            px, py = ring[i]
            # a closed ring starts and ends on one point: measure from that point instead
            d = abs(dy * (px - ax) - dx * (py - ay)) / L if L > 1e-12 else math.hypot(px - ax, py - ay)
            if d > best:
                best, at = d, i
        if at is not None and best > tol:
            keep[at] = True
            stack += [(a, at), (at, b)]
    return [p for p, k in zip(ring, keep) if k]


def ring_area(ring):
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]))) / 2


def frames_outline():
    with open(os.path.join(REPO, 'model', 'frames.geojson'), encoding='utf-8') as f:
        gj = json.load(f)
    out = []
    for feat in sorted(gj['features'], key=lambda x: x['properties']['digit']):
        g = feat['geometry']
        polys = g['coordinates'] if g['type'] == 'MultiPolygon' else [g['coordinates']]
        for poly in polys:
            ring = [tuple(p) for p in poly[0]]
            if ring_area(ring) < 0.002:                # islets under about 25 km² are left out of the map
                continue
            for x, y in simplify(ring, 0.01):
                out.append((round(x, 4), round(y, 4), feat['properties']['digit']))
            out.append(('nan', 'nan', feat['properties']['digit']))
    write('frames-outline.dat', ['lon', 'lat', 'frame'], out)


def main():
    os.makedirs(OUT, exist_ok=True)
    frames_outline()

    areas = {r['zone']: r for r in rows('areas.csv.gz')}
    per_zone = collections.Counter()
    cells = collections.Counter()
    hafia = []
    for fr in FRAMES:
        for r in rows(fr + '.csv.gz'):
            z = r['zone']
            per_zone[z] += 1
            la, lo = float(r['entrance_lat']), float(r['entrance_lng'])
            cells[(math.floor(lo / CELL_DEG), math.floor(la / CELL_DEG))] += 1
            if z == '0-00026':                         # Hafia 3, Dixinn: the paper's worked example
                hafia.append((int(r['number']), la, lo))

    write('frames-density.dat', ['lon', 'lat', 'log10n'],
          sorted(((round((i + 0.5) * CELL_DEG, 3), round((j + 0.5) * CELL_DEG, 3), round(math.log10(n), 3))
                  for (i, j), n in cells.items())))

    # compounds per area, in bins of a fifth of a decade
    edges = [round(10 ** (k / 5)) for k in range(0, 23)]
    edges = sorted(set(edges))
    hist = collections.Counter()
    for n in per_zone.values():
        for lo, hi in zip(edges, edges[1:]):
            if lo <= n < hi:
                hist[lo] += 1
                break
    bins = [(lo, hi, hist[lo]) for lo, hi in zip(edges, edges[1:]) if lo <= max(per_zone.values())]
    bins.append((bins[-1][1], bins[-1][1], 0))       # closing edge for an interval bar chart
    write('areas-hist.dat', ['lo', 'hi', 'areas'], bins)

    # Hafia 3 in local metres around its mean point, in number order
    mla = sum(p[1] for p in hafia) / len(hafia)
    mlo = sum(p[2] for p in hafia) / len(hafia)
    ky = 111132.954 - 559.822 * math.cos(2 * math.radians(mla))
    kx = 111412.84 * math.cos(math.radians(mla))
    write('hafia3.dat', ['x', 'y', 'number'],
          [(round((lo - mlo) * kx, 1), round((la - mla) * ky, 1), n) for n, la, lo in sorted(hafia)])

    # the national range of the name Madina: one block per place
    mad = []
    for z, a in areas.items():
        if a['name_key'] == 'madina' and a['blocks']:
            for blk in a['blocks'].split(';'):
                s, e = (int(v) for v in blk.split('-'))
                mad.append((s, e + 1, int(a['frame']), per_zone[z]))
    mad.sort()
    write('madina-blocks.dat', ['start', 'end', 'frame', 'compounds', 'row'],
          [(s, e, f, n, i) for i, (s, e, f, n) in enumerate(mad)])

    # footprint sources and round houses by frame
    with open(os.path.join(REPO, 'model', 'building-stats.json'), encoding='utf-8') as f:
        bs = json.load(f)['frames']
    order = ['Conakry', 'Basse-Guinée', 'Moyenne-Guinée', 'Haute-Guinée', 'Guinée forestière']
    write('footprints.dat', ['frame', 'osm', 'ml', 'roundpct', 'median'],
          [(i, round(bs[k]['fromOpenStreetMap'] / 1e6, 4), round((bs[k]['structures'] - bs[k]['fromOpenStreetMap']) / 1e6, 4),
            round(100 * bs[k]['roundHouseShare'], 1), bs[k]['footprintAreaM2']['p50']) for i, k in enumerate(order)])


if __name__ == '__main__':
    main()
