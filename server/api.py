"""HTTP layer: routes /v1 requests to the service and writes JSON."""
import json
import logging
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, unquote, urlsplit

from .service import ApiError, Service

MAX_BODY = 64 * 1024
log = logging.getLogger('addresses')

ROUTES = [
    ('GET', r'/v1/health', 'health'),
    ('GET', r'/v1/info', 'info'),
    ('GET', r'/v1/find', 'find'),
    ('GET', r'/v1/at', 'at'),
    ('GET', r'/v1/near', 'near'),
    ('GET', r'/v1/verify', 'verify'),
    ('GET', r'/v1/spot', 'spot'),
    ('GET', r'/v1/spot/decode', 'spot_decode'),
    ('GET', r'/v1/zones', 'zones'),
    ('GET', r'/v1/zones/(?P<key>[^/]+)', 'zone'),
    ('GET', r'/v1/zones/(?P<key>[^/]+)/codes', 'zone_codes'),
    ('GET', r'/v1/areas', 'areas'),
    ('GET', r'/v1/areas/(?P<zone>[^/]+)', 'get_area'),
    ('GET', r'/v1/codes/(?P<machine>[^/]+)', 'get_code'),
    ('POST', r'/v1/codes', 'issue'),
    ('PATCH', r'/v1/codes/(?P<machine>[^/]+)', 'patch'),
]
COMPILED = [(m, re.compile('^' + p + '/?$'), h) for m, p, h in ROUTES]


class Handler(BaseHTTPRequestHandler):
    server_version = 'n-ways-addresses'
    sys_version = ''

    def version_string(self):
        return self.server_version
    protocol_version = 'HTTP/1.1'

    @property
    def svc(self):
        return self.server.service

    def log_message(self, fmt, *args):
        log.info('%s %s', self.address_string(), fmt % args)

    def _cors(self):
        origins = self.server.cors
        if not origins:
            return
        origin = self.headers.get('Origin')
        if '*' in origins:
            self.send_header('Access-Control-Allow-Origin', '*')
        elif origin and origin in origins:
            self.send_header('Access-Control-Allow-Origin', origin)
            self.send_header('Vary', 'Origin')

    def _send(self, status, body, extra=None):
        data = json.dumps(body, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self._cors()
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(data)

    def _route(self, method):
        t0 = time.time()
        url = urlsplit(self.path)
        path = url.path
        params = {k: v[-1] for k, v in parse_qs(url.query, keep_blank_values=True).items()}
        allowed = set()
        try:
            self._raw = b''
            if method in ('POST', 'PATCH', 'PUT', 'DELETE'):
                try:
                    n = int(self.headers.get('Content-Length') or 0)
                except ValueError:
                    n = -1
                if n < 0 or n > MAX_BODY:
                    self.close_connection = True
                    raise ApiError(413, 'too_large', 'The body must be JSON of at most 64 KB, with a Content-Length.')
                self._raw = self.rfile.read(n) if n else b''
            for m, rx, name in COMPILED:
                hit = rx.match(path)
                if not hit:
                    continue
                if m != method and not (method == 'HEAD' and m == 'GET'):
                    allowed.add(m)
                    continue
                args = {k: unquote(v) for k, v in hit.groupdict().items()}
                status, body = self._call(name, args, params)
                self._send(status, body)
                return
            if allowed:
                raise ApiError(405, 'method_not_allowed', '%s is not allowed here. Allowed: %s.' % (method, ', '.join(sorted(allowed))))
            raise ApiError(404, 'not_found', 'No endpoint %s. See /v1/info and the API documentation.' % path)
        except ApiError as e:
            extra = {'Allow': ', '.join(sorted(allowed))} if e.status == 405 else None
            if e.status == 401:
                extra = {'WWW-Authenticate': 'Bearer'}
            self._send(e.status, e.body(), extra)
        except Exception:
            log.exception('internal error on %s %s', method, path)
            self._send(500, {'error': {'code': 'internal', 'message': 'Internal error. The server log has the details.'}})
        finally:
            log.debug('%s %s %.1f ms', method, path, (time.time() - t0) * 1000)

    def _body(self):
        raw = self._raw
        if not raw:
            raise ApiError(400, 'bad_json', 'A JSON body is required.')
        try:
            return json.loads(raw.decode('utf-8'))
        except (ValueError, UnicodeDecodeError):
            raise ApiError(400, 'bad_json', 'The body is not valid JSON.')

    def _call(self, name, args, params):
        s = self.svc
        if name in ('health', 'info', 'zones'):
            return getattr(s, name)()
        if name in ('find', 'at', 'near', 'verify', 'spot', 'spot_decode', 'areas'):
            return getattr(s, name)(params)
        if name == 'zone':
            return s.zone(args['key'])
        if name == 'zone_codes':
            return s.zone_codes(args['key'], params)
        if name == 'get_area':
            return s.get_area(args['zone'])
        if name == 'get_code':
            return s.get_code(args['machine'])
        who = s.authorise(self.headers.get('Authorization'))
        body = self._body()
        if name == 'issue':
            return s.issue(body, who)
        return s.patch(args['machine'], body, who)

    def do_GET(self):
        self._route('GET')

    def do_HEAD(self):
        self._route('HEAD')

    def do_POST(self):
        self._route('POST')

    def do_PATCH(self):
        self._route('PATCH')

    def do_PUT(self):
        self._route('PUT')

    def do_DELETE(self):
        self._route('DELETE')

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PATCH, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Authorization, Content-Type')
        self.send_header('Access-Control-Max-Age', '600')
        self.send_header('Content-Length', '0')
        self.end_headers()


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def make_server(db, host='0.0.0.0', port=8080, issue_keys=(), per_day=5, cors=()):
    srv = Server((host, port), Handler)
    srv.service = Service(db, issue_keys=issue_keys, per_day=per_day)
    srv.cors = [o for o in cors if o]
    return srv


def serve(db, host, port, issue_keys, per_day, cors):
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format='%(asctime)s %(levelname)s %(message)s')
    srv = make_server(db, host, port, issue_keys, per_day, cors)
    mode = 'issuing (%d key%s, %d codes per key per day)' % (len(srv.service.keys), '' if len(srv.service.keys) == 1 else 's', per_day) \
        if srv.service.keys else 'read-only'
    log.info('serving %d codes from %s on http://%s:%d/v1 (%s)', srv.service.total(), db, host, port, mode)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
        srv.service.close()
