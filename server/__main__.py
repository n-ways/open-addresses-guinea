"""Command line: import, serve, export."""
import argparse
import os
import sys

from . import store


def env_list(name):
    return [x.strip() for x in os.environ.get(name, '').split(',') if x.strip()]


def main(argv=None):
    p = argparse.ArgumentParser(prog='python3 -m server', description='N-Ways Addressing for Guinea: registry server.')
    sub = p.add_subparsers(dest='cmd')

    i = sub.add_parser('import', help='load a published registry into SQLite (verifies every SHA-256 and count)')
    i.add_argument('--registry', default='registry', help='folder with MANIFEST.json and the *.csv.gz files')
    i.add_argument('--db', default=os.environ.get('ADDRESSES_DB', 'data/addresses.sqlite'))
    i.add_argument('--force', action='store_true', help='re-import even when the database already holds this registry')
    i.add_argument('--replace-local-changes', action='store_true',
                   help='discard codes issued or changed in this database (export them first)')

    s = sub.add_parser('serve', help='serve the JSON API')
    s.add_argument('--db', default=os.environ.get('ADDRESSES_DB', 'data/addresses.sqlite'))
    s.add_argument('--host', default=os.environ.get('HOST', '0.0.0.0'))
    s.add_argument('--port', type=int, default=int(os.environ.get('PORT', '8080')))

    st = sub.add_parser('start', help='import the registry when the database does not exist yet, then serve (containers)')
    st.add_argument('--registry', default=os.environ.get('REGISTRY_DIR', 'registry'))
    st.add_argument('--db', default=os.environ.get('ADDRESSES_DB', 'data/addresses.sqlite'))
    st.add_argument('--host', default=os.environ.get('HOST', '0.0.0.0'))
    st.add_argument('--port', type=int, default=int(os.environ.get('PORT', '8080')))

    e = sub.add_parser('export', help='write the registry in the published format')
    e.add_argument('--db', default=os.environ.get('ADDRESSES_DB', 'data/addresses.sqlite'))
    e.add_argument('--out', required=True)

    a = p.parse_args(argv)
    if a.cmd == 'import':
        try:
            store.import_registry(a.registry, a.db, force=a.force, replace_local=a.replace_local_changes)
        except store.RegistryError as err:
            print('import refused: %s' % err, file=sys.stderr)
            return 1
        return 0
    if a.cmd == 'start':
        if not os.path.exists(a.db):
            print('first start: importing %s into %s' % (a.registry, a.db), file=sys.stderr)
            try:
                store.import_registry(a.registry, a.db, log=lambda m: print(m, file=sys.stderr))
            except store.RegistryError as err:
                print('import refused: %s' % err, file=sys.stderr)
                return 1
        a.cmd = 'serve'
    if a.cmd == 'serve':
        if not os.path.exists(a.db):
            print('%s does not exist: run "python3 -m server import" first' % a.db, file=sys.stderr)
            return 1
        from .api import serve
        try:
            per_day = int(os.environ.get('ISSUE_PER_DAY', '5'))
        except ValueError:
            print('ISSUE_PER_DAY must be a whole number', file=sys.stderr)
            return 1
        serve(a.db, a.host, a.port, env_list('ISSUE_KEYS'), per_day, env_list('CORS_ORIGINS'))
        return 0
    if a.cmd == 'export':
        store.export_registry(a.db, a.out)
        return 0
    p.print_help()
    return 2


if __name__ == '__main__':
    sys.exit(main())
