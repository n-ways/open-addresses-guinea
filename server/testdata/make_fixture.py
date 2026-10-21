#!/usr/bin/env python3
"""Builds the test registry from the published one: the complete area table
and every code of the commune of Kaloum (13 areas of the Conakry frame), in
the published format with its own MANIFEST.json. Also writes gaps.csv beside
it: published codes whose entrance lies in no frame outline but within 0.01
degrees of one (SPEC 2), so in Guinea.

  python3 server/testdata/make_fixture.py registry server/testdata/registry
"""
import csv
import gzip
import hashlib
import io
import json
import os
import sys

# Codes whose entrance lies in no frame outline: four of Conakry, twelve of
# Haute-Guinée, two of Basse-Guinée, two of Guinée forestière and four of
# Moyenne-Guinée, each of a different area, every one inside the national
# border or less than 200 m outside it (SPEC 2.1).
GAPS = (
    'GN-04536-1133-9', 'GN-09091-1091-9', 'GN-06002-1307-6', 'GN-06002-1975-5', 'GN-10423-1741-9', 'GN-06935-1339-4',
    'GN-05705-1075-2', 'GN-04546-4267-8', 'GN-04544-1398-7', 'GN-00970-1006-8', 'GN-07189-1119-9', 'GN-06649-1045-4',
    'GN-08011-1007-2', 'GN-08838-3350-7', 'GN-00988-1294-4', 'GN-01187-1285-0', 'GN-02424-2167-8', 'GN-06215-1099-2',
    'GN-04983-1021-6', 'GN-07089-1451-8', 'GN-03227-2152-0', 'GN-01596-2173-1', 'GN-07330-1170-3', 'GN-07289-10501-0',
)


def gaps(src, out):
    """gaps.csv: the GAPS codes, with their frame file's key first."""
    want = set(GAPS)
    rows = {}
    header = None
    for key in ('CKY', 'BAS', 'MOY', 'HAU', 'FOR'):
        with gzip.open(os.path.join(src, key + '.csv.gz'), 'rt', encoding='utf-8', newline='') as f:
            r = csv.reader(f)
            header = next(r)
            for row in r:
                if row[0] in want:
                    rows[row[0]] = [key] + row
    with open(os.path.join(os.path.dirname(os.path.abspath(out)), 'gaps.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, lineterminator='\n')
        w.writerow(['frame'] + header)
        for m in GAPS:
            w.writerow(rows[m])
    print('%d codes in no frame outline' % len(rows))


def main(src, out):
    os.makedirs(out, exist_ok=True)
    with gzip.open(os.path.join(src, 'areas.csv.gz'), 'rb') as f:
        areas_raw = f.read()
    kaloum = {r['zone'] for r in csv.DictReader(io.StringIO(areas_raw.decode('utf-8'))) if r['label'] == 'Kaloum'}
    lines = []
    with gzip.open(os.path.join(src, 'CKY.csv.gz'), 'rt', encoding='utf-8', newline='') as f:
        header = f.readline()
        for line in f:
            row = next(csv.reader([line]))
            if row[3] in kaloum:
                lines.append(line)
    cky = (header + ''.join(lines)).encode('utf-8')
    sums = {}
    for name, data in (('areas.csv', areas_raw), ('CKY.csv', cky)):
        with open(os.path.join(out, name + '.gz'), 'wb') as raw:
            with gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0) as gz:
                gz.write(data)
        sums[name] = hashlib.sha256(data).hexdigest()
    with open(os.path.join(src, 'MANIFEST.json'), encoding='utf-8') as f:
        man = json.load(f)
    man.update(byFrame={'CKY': len(lines)}, codes=len(lines), sha256=sums)
    with open(os.path.join(out, 'MANIFEST.json'), 'w', encoding='utf-8') as f:
        f.write(json.dumps(man, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    print('%d codes of %d Kaloum areas' % (len(lines), len(kaloum)))


if __name__ == '__main__':
    main(*sys.argv[1:3])
    gaps(*sys.argv[1:3])
