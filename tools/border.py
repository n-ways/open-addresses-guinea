#!/usr/bin/env python3
"""Guinea's national border (engine/SPEC.md 2.1), and the check that no code lies across it.

  python3 tools/border.py build <extract.osm.pbf> [--full FILE]
        the OpenStreetMap admin_level=2 relation of Guinea (ISO3166-1=GN), assembled
        by osmium, simplified by Douglas-Peucker at 5 m -> engine/data/border.geojson
        (--full also writes the border unsimplified, for `check --border FILE`)
  python3 tools/border.py check [--registry registry] [--border FILE]
        counts the codes whose entrance lies more than 300 m outside the border;
        exits 1 if there is any

The extract must hold the relation whole. A country extract clipped at its own
outline may miss border ways; osmium then cannot assemble the area and the tool
stops. N-Ways' data/osm/westafrica-admin.osm.pbf (every admin boundary of the
region) always holds it.

The simplified file records how far it strays from the true line at most
(maxDeviationM, measured both ways: every vertex of the true line to the
simplified one, and the simplified line, sampled every 10 m, to the true one).
gn_codes.Border takes that, rounded up, off the 300 m (limitM), so a point it
accepts is never more than 300 m outside the true border.
"""
import argparse
import csv
import gzip
import json
import math
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'engine', 'reference'))
import gn_codes as g  # noqa: E402

ISO = 'GN'
SIMPLIFY_M = 5.0
SAMPLE_M = 10.0
FRAMES = ('BAS', 'CKY', 'FOR', 'HAU', 'MOY')


def read_border(pbf):
    """(relation id, MultiPolygon coordinates) of the admin_level=2 relation of Guinea."""
    with tempfile.TemporaryDirectory() as tmp:
        sub = os.path.join(tmp, 'al2.osm.pbf')
        seq = os.path.join(tmp, 'al2.geojsonseq')
        subprocess.run(['osmium', 'tags-filter', '-O', '-o', sub, pbf, 'r/admin_level=2'], check=True)
        subprocess.run(['osmium', 'export', '-O', '-f', 'geojsonseq', '--geometry-types=polygon', '-a', 'type,id',
                        '-o', seq, sub], check=True)
        found = []
        with open(seq, encoding='utf-8') as fh:
            for line in fh:
                j = json.loads(line.lstrip('\x1e'))
                p = j['properties']
                if p.get('@type') == 'relation' and p.get('admin_level') == '2' and p.get('ISO3166-1') == ISO:
                    found.append(j)
    if len(found) != 1:
        sys.exit(f'expected one complete admin_level=2 relation with ISO3166-1={ISO} in {pbf}, found {len(found)} '
                 '(an extract clipped at the border misses ways: use data/osm/westafrica-admin.osm.pbf)')
    geom = found[0]['geometry']
    polys = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
    return found[0]['properties']['@id'], polys


def _seg_d(p, a, b):
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def douglas_peucker(pts, tol):
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        best, k = -1.0, None
        for m in range(i + 1, j):
            d = _seg_d(pts[m], pts[i], pts[j])
            if d > best:
                best, k = d, m
        if k is not None and best > tol:
            keep[k] = True
            stack += [(i, k), (k, j)]
    return [p for p, f in zip(pts, keep) if f]


def simplify_ring(ring, tol):
    """A closed ring of (lon, lat), simplified on the local plane at its mean latitude,
    split at its first vertex and the vertex farthest from it so both halves are open lines."""
    pts = ring[:-1] if ring[0] == ring[-1] else list(ring)
    lat0 = sum(y for _, y in pts) / len(pts)
    kx, ky = g.m_per_deg_lon(lat0), g.m_per_deg_lat(lat0)
    xy = [(x * kx, y * ky) for x, y in pts]
    far = max(range(len(xy)), key=lambda i: math.hypot(xy[i][0] - xy[0][0], xy[i][1] - xy[0][1]))
    a = douglas_peucker(xy[:far + 1], tol)
    b = douglas_peucker(xy[far:] + [xy[0]], tol)
    out = a + b[1:]
    if len(out) < 4:
        return list(ring)
    return [(x / kx, y / ky) for x, y in out]


class SegIndex:
    """Nearest-segment distance in metres, on the local plane at the query point."""

    def __init__(self, rings, cell=0.01):
        self.cell, self.segs, self.grid = cell, [], {}
        for ring in rings:
            for i in range(1, len(ring)):
                self.segs.append((ring[i - 1], ring[i]))
        for k, (a, b) in enumerate(self.segs):
            for gx in range(int(math.floor(min(a[0], b[0]) / cell)), int(math.floor(max(a[0], b[0]) / cell)) + 1):
                for gy in range(int(math.floor(min(a[1], b[1]) / cell)), int(math.floor(max(a[1], b[1]) / cell)) + 1):
                    self.grid.setdefault((gx, gy), []).append(k)

    def dist(self, p):
        lon, lat = p
        kx, ky = g.m_per_deg_lon(lat), g.m_per_deg_lat(lat)
        gx, gy = int(math.floor(lon / self.cell)), int(math.floor(lat / self.cell))
        reach = self.cell * min(kx, ky)
        best = math.inf
        for r in range(0, 200):
            ring = [(x, y) for x in range(gx - r, gx + r + 1) for y in range(gy - r, gy + r + 1)
                    if max(abs(x - gx), abs(y - gy)) == r]
            for c in ring:
                for k in self.grid.get(c, ()):
                    (ax, ay), (bx, by) = self.segs[k]
                    best = min(best, g._seg_dist(0.0, 0.0, (ax - lon) * kx, (ay - lat) * ky, (bx - lon) * kx, (by - lat) * ky))
            if best <= r * reach:   # nothing beyond the searched square can be nearer
                return best
        return best


def deviation(true_rings, simple_rings):
    t, s = SegIndex(true_rings), SegIndex(simple_rings)
    worst = max(s.dist(p) for ring in true_rings for p in ring)
    for ring in simple_rings:
        for i in range(1, len(ring)):
            a, b = ring[i - 1], ring[i]
            lat = (a[1] + b[1]) / 2
            n = max(1, int(math.hypot((b[0] - a[0]) * g.m_per_deg_lon(lat), (b[1] - a[1]) * g.m_per_deg_lat(lat)) // SAMPLE_M))
            for j in range(n + 1):
                worst = max(worst, t.dist((a[0] + (b[0] - a[0]) * j / n, a[1] + (b[1] - a[1]) * j / n)))
    return worst


def closed(ring):
    out = [[round(x, 5), round(y, 5)] for x, y in ring]
    if out[0] != out[-1]:
        out.append(out[0])
    return out


def build(pbf, out, full=None, tol=SIMPLIFY_M):
    rid, polys = read_border(os.path.abspath(pbf))
    true_rings = [[(float(x), float(y)) for x, y in r] for p in polys for r in p]
    simple = [[closed(simplify_ring([(float(x), float(y)) for x, y in r], tol)) for r in p] for p in polys]
    dev = deviation(true_rings, [[(x, y) for x, y in r] for p in simple for r in p])
    dev = math.ceil(dev * 10) / 10
    doc = {'type': 'Feature',
           'properties': {'country': ISO, 'source': f'OpenStreetMap relation/{rid} (admin_level=2), ODbL, © OpenStreetMap contributors',
                          'simplifiedM': tol, 'maxDeviationM': dev, 'borderM': g.BORDER_M,
                          'limitM': g.BORDER_M - math.ceil(dev)},
           'geometry': {'type': 'MultiPolygon', 'coordinates': simple}}
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(doc, fh, separators=(',', ':'), ensure_ascii=False)
        fh.write('\n')
    if full:
        with open(full, 'w', encoding='utf-8') as fh:
            json.dump({'type': 'Feature', 'properties': {'country': ISO, 'source': f'OpenStreetMap relation/{rid}', 'maxDeviationM': 0},
                       'geometry': {'type': 'MultiPolygon', 'coordinates': polys}}, fh, separators=(',', ':'))
    print(f'relation {rid}: {sum(len(r) for r in true_rings):,} vertices -> {sum(len(r) for p in simple for r in p):,}, '
          f'largest deviation {dev:.1f} m, limit {doc["properties"]["limitM"]:.0f} m, {os.path.getsize(out):,} bytes')


def check(registry, border=None):
    """Codes certainly more than 300 m outside the true border (beyond 300 m plus the
    file's deviation), and codes the file cannot settle (within the deviation of 300 m,
    where the server refuses a new code). With the unsimplified border (--full) the
    deviation is 0 and the count is exact."""
    near = g.Border(border)
    far = g.Border(border, limit_m=g.BORDER_M + math.ceil(near.deviation))
    total = abroad = edge = 0
    first = []
    for k in FRAMES:
        with gzip.open(os.path.join(registry, f'{k}.csv.gz'), 'rt', encoding='utf-8', newline='') as fh:
            for row in csv.DictReader(fh):
                total += 1
                lat, lng = float(row['entrance_lat']), float(row['entrance_lng'])
                if near.holds(lat, lng):
                    continue
                if far.holds(lat, lng):
                    edge += 1
                    continue
                abroad += 1
                if len(first) < 10:
                    first.append(row['machine'])
    print(f'{abroad:,} of {total:,} codes have their entrance more than {far.limit:.0f} m outside the border'
          + (f' (first: {", ".join(first)})' if first else ''))
    if near.deviation:
        print(f'{edge:,} lie between {near.limit:.0f} and {far.limit:.0f} m outside this border, which is {near.deviation} m '
              'from the true line at most; check them with the unsimplified border (build --full FILE, check --border FILE)')
    return abroad


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('build')
    p.add_argument('pbf')
    p.add_argument('--out', default=g.BORDER_FILE)
    p.add_argument('--full')
    p.add_argument('--tolerance', type=float, default=SIMPLIFY_M, help='Douglas-Peucker tolerance in metres (default %(default)s)')
    c = sub.add_parser('check')
    c.add_argument('--registry', default=os.path.join(REPO, 'registry'))
    c.add_argument('--border', help='a border file (default engine/data/border.geojson)')
    a = ap.parse_args()
    if a.cmd == 'build':
        build(a.pbf, a.out, a.full, a.tolerance)
    else:
        sys.exit(1 if check(a.registry, a.border) else 0)


if __name__ == '__main__':
    main()
