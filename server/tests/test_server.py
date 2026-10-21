"""Tests of the registry server against the test registry (server/testdata).

  python3 -m unittest discover -s server/tests -t .
"""
import csv
import gzip
import hashlib
import http.client
import io
import json
import math
import os
import shutil
import tempfile
import threading
import unittest

from server import api, engine, store
from server.service import Service

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(os.path.dirname(HERE), 'testdata', 'registry')
PARITY = os.path.join(os.path.dirname(HERE), 'testdata', 'parity.json')
GAPS = os.path.join(os.path.dirname(HERE), 'testdata', 'gaps.csv')
QUIET = lambda *a, **k: None  # noqa: E731


def fixture_rows(name='CKY'):
    with gzip.open(os.path.join(FIXTURE, name + '.csv.gz'), 'rt', encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def read_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def write_json(path, obj):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f)


def plain(path):
    with gzip.open(path, 'rb') as f:
        return f.read()


def gap_rows():
    with open(GAPS, encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def gap_registry(out):
    """A registry of the area table and the codes of gaps.csv, in the published format."""
    os.makedirs(out)
    with open(GAPS, encoding='utf-8', newline='') as f:
        rows = list(csv.reader(f))
    header, by = rows[0][1:], {}
    for r in rows[1:]:
        by.setdefault(r[0], []).append(r[1:])
    sums = {'areas.csv': read_json(os.path.join(FIXTURE, 'MANIFEST.json'))['sha256']['areas.csv']}
    shutil.copy(os.path.join(FIXTURE, 'areas.csv.gz'), out)
    for key, codes in by.items():
        buf = io.StringIO()
        csv.writer(buf, lineterminator='\n').writerows([header] + codes)
        data = buf.getvalue().encode('utf-8')
        with gzip.open(os.path.join(out, key + '.csv.gz'), 'wb') as g:
            g.write(data)
        sums[key + '.csv'] = hashlib.sha256(data).hexdigest()
    man = read_json(os.path.join(FIXTURE, 'MANIFEST.json'))
    man.update(byFrame={k: len(v) for k, v in by.items()}, codes=len(rows) - 1, sha256=sums)
    write_json(os.path.join(out, 'MANIFEST.json'), man)
    return out


class Base(unittest.TestCase):
    keys = ()
    per_day = 1000
    gaps = False

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='gn-server-')
        cls.db = os.path.join(cls.tmp, 'addresses.sqlite')
        reg = gap_registry(os.path.join(cls.tmp, 'registry')) if cls.gaps else FIXTURE
        store.import_registry(reg, cls.db, log=QUIET)
        cls.srv = api.make_server(cls.db, '127.0.0.1', 0, issue_keys=cls.keys, per_day=cls.per_day, cors=['*'])
        cls.port = cls.srv.server_address[1]
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.srv.service.close()
        shutil.rmtree(cls.tmp)

    def call(self, method, path, body=None, key=None):
        c = http.client.HTTPConnection('127.0.0.1', self.port, timeout=30)
        headers = {}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers['Content-Type'] = 'application/json'
        if key:
            headers['Authorization'] = 'Bearer ' + key
        c.request(method, path, body=data, headers=headers)
        r = c.getresponse()
        raw = r.read()
        c.close()
        self.assertEqual(r.getheader('Content-Type'), 'application/json; charset=utf-8')
        return r.status, json.loads(raw.decode())

    def get(self, path):
        return self.call('GET', path)

    def error(self, path, status, code, method='GET', body=None, key=None):
        st, b = self.call(method, path, body, key)
        self.assertEqual(st, status, b)
        self.assertEqual(set(b), {'error'})
        self.assertEqual(b['error']['code'], code, b)
        self.assertTrue(b['error']['message'])
        return b


class ImportExport(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='gn-import-')
        self.db = os.path.join(self.tmp, 'a.sqlite')

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_round_trip_is_byte_identical(self):
        store.import_registry(FIXTURE, self.db, log=QUIET)
        out = os.path.join(self.tmp, 'out')
        store.export_registry(self.db, out, log=QUIET)
        for name in ('areas.csv.gz', 'CKY.csv.gz'):
            self.assertEqual(plain(os.path.join(out, name)), plain(os.path.join(FIXTURE, name)), name)
        with open(os.path.join(out, 'MANIFEST.json'), 'rb') as a, open(os.path.join(FIXTURE, 'MANIFEST.json'), 'rb') as b:
            self.assertEqual(a.read(), b.read())

    def test_reimport_is_safe(self):
        store.import_registry(FIXTURE, self.db, log=QUIET)
        msgs = []
        store.import_registry(FIXTURE, self.db, log=msgs.append)
        self.assertIn('nothing to do', msgs[-1])
        store.import_registry(FIXTURE, self.db, log=QUIET, force=True)
        c = store.connect(self.db, readonly=True)
        self.assertEqual(c.execute('SELECT count(*) FROM codes').fetchone()[0], 5646)
        c.close()

    def _copy(self):
        reg = os.path.join(self.tmp, 'reg')
        shutil.copytree(FIXTURE, reg)
        return reg

    def test_tampered_file_is_refused(self):
        reg = self._copy()
        data = plain(os.path.join(reg, 'CKY.csv.gz')).replace(b'Almamiya 1007', b'Almamiya 1008', 1)
        with gzip.open(os.path.join(reg, 'CKY.csv.gz'), 'wb') as f:
            f.write(data)
        with self.assertRaises(store.RegistryError) as e:
            store.import_registry(reg, self.db, log=QUIET)
        self.assertIn('SHA-256', str(e.exception))
        self.assertFalse(os.path.exists(self.db))

    def test_count_mismatch_is_refused(self):
        reg = self._copy()
        p = os.path.join(reg, 'MANIFEST.json')
        man = read_json(p)
        man['byFrame']['CKY'] += 1
        write_json(p, man)
        with self.assertRaises(store.RegistryError) as e:
            store.import_registry(reg, self.db, log=QUIET)
        self.assertIn('manifest says', str(e.exception))

    def test_other_country_is_refused(self):
        reg = self._copy()
        p = os.path.join(reg, 'MANIFEST.json')
        man = read_json(p)
        man['country'] = 'XX'
        write_json(p, man)
        with self.assertRaises(store.RegistryError):
            store.import_registry(reg, self.db, log=QUIET)

    def test_csv_dialect(self):
        self.assertEqual(store.csv_line(['a', '', 'b, c', 'say "x"', ' lead', '\\.']), 'a,,"b, c","say ""x"""," lead","\\."\n')


class ReadApi(Base):
    def test_health_and_info(self):
        st, b = self.get('/v1/health')
        self.assertEqual((st, b['status'], b['country'], b['codes'], b['issuing']), (200, 'ok', 'GN', 5646, False))
        self.assertEqual(b['registry_exported'], '2026-10-21T18:50:00Z')
        st, b = self.get('/v1/info')
        self.assertEqual(st, 200)
        self.assertEqual([z['key'] for z in b['zones']], ['CKY', 'BAS', 'MOY', 'HAU', 'FOR'])
        self.assertEqual(b['areas'], 17044)
        self.assertEqual(b['credit'], engine.CREDIT)
        self.assertEqual(b['licences']['data'], 'ODbL-1.0')

    def test_code_card_has_every_registry_column(self):
        rows = fixture_rows()
        for row in (rows[0], rows[len(rows) // 2], rows[-1]):
            st, b = self.get('/v1/codes/' + row['machine'])
            self.assertEqual(st, 200)
            for col in store.CODE_COLUMNS:
                want = row[col]
                got = b[col]
                self.assertEqual(str(got) if not isinstance(got, float) else got, float(want) if isinstance(got, float) else want, col)
            self.assertEqual(b['forms']['remembered'], row['home'])
            self.assertEqual(b['forms']['plate'], row['plate'])
            self.assertNotIn('-', b['forms']['plate'].split('·')[-1])
            self.assertEqual(b['frame']['key'], 'CKY')
            self.assertEqual(b['area']['zone'], row['zone'])
            self.assertEqual(b['bloc'], row['spot'][:6])

    def test_code_errors(self):
        self.error('/v1/codes/GN-00053-1007-5', 422, 'check_mismatch')
        self.error('/v1/codes/hello', 400, 'invalid_code')
        self.error('/v1/codes/GN-00053-1008-' + str(engine.ref.home_check(53, 1008)), 404, 'not_issued')

    def test_find_remembered_any_spelling(self):
        for q in ('Almamiya 1007', 'almamiya 1007', 'ALMAMIYA  10 07', 'Almamiyà 1007', 'ALMAMIYA · 1007', 'Almamiya 1007, Kaloum'):
            st, b = self.get('/v1/find?q=' + q.replace(' ', '%20').replace('·', '%C2%B7').replace(',', '%2C').replace('à', '%C3%A0'))
            self.assertEqual(st, 200, (q, b))
            self.assertEqual(b['kind'], 'remembered')
            self.assertEqual(b['matches'][0]['machine'], 'GN-00053-1007-6')

    def test_find_quartier_with_number(self):
        row = [r for r in fixture_rows() if r['home'].startswith('Coronthie 2')][0]
        n = row['number']
        for q in ('Coronthie 2 · %s' % n, 'coronthie 2 %s' % n, 'Coronthie 2 %s %s' % (n[:2], n[2:])):
            st, b = self.get('/v1/find?q=' + q.replace(' ', '%20').replace('·', '%C2%B7'))
            self.assertEqual((st, b['matches'][0]['machine']), (200, row['machine']), q)

    def test_find_machine_spot_and_street(self):
        st, b = self.get('/v1/find?q=gn-00053-1007-6')
        self.assertEqual((st, b['kind'], b['matches'][0]['home']), (200, 'machine', 'Almamiya 1007'))
        st, b = self.get('/v1/find?q=0%20229J%20VVG7')
        self.assertEqual((st, b['kind'], b['matches'][0]['machine']), (200, 'spot', 'GN-00053-1007-6'))
        st, b = self.get('/v1/find?q=Avenue%20du%20Port%2C%20Kaloum')
        self.assertEqual((st, b['kind']), (200, 'official_address'))
        self.assertGreater(b['total'], 20)
        self.assertEqual(b['count'], 20)
        self.assertTrue(b['truncated'])
        self.assertTrue(all(m['official_street'] == 'Avenue du Port, Kaloum' for m in b['matches']))
        st, b = self.get('/v1/find?q=Avenue%20du%20Port%2C%20Kaloum&limit=2')
        self.assertEqual(b['count'], 2)
        st, b = self.get('/v1/find?q=Avenue%20du%20Port%20%C2%B7%20Almamiya%201007')
        self.assertEqual((st, b['kind'], b['count'], b['matches'][0]['machine']), (200, 'official_address', 1, 'GN-00053-1007-6'))

    def test_find_errors(self):
        self.error('/v1/find', 400, 'bad_request')
        self.error('/v1/find?q=GN-00053-1007-5', 422, 'check_mismatch')
        self.error('/v1/find?q=Almamiya%201007-5', 422, 'check_mismatch')
        self.error('/v1/find?q=Almamiya%201008', 404, 'not_issued')
        self.error('/v1/find?q=Nowhereville%201007', 404, 'not_found')
        self.error('/v1/find?q=Almamiya', 400, 'invalid_code')
        self.error('/v1/find?q=0%20229J%20VVG', 400, 'invalid_code')
        self.error('/v1/find?q=4%20222J%20VVG7', 404, 'no_code_here')

    def test_at(self):
        st, b = self.get('/v1/at?lat=9.5154452&lng=-13.7093929')
        self.assertEqual((st, b['status'], b['code']['machine'], b['distance_m']), (200, 'found', 'GN-00053-1007-6', 0.0))
        st, b = self.get('/v1/at?lat=9.5154452&lng=-13.7092929')   # 11 m east
        self.assertEqual(b['status'], 'found')
        st, b = self.get('/v1/at?lat=9.5300&lng=-13.6950')
        self.assertEqual((st, b['status']), (200, 'none'))
        self.assertTrue(b['area']['zone'].startswith('0-'))
        st, b = self.get('/v1/at?lat=48.85&lng=2.35')
        self.assertEqual((st, b['status']), (200, 'outside'))
        self.error('/v1/at?lat=9.5', 400, 'bad_request')
        self.error('/v1/at?lat=abc&lng=1', 400, 'bad_request')
        self.error('/v1/at?lat=91&lng=1', 400, 'bad_request')

    def test_near(self):
        st, b = self.get('/v1/near?lat=9.5154452&lng=-13.7093929&radius=60&limit=5')
        self.assertEqual(st, 200)
        self.assertEqual(b['codes'][0]['machine'], 'GN-00053-1007-6')
        self.assertLessEqual(len(b['codes']), 5)
        ds = [c['distance_m'] for c in b['codes']]
        self.assertEqual(ds, sorted(ds))
        self.assertTrue(all(d <= 60 for d in ds))
        self.error('/v1/near?lat=9.5&lng=-13.7&radius=501', 400, 'bad_request')
        self.error('/v1/near?lat=9.5&lng=-13.7&limit=101', 400, 'bad_request')

    def test_verify(self):
        st, b = self.get('/v1/verify?code=GN-00053-1007-6')
        self.assertEqual((st, b['valid'], b['issued'], b['status']), (200, True, True, 'provisional'))
        st, b = self.get('/v1/verify?code=GN-00053-1070-6')
        self.assertEqual((b['valid'], b['check_ok'], b['syntax_ok']), (False, False, True))
        st, b = self.get('/v1/verify?code=GN-00053-1008-%d' % engine.ref.home_check(53, 1008))
        self.assertEqual((b['valid'], b['check_ok'], b['issued'], b['in_block_of']), (False, True, False, '0-00208'))
        st, b = self.get('/v1/verify?code=Almamiya')
        self.assertEqual((b['valid'], b['syntax_ok']), (False, False))
        self.error('/v1/verify', 400, 'bad_request')

    def test_spot(self):
        st, b = self.get('/v1/spot?lat=9.5154452&lng=-13.7093929')
        self.assertEqual((st, b['spot'], b['bloc'], b['frame']['key'], b['edge']), (200, '0 229J VVG7', '0 229J', 'CKY', False))
        # a point beyond Basse-Guinée's grid takes the grid's nearest edge cell (SPEC 3.4)
        st, b = self.get('/v1/spot?lat=9.0275327&lng=-13.2964538')
        self.assertEqual((st, b['spot'], b['frame']['key'], b['edge'], b['cell']['lat']), (200, '1 2F2C 2W2Q', 'BAS', True, 9.0300136))
        st, d = self.get('/v1/spot/decode?code=0229jvvg7')
        self.assertEqual((st, d['code']), (200, '0 229J VVG7'))
        self.assertLess(engine.dist_m(d['lat'], d['lng'], 9.5154452, -13.7093929), 3)
        self.error('/v1/spot?lat=48.85&lng=2.35', 422, 'outside')
        self.error('/v1/spot/decode?code=9%20229J%20VVG7', 400, 'invalid_code')
        self.error('/v1/spot/decode?code=0%20229J%20VVG7-2', 422, 'check_mismatch')
        self.error('/v1/spot/decode', 400, 'bad_request')

    def test_zones_and_areas(self):
        st, b = self.get('/v1/zones')
        self.assertEqual((st, b['count']), (200, 5))
        st, b = self.get('/v1/zones/cky')
        self.assertEqual((st, b['key'], b['counts']['total']), (200, 'CKY', 5646))
        self.assertEqual(len(b['areas']), 228)
        self.error('/v1/zones/XYZ', 404, 'not_found')
        st, b = self.get('/v1/areas/0-00209')
        self.assertEqual((st, b['plate_name'], b['blocks'], b['counts']['total']), (200, 'Manquepas', [{'lo': 1950, 'hi': 1999, 'size': 50}], 7))
        self.assertIn('0-00205', b['same_name'])
        self.error('/v1/areas/9-99999', 404, 'not_found')
        st, b = self.get('/v1/areas?name=manquepas')
        self.assertEqual((st, b['matched_by'], b['count']), (200, 'plate name', 4))
        st, b = self.get('/v1/areas?name=Missid%C3%A9%20Bhoundou%20Kalouma')
        self.assertEqual((st, b['matched_by'], b['areas'][0]['plate_name']), (200, 'alias', 'Kalouma'))
        st, b = self.get('/v1/areas?name=Madina%20March%C3%A9')
        self.assertEqual((st, b['areas'][0]['zone']), (200, '0-00008'))
        self.error('/v1/areas', 400, 'bad_request')

    def test_paging(self):
        seen, after = [], ''
        for _ in range(3):
            st, b = self.get('/v1/zones/CKY/codes?limit=1000&after=' + after)
            self.assertEqual(st, 200)
            seen += [c['machine'] for c in b['codes']]
            if not b['next']:
                break
            after = b['next']
        st, b = self.get('/v1/zones/CKY/codes?limit=1000&after=' + after)
        while b['next']:
            seen += [c['machine'] for c in b['codes']]
            st, b = self.get('/v1/zones/CKY/codes?limit=1000&after=' + b['next'])
        seen += [c['machine'] for c in b['codes']]
        self.assertEqual(seen, sorted(r['machine'] for r in fixture_rows()))
        self.error('/v1/zones/CKY/codes?limit=0', 400, 'bad_request')

    def test_routing_errors(self):
        self.error('/v1/nothing', 404, 'not_found')
        self.error('/v1/health', 405, 'method_not_allowed', method='POST', body={})
        self.error('/v1/codes', 403, 'read_only', method='POST', body={'lat': 9.5, 'lng': -13.7})
        self.error('/v1/codes/GN-00053-1007-6', 403, 'read_only', method='PATCH', body={'status': 'confirmed'})


class IssueApi(Base):
    keys = ('k-one', 'k-two')
    per_day = 10000

    def post(self, body, key='k-one'):
        return self.call('POST', '/v1/codes', body, key)

    def test_a_parity_with_the_issuer(self):
        """The same requests give the same numbers, forms and blocks as the N-Ways issuer."""
        cases = read_json(PARITY)['cases']
        blocks = 0
        for c in cases:
            body = {k: c[k] for k in ('lat', 'lng', 'of') if k in c}
            st, b = self.post(body)
            e = c['expected']
            self.assertEqual(st, 201, (c, b))
            got = {'zone': b['zone'], 'number': b['number'], 'machine': b['machine'], 'home': b['home'], 'plate': b['plate'],
                   'spoken': b['forms']['spoken'], 'plus_code': b['plus_code'], 'spot': b['spot']}
            if 'new_block' in b:
                got['new_blocks'] = [[b['new_block']['lo'], b['new_block']['hi']]]
                blocks += 1
            self.assertEqual(got, e, c)
            self.assertEqual((b['status'], b['issued']), ('provisional', 'on-demand'))
            self.assertEqual(b['entrance_kind'], 'door' if 'of' in c else 'centre')
        self.assertGreaterEqual(blocks, 3)
        # extension blocks are kept and exported
        st, a = self.get('/v1/areas/0-00214')
        self.assertEqual(len(a['blocks']), 2)
        out = os.path.join(self.tmp, 'export')
        store.export_registry(self.db, out, log=QUIET)
        rows = {r['zone']: r for r in csv.DictReader(plain(os.path.join(out, 'areas.csv.gz')).decode().splitlines())}
        self.assertEqual(rows['0-00214']['blocks'], '|'.join('%d-%d' % (x['lo'], x['hi']) for x in a['blocks']))
        man = read_json(os.path.join(out, 'MANIFEST.json'))
        self.assertEqual(man['codes'], 5646 + len(cases))
        db2 = os.path.join(self.tmp, 'again.sqlite')
        store.import_registry(out, db2, log=QUIET)
        s2 = Service(db2)
        self.assertEqual(s2.total(), 5646 + len(cases))
        self.assertEqual(s2.reg.area('0-00214').blocks, [[x['lo'], x['hi']] for x in a['blocks']])
        s2.close()

    def test_auth(self):
        self.error('/v1/codes', 401, 'unauthorised', method='POST', body={'lat': 9.5, 'lng': -13.7})
        self.error('/v1/codes', 401, 'unauthorised', method='POST', body={'lat': 9.5, 'lng': -13.7}, key='wrong')

    def test_duplicates(self):
        b = self.error('/v1/codes', 409, 'exists', method='POST', body={'lat': 9.5154452, 'lng': -13.7093929}, key='k-one')
        st, _ = self.call('GET', '/v1/health')
        b = self.call('POST', '/v1/codes', {'lat': 9.5154452 + 2 / 110574, 'lng': -13.7093929}, 'k-one')
        self.assertEqual((b[0], b[1]['error']['code'], b[1]['error']['existing']['machine']), (409, 'exists', 'GN-00053-1007-6'))
        # an outline over a published compound's entrance
        lat, lng = 9.5154452, -13.7093929
        d = 6 / 110574
        ring = [[lng - d, lat - d], [lng + d, lat - d], [lng + d, lat + d], [lng - d, lat + d]]
        st, b = self.post({'lat': lat + 4 * d, 'lng': lng + 4 * d, 'outline': ring})
        self.assertEqual((st, b['error']['code']), (409, 'exists'))

    def test_outline_rules(self):
        lat, lng = 9.5278, -13.7120
        st, b = self.call('GET', '/v1/at?lat=%f&lng=%f' % (lat, lng))
        self.assertEqual(b['status'], 'none')
        tiny = [[lng, lat], [lng + 1e-6, lat], [lng + 1e-6, lat + 1e-6]]
        st, b = self.post({'lat': lat, 'lng': lng, 'outline': tiny})
        self.assertEqual((st, b['error']['code']), (422, 'bad_outline'))
        big = [[lng, lat], [lng + 0.003, lat], [lng + 0.003, lat + 0.003], [lng, lat + 0.003]]
        st, b = self.post({'lat': lat, 'lng': lng, 'outline': big})
        self.assertEqual((st, b['error']['code']), (422, 'bad_outline'))
        d = 5 / 110574
        ring = [[lng - d, lat - d], [lng + d, lat - d], [lng + d, lat + d], [lng - d, lat + d], [lng - d, lat - d]]
        st, b = self.post({'lat': lat, 'lng': lng, 'outline': ring})
        self.assertEqual(st, 201, b)
        self.assertEqual((b['structures'], b['class'], b['kind']), (1, 'residential.house', 'building'))
        self.assertAlmostEqual(b['floor_area_m2'], 100.0, delta=1.5)
        # the same building drawn again, shifted by a metre
        e = 1 / 110574
        again = [[x + e, y] for x, y in ring]
        st, b2 = self.post({'lat': lat + 5 * d, 'lng': lng + e, 'outline': again})
        self.assertEqual((st, b2['error']['code'], b2['error']['existing']['machine']), (409, 'exists', b['machine']))
        # a point inside a drawn outline is that code
        st, at = self.get('/v1/at?lat=%f&lng=%f' % (lat + 0.8 * d, lng - 0.8 * d))
        self.assertEqual((at['status'], at['code']['machine']), ('found', b['machine']))

    def test_doors_and_places(self):
        self.error('/v1/codes', 404, 'not_found', method='POST', body={'lat': 9.5154, 'lng': -13.7094, 'of': 'GN-00053-1008-' + str(engine.ref.home_check(53, 1008))}, key='k-one')
        self.error('/v1/codes', 422, 'too_far', method='POST', body={'lat': 9.5174452, 'lng': -13.7093929, 'of': 'GN-00053-1007-6'}, key='k-one')
        self.error('/v1/codes', 422, 'outside', method='POST', body={'lat': 48.85, 'lng': 2.35}, key='k-one')
        self.error('/v1/codes', 400, 'bad_request', method='POST', body={'lat': 'x', 'lng': 1}, key='k-one')
        self.error('/v1/codes', 400, 'bad_request', method='POST', body={'lat': True, 'lng': -13.7}, key='k-one')
        wrong = (engine.ref.home_check(53, 1007) + 1) % 10
        self.error('/v1/codes', 422, 'check_mismatch', method='POST', body={'lat': 9.5154, 'lng': -13.7094, 'of': 'GN-00053-1007-%d' % wrong}, key='k-one')
        self.error('/v1/codes', 400, 'bad_json', method='POST', body=[1, 2], key='k-one')

    def test_patch(self):
        rows = fixture_rows()
        m = rows[10]['machine']
        st, b = self.call('PATCH', '/v1/codes/' + m, {'status': 'confirmed'}, 'k-two')
        self.assertEqual((st, b['status']), (200, 'confirmed'))
        lat, lng = float(rows[10]['entrance_lat']), float(rows[10]['entrance_lng'])
        st, b = self.call('PATCH', '/v1/codes/' + m, {'entrance': {'lat': lat + 20 / 110574, 'lng': lng, 'kind': 'gate'}}, 'k-two')
        self.assertEqual((st, b['entrance_kind'], b['entrance_lat']), (200, 'gate', round(lat + 20 / 110574, 7)))
        self.assertEqual(b['spot'], engine.ref.encode_spot(lat + 20 / 110574, lng, engine.ref.load_frames()[0]))
        self.assertEqual(b['plus_code'], engine.plus_code(lat + 20 / 110574, lng))
        self.error('/v1/codes/' + m, 422, 'too_far', method='PATCH', body={'entrance': {'lat': lat + 0.002, 'lng': lng}}, key='k-two')
        self.error('/v1/codes/' + m, 422, 'bad_status', method='PATCH', body={'status': 'gone'}, key='k-two')
        self.error('/v1/codes/' + m, 400, 'bad_request', method='PATCH', body={'home': 'x'}, key='k-two')
        st, b = self.call('PATCH', '/v1/codes/' + m, {'status': 'retired'}, 'k-two')
        self.assertEqual((st, b['status']), (200, 'retired'))
        self.error('/v1/codes/' + m, 409, 'retired', method='PATCH', body={'status': 'confirmed'}, key='k-two')
        self.error('/v1/find?q=' + rows[10]['home'].replace(' ', '%20').replace('·', '%C2%B7'), 410, 'retired')
        # a retired number stays taken: it is in the area's numbers that a new compound avoids
        c = store.connect(self.db, readonly=True)
        nums = [r[0] for r in c.execute('SELECT num FROM codes WHERE "zone" = ?', (rows[10]['zone'],))]
        c.close()
        self.assertIn(int(rows[10]['number']), nums)


class RateLimit(Base):
    keys = ('only',)
    per_day = 2

    def test_daily_limit_per_key(self):
        row = fixture_rows()[0]
        lat, lng = float(row['entrance_lat']), float(row['entrance_lng'])
        for i in range(2):
            st, b = self.call('POST', '/v1/codes', {'lat': lat + (i + 1) * 4 / 110574, 'lng': lng, 'of': row['machine']}, 'only')
            self.assertEqual(st, 201, b)
        self.error('/v1/codes', 429, 'rate_limited', method='POST', body={'lat': lat, 'lng': lng + 5 / 111000, 'of': row['machine']}, key='only')


class Gaps(Base):
    """A point in no frame outline but within 0.01 degrees of one is in Guinea
    (SPEC 2): it is found, takes a code and an entrance moves there."""
    keys = ('k-one',)
    gaps = True

    def test_found_at_its_own_entrance(self):
        rows = gap_rows()
        self.assertGreaterEqual(len(rows), 20)
        for r in rows:
            st, b = self.get('/v1/at?lat=%s&lng=%s' % (r['entrance_lat'], r['entrance_lng']))
            self.assertEqual((st, b['status'], b['code']['machine'], b['distance_m']), (200, 'found', r['machine'], 0.0), r)
            self.assertEqual((b['frame']['key'], b['area']['zone']), (r['frame'], r['zone']), r)
            st, s = self.get('/v1/spot?lat=%s&lng=%s' % (r['entrance_lat'], r['entrance_lng']))
            self.assertEqual((st, s['spot'], s['frame']['key']), (200, r['spot'], r['frame']), r)
            st, n = self.get('/v1/near?lat=%s&lng=%s&radius=10' % (r['entrance_lat'], r['entrance_lng']))
            self.assertEqual(n['codes'][0]['machine'], r['machine'])

    def test_issue_in_a_gap(self):
        # free points in no outline, inside the national border; frame, spot and area by SPEC 2, 3.4 and 4
        for lat, lng, frame, spot, zone in ((7.7975007, -8.0927296, 'FOR', '4 4JQ2 X6R7', '4-17041'),
                                            (12.0595992, -9.8370793, 'HAU', '3 RC32 MQ5X', '3-08998')):
            st, at = self.get('/v1/at?lat=%s&lng=%s' % (lat, lng))
            self.assertEqual((at['status'], at['frame']['key'], at['area']['zone']), ('none', frame, zone))
            st, b = self.call('POST', '/v1/codes', {'lat': lat, 'lng': lng}, 'k-one')
            self.assertEqual((st, b['zone'], b['spot']), (201, zone, spot), b)
            st, at = self.get('/v1/at?lat=%s&lng=%s' % (lat, lng))
            self.assertEqual((at['status'], at['code']['machine']), ('found', b['machine']))
        # a door of a code in a gap
        r = gap_rows()[1]
        lat, lng = float(r['entrance_lat']) + 15 / 110574, float(r['entrance_lng'])
        st, b = self.call('POST', '/v1/codes', {'lat': lat, 'lng': lng, 'of': r['machine']}, 'k-one')
        self.assertEqual((st, b['zone']), (201, r['zone']), b)
        # beyond 0.01 degrees of every outline, or abroad, a point is outside
        for lat, lng in ((12.6, -8.0), (7.0, -9.4), (8.0, -14.0), (48.85, 2.35)):
            st, at = self.get('/v1/at?lat=%s&lng=%s' % (lat, lng))
            self.assertEqual((st, at['status']), (200, 'outside'))
            self.error('/v1/codes', 422, 'outside', method='POST', body={'lat': lat, 'lng': lng}, key='k-one')

    def test_move_entrance_in_a_gap(self):
        r = gap_rows()[-1]
        lat, lng = float(r['entrance_lat']) - 20 / 110574, float(r['entrance_lng'])
        st, b = self.call('PATCH', '/v1/codes/' + r['machine'], {'entrance': {'lat': lat, 'lng': lng}}, 'k-one')
        self.assertEqual((st, b['entrance_lat']), (200, round(lat, 7)), b)
        self.assertEqual(b['spot'], engine.ref.spot_of(lat, lng, engine.ref.load_frames())[0])
        st, at = self.get('/v1/at?lat=%s&lng=%s' % (lat, lng))
        self.assertEqual((at['status'], at['code']['machine']), ('found', r['machine']))


class TheBorderDecides(Base):
    """The national border decides (SPEC 2.1): a point in a frame outline but more
    than 300 m outside the border is in a neighbouring country. Points on one line
    across the border of Guinée forestière, all inside the frame's outline."""
    keys = ('k-one',)
    gaps = True
    INSIDE = (8.5272053, -10.6192465)       # 150 m inside the border
    NEAR = (8.5284347, -10.6227597)         # 260 m outside: still Guinea
    BEYOND = (8.5286446, -10.6233596)       # 330 m outside
    FAR = (8.5308106, -10.6295492)          # 1 km outside

    def test_border_file(self):
        b = engine.ref.Border()
        self.assertLess(os.path.getsize(engine.ref.BORDER_FILE), 1 << 20)
        self.assertGreater(b.deviation, 0)
        self.assertEqual(b.limit, engine.ref.BORDER_M - math.ceil(b.deviation))
        self.assertTrue(b.inside(*self.INSIDE))
        self.assertEqual(b.outside_m(*self.INSIDE), 0.0)
        self.assertAlmostEqual(b.outside_m(*self.NEAR), 260.0, delta=b.deviation)
        for p in (self.BEYOND, self.FAR):
            self.assertFalse(b.holds(*p))
            self.assertIsNotNone(engine.ref.frame_of(p[0], p[1], engine.ref.load_frames()), p)
        self.assertTrue(b.holds(9.5154452, -13.7093929))    # Kaloum

    def test_no_code_across_the_border(self):
        for lat, lng in (self.BEYOND, self.FAR):
            st, at = self.get('/v1/at?lat=%s&lng=%s' % (lat, lng))
            self.assertEqual((st, at['status']), (200, 'outside'))
            self.error('/v1/codes', 422, 'outside', method='POST', body={'lat': lat, 'lng': lng}, key='k-one')
        st, at = self.get('/v1/at?lat=%s&lng=%s' % self.NEAR)
        self.assertEqual((at['status'], at['frame']['key']), ('none', 'FOR'))
        st, b = self.call('POST', '/v1/codes', {'lat': self.NEAR[0], 'lng': self.NEAR[1]}, 'k-one')
        self.assertEqual(st, 201, b)
        # its entrance never moves across the border, and another door there is refused
        self.error('/v1/codes/' + b['machine'], 422, 'outside', method='PATCH',
                   body={'entrance': {'lat': self.BEYOND[0], 'lng': self.BEYOND[1]}}, key='k-one')
        self.error('/v1/codes', 422, 'outside', method='POST',
                   body={'lat': self.BEYOND[0], 'lng': self.BEYOND[1], 'of': b['machine']}, key='k-one')
        st, at = self.get('/v1/at?lat=%s&lng=%s' % self.NEAR)
        self.assertEqual((at['status'], at['code']['machine']), ('found', b['machine']))
        st, p = self.call('PATCH', '/v1/codes/' + b['machine'], {'entrance': {'lat': 8.5282548, 'lng': -10.6222455}}, 'k-one')   # 200 m outside
        self.assertEqual((st, p['entrance_lat']), (200, 8.5282548), p)


if __name__ == '__main__':
    unittest.main()
