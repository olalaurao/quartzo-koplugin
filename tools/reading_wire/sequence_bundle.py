"""Exact-source disposable TLS bundle. Never provision a phone or attest hardware."""
import argparse
import base64
import ipaddress
import pathlib
import re
import shutil
import subprocess
import tempfile
import time

from probe_bundle import (BASELINE, ROOT, encoded, hexadecimal, native_snapshot,
                          parse, plain_root, read, sha)

NAME = 'quartzo-wire-tls-probe'
REVISION = 'canonical-wire-sequence-v1'
SOURCE_MAP = {
    'codec.lua': 'tools/reading_wire/codec.lua',
    'koreader_deps.lua': 'tools/reading_wire/koreader_deps.lua',
    'exchange.lua': 'tools/reading_wire/exchange.lua',
    'sequence.lua': 'tools/reading_wire/sequence.lua',
    'client.lua': 'tools/transport_probe/client.lua',
    'kindle.lua': 'tools/reading_wire/sequence_kindle.lua',
    'run.sh': 'tools/transport_probe/run.sh',
    'menu.json': 'tools/reading_wire/sequence_menu.json',
    'config.xml': 'tools/reading_wire/sequence_config.xml',
}
INPUTS = {'private-session.json', 'server.pem', 'untrusted.pem', 'synthetic-fixture.json'}
RUNTIME = {'run.lock', 'launcher-status.txt', 'device-observation.json', 'device-observation.json.tmp'}


def private_directory(path, fresh=False):
    path = pathlib.Path(path).absolute()
    parent = plain_root(path.parent)
    path = parent / path.name
    if not path.is_relative_to(pathlib.Path(tempfile.gettempdir()).resolve()):
        raise ValueError('Private TLS bundles must stay in temporary storage')
    if any((directory / '.git').exists() for directory in (path, *path.parents)):
        raise ValueError('Private TLS bundle inside Git refused')
    if path.is_symlink() or path.is_junction() or (fresh and path.exists()):
        raise ValueError('Existing or linked TLS bundle preserved')
    return path if fresh else plain_root(path)


def read_sources(revision):
    if not hexadecimal(revision, 40):
        raise ValueError('Exact committed diagnostic source required')
    resolved = subprocess.run(['git', 'rev-parse', revision + '^{commit}'], cwd=ROOT,
                              capture_output=True, check=True).stdout.decode().strip()
    if resolved != revision:
        raise ValueError('Exact diagnostic commit mismatch')
    values = {}
    for name, source in SOURCE_MAP.items():
        value = subprocess.run(['git', 'show', revision + ':' + source], cwd=ROOT,
                               capture_output=True, check=True).stdout
        if name == 'run.sh':
            if value.count(b'quartzo-transport-probe') != 1:
                raise ValueError('Unsupported launcher source')
            value = value.replace(b'quartzo-transport-probe', NAME.encode())
        if not value or len(value) > 65536 or b'\r' in value:
            raise ValueError('Unsupported diagnostic source bytes')
        values[name] = value
    return values


def inputs(directory, live=False):
    values = {name: read(directory / name, 16384) for name in INPUTS}
    session = parse(values['private-session.json'])
    if (set(session) != {'endpoint', 'token', 'run_id', 'not_before_epoch', 'expires_at_epoch'}
            or not hexadecimal(session['run_id'], 32)
            or not isinstance(session['token'], str)
            or re.fullmatch(r'[A-Za-z0-9_-]{43}', session['token']) is None):
        raise ValueError('Invalid private synthetic session')
    match = re.fullmatch(r'https://([0-9.]+):([0-9]+)', session['endpoint'])
    if not match or not 1024 <= int(match[2]) <= 65535:
        raise ValueError('Explicit private HTTPS endpoint required')
    address = ipaddress.IPv4Address(match[1])
    if not any(address in ipaddress.IPv4Network(network) for network in
               ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '127.0.0.1/32')):
        raise ValueError('Unsupported diagnostic network')
    start, expiry = session['not_before_epoch'], session['expires_at_epoch']
    if type(start) is not int or type(expiry) is not int or not 0 < expiry-start <= 1800:
        raise ValueError('Invalid diagnostic lifetime')
    if live and not start <= time.time() < expiry-30:
        raise ValueError('Diagnostic session not currently usable')
    for name in ('server.pem', 'untrusted.pem'):
        if b'-----BEGIN CERTIFICATE-----' not in values[name] or b'PRIVATE KEY' in values[name]:
            raise ValueError('Only public test certificates may leave the phone session')
    if values['server.pem'] == values['untrusted.pem']:
        raise ValueError('Distinct test trust material required')
    fixture = parse(values['synthetic-fixture.json'])
    scope = 'synthetic-wire-' + session['run_id']
    if (type(fixture.get('schema_version')) is not int or fixture.get('schema_version') != 1
            or fixture.get('fixture_revision') != 'canonical-wire-synthetic-v1'
            or fixture.get('run_id') != session['run_id'] or fixture.get('canonical_ack') is not False
            or fixture.get('physical_execution_attested') is not False
            or fixture.get('binding') != dict(binding_id=scope, vault_scope=scope,
                                             device_id='synthetic-wire-device', source_epoch=scope)
            or type(fixture.get('expected_unique_events')) is not int or fixture.get('expected_unique_events') != 3
            or type(fixture.get('expected_native_seconds')) is not int or fixture.get('expected_native_seconds') != 120
            or not isinstance(fixture.get('expected_shards'), list) or len(fixture['expected_shards']) != 3):
        raise ValueError('Unsupported synthetic fixture')
    paths = set()
    for shard in fixture['expected_shards']:
        if not isinstance(shard, dict) or set(shard) != {'path', 'sha256', 'bytes_base64'}:
            raise ValueError('Unsupported expected shard')
        path, digest = shard['path'], shard['sha256']
        if (not hexadecimal(digest, 64) or not isinstance(path, str)
                or re.fullmatch(r'sessions/reading_activity_v1/[a-f0-9]{64}/[a-f0-9]{64}/[0-9]{4}/(0[1-9]|1[0-2])/[a-f0-9]{64}\.jsonl', path) is None
                or not path.endswith('/' + digest + '.jsonl') or path in paths):
            raise ValueError('Unsupported expected shard path')
        value = base64.b64decode(shard['bytes_base64'], validate=True)
        if not 0 < len(value) <= 8192 or sha(value) != digest:
            raise ValueError('Expected shard bytes do not match')
        paths.add(path)
    return values, session, fixture


def prepare(session_directory, output, revision):
    source, output = private_directory(session_directory), private_directory(output, fresh=True)
    values, session, _ = inputs(source, live=True)
    values.update(read_sources(revision))
    manifest = dict(probe_revision=REVISION, run_id=session['run_id'], koreader_baseline=BASELINE,
                    source_commit=revision, files={name: sha(value) for name, value in values.items()})
    output.mkdir(mode=0o700, exist_ok=False)
    for name, value in {**values, 'bundle-manifest.json': encoded(manifest)}.items():
        with (output / name).open('xb') as stream:
            stream.write(value)
    verify_bundle(output)
    return manifest


def verify_bundle(directory, allow_runtime=False):
    directory = plain_root(directory)
    expected = set(SOURCE_MAP) | INPUTS | {'bundle-manifest.json'}
    actual = {entry.name for entry in directory.iterdir()}
    if not expected <= actual or actual - expected - (RUNTIME if allow_runtime else set()):
        raise ValueError('Unexpected TLS bundle entry')
    for name in actual:
        path = directory / name
        if path.is_symlink() or path.is_junction():
            raise ValueError('Linked TLS bundle entry refused')
        if name == 'run.lock':
            if not path.is_dir() or any(path.iterdir()):
                raise ValueError('Invalid single-use lock')
        elif not path.is_file():
            raise ValueError('Regular TLS bundle file required')
    manifest_bytes = read(directory / 'bundle-manifest.json', 8192)
    manifest = parse(manifest_bytes)
    if (set(manifest) != {'probe_revision', 'run_id', 'koreader_baseline', 'source_commit', 'files'}
            or manifest['probe_revision'] != REVISION or manifest['koreader_baseline'] != BASELINE
            or not isinstance(manifest['files'], dict) or set(manifest['files']) != set(SOURCE_MAP) | INPUTS):
        raise ValueError('Unsupported TLS bundle manifest')
    values, session, _ = inputs(directory)
    values.update(read_sources(manifest['source_commit']))
    if session['run_id'] != manifest['run_id']:
        raise ValueError('TLS session identity mismatch')
    for name, expected_bytes in values.items():
        value = read(directory / name, 65536)
        if value != expected_bytes or sha(value) != manifest['files'][name]:
            raise ValueError('TLS bundle changed')
    return manifest, sha(manifest_bytes)


def install(bundle, root):
    bundle, root = private_directory(bundle), plain_root(root)
    manifest, digest = verify_bundle(bundle)
    inputs(bundle, live=True)
    native = native_snapshot(root)
    extensions = plain_root(root / 'extensions')
    if extensions.parent != root or shutil.disk_usage(root).free < 4*1024*1024:
        raise ValueError('Mounted target unavailable')
    target = extensions / NAME
    if target.exists() or target.is_symlink() or target.is_junction():
        raise ValueError('Existing diagnostic preserved')
    target.mkdir(exist_ok=False)
    for name in set(SOURCE_MAP) | INPUTS | {'bundle-manifest.json'}:
        with (target / name).open('xb') as stream:
            stream.write(read(bundle / name, 65536))
    if verify_bundle(target) != (manifest, digest) or native_snapshot(root) != native:
        raise ValueError('Installed diagnostic changed')
    return dict(probe_revision=REVISION, run_id=manifest['run_id'], source_commit=manifest['source_commit'],
                manifest_digest=digest, native_source_sha256=native, canonical_ack=False,
                physical_execution_attested=False, production_changed=False)


def collect(bundle, root, observation, android_directory):
    manifest, digest = verify_bundle(private_directory(bundle))
    root, android = plain_root(root), plain_root(android_directory)
    target = root / 'extensions' / NAME
    if verify_bundle(target, allow_runtime=True) != (manifest, digest):
        raise ValueError('Installed TLS bundle mismatch')
    expected = dict(probe_revision=REVISION, run_id=manifest['run_id'], source_commit=manifest['source_commit'],
                    manifest_digest=digest, native_source_sha256=native_snapshot(root), canonical_ack=False,
                    physical_execution_attested=False, production_changed=False)
    if encoded(parse(read(observation, 4096))) != encoded(expected):
        raise ValueError('Installation observation mismatch')
    if read(target / 'launcher-status.txt', 64).strip() != b'completed' or (target / 'device-observation.json.tmp').exists():
        raise ValueError('Launcher/report incomplete')
    if not (target / 'run.lock').is_dir():
        raise ValueError('Single-use launch not observed')
    device = parse(read(target / 'device-observation.json', 12288))
    required = dict(probe_revision=REVISION, phase='wire_claims_checked', source_data='synthetic',
        run_id=manifest['run_id'], source_commit=manifest['source_commit'], manifest_digest=digest,
        canonical_ack=False, canonical_persistence_proven=False, physical_execution_attested=False,
        source_cursor_changed=False, statistics_accessed=False, wifi_changed=False,
        attempts=10, checked_responses=5, deliberately_discarded_responses=1,
        lua_version='Lua 5.1', jit_arch='arm', koreader_version=BASELINE,
        native_source_sha256=expected['native_source_sha256'])
    if set(device) != set(required) | {'steps', 'jit_version', 'json_version', 'luasec_version'}:
        raise ValueError('Unexpected device observation')
    for key, value in required.items():
        if type(device[key]) is not type(value) or device[key] != value:
            raise ValueError('Device sequence observations mismatch')
    for key, pattern in (('jit_version', r'LuaJIT 2\.1[ A-Za-z0-9.()_-]{0,96}'),
                         ('json_version', r'dkjson [0-9]+\.[0-9]+'),
                         ('luasec_version', r'[A-Za-z0-9 .()_-]{1,64}')):
        if not isinstance(device[key], str) or re.fullmatch(pattern, device[key]) is None:
            raise ValueError('Unsupported native runtime observation')
    steps = ['untrusted_certificate_rejected', 'unauthorized', 'rate_limited', 'server_retryable',
             'deliberately_discarded_response', 'seed_1', 'mixed_1', 'mixed_2',
             'within_request_conflict_1', 'within_request_conflict_2']
    if not isinstance(device['steps'], list) or len(device['steps']) != 10:
        raise ValueError('Incomplete finite sequence')
    batches = []
    for index, (step, name) in enumerate(zip(device['steps'], steps), 1):
        nonce = 'qrtr_' + manifest['run_id'][:16] + format(index, '016x')
        if (set(step) != {'step', 'request_id', 'batch_id', 'request_sha256'} or step['step'] != name
                or step['request_id'] != nonce or not hexadecimal(step['request_sha256'], 64)
                or not isinstance(step['batch_id'], str) or re.fullmatch(r'qrtb_[a-f0-9]{64}', step['batch_id']) is None):
            raise ValueError('Sequence request binding mismatch')
        batches.append(step['batch_id'])
    if len(set(batches)) != 3 or len(set(batches[:6])) != 1 or batches[6] != batches[7] or batches[8] != batches[9]:
        raise ValueError('Immutable retry batch mismatch')
    _, _, fixture = inputs(target)
    phone = parse(read(android / 'completed.json', 16384))
    phone_required = dict(probe_revision='canonical-wire-tls-v1', phase='completed', run_id=manifest['run_id'],
        source_data='synthetic', request_count=9, http_status_counts={'401':1,'429':1,'503':1,'200':6},
        transport_error_count=0, credential_cleanup_failed=False, unique_events=3, native_seconds=120,
        pending_queue_actions=6, canonical_ack=False, source_cursor_changed=False,
        statistics_accessed=False, wifi_changed=False, physical_execution_attested=False,
        credential_revoked=True, control_failed=False, production_registered=False, cloud_delivery_proven=False)
    if set(phone) != set(phone_required) | {'canonical_paths'}:
        raise ValueError('Unexpected phone observation')
    for key, value in phone_required.items():
        if type(phone[key]) is not type(value) or encoded(phone[key]) != encoded(value):
            raise ValueError('Canonical owner observation mismatch')
    expected_paths = {shard['path'] for shard in fixture['expected_shards']}
    if not isinstance(phone['canonical_paths'], list) or set(phone['canonical_paths']) != expected_paths or len(phone['canonical_paths']) != 3:
        raise ValueError('Canonical path observation mismatch')
    actual_paths, pending = set(), [plain_root(android / 'vault')]
    while pending:
        parent = pending.pop()
        for path in parent.iterdir():
            if path.is_symlink() or path.is_junction():
                raise ValueError('Linked exported vault refused')
            if path.is_dir():
                pending.append(plain_root(path))
            elif path.is_file():
                actual_paths.add(path.relative_to(android / 'vault').as_posix())
            else:
                raise ValueError('Unexpected exported vault entry')
    if actual_paths != expected_paths:
        raise ValueError('Exported canonical inventory mismatch')
    for shard in fixture['expected_shards']:
        value = read(android / 'vault' / shard['path'], 8192)
        if value != base64.b64decode(shard['bytes_base64'], validate=True):
            raise ValueError('Actual canonical bytes mismatch')
    # All evidence can be synthesized on a host: correlation is not attestation.
    return dict(probe_revision=REVISION, proof='correlated_wire_and_owner_observations',
                run_id=manifest['run_id'], source_commit=manifest['source_commit'], observations_match=True,
                fixture_sha256=manifest['files']['synthetic-fixture.json'], canonical_paths=sorted(expected_paths),
                unique_events=3, native_seconds=120, credential_revocation_observed=True,
                canonical_ack=False, physical_execution_attested=False, cloud_delivery_proven=False,
                source_cursor_changed=False, production_changed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare_parser = commands.add_parser('prepare')
    prepare_parser.add_argument('--session', type=pathlib.Path, required=True)
    prepare_parser.add_argument('--source-commit', required=True)
    prepare_parser.add_argument('--output', type=pathlib.Path, required=True)
    for name in ('install', 'collect'):
        command = commands.add_parser(name)
        command.add_argument('--bundle', type=pathlib.Path, required=True)
        command.add_argument('--kindle-root', type=pathlib.Path, required=True)
        command.add_argument('--observation', type=pathlib.Path, required=True)
        if name == 'collect':
            command.add_argument('--android-export', type=pathlib.Path, required=True)
            command.add_argument('--output', type=pathlib.Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            prepare(args.session, args.output, args.source_commit)
        else:
            destination = args.observation if args.command == 'install' else args.output
            plain_root(destination.absolute().parent)
            if destination.exists() or destination.is_symlink() or destination.is_junction():
                raise ValueError('Fresh observation output required')
            report = install(args.bundle, args.kindle_root) if args.command == 'install' else collect(
                args.bundle, args.kindle_root, args.observation, args.android_export)
            with destination.open('xb') as stream:
                stream.write(encoded(report))
        print('TLS diagnostic operation completed; physical/canonical ACK acceptance remains separate')
    except Exception:
        raise SystemExit('FAIL: TLS diagnostic operation; private, existing and partial files preserved') from None


if __name__ == '__main__':
    main()
