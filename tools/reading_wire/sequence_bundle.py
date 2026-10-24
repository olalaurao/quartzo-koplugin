"""Exact-source disposable TLS bundle. Never provision a phone or attest hardware."""
import argparse
import base64
import datetime
import ipaddress
import json
import pathlib
import re
import shutil
import ssl
import sqlite3
import subprocess
import tempfile
import time

from probe_bundle import (BASELINE, ROOT, encoded, hexadecimal, native_snapshot,
                          parse, plain_root, read, sha, ProbeDefinition, NATIVE)

NAME = 'quartzo-wire-tls-probe'
REVISION = 'canonical-paired-sequence-v1'
SOURCE_MAP = {
    'codec.lua': 'quartzo.koplugin/quartzo/codec.lua',
    'koreader_deps.lua': 'quartzo.koplugin/quartzo/koreader_deps.lua',
    'exchange.lua': 'quartzo.koplugin/quartzo/paired_exchange.lua',
    'sequence.lua': 'tools/reading_wire/paired_sequence.lua',
    'outbox.lua': 'quartzo.koplugin/quartzo/outbox.lua',
    'process.lua': 'tools/plugin/outbox_probe.lua',
    'client.lua': 'tools/transport_probe/client.lua',
    'kindle.lua': 'tools/reading_wire/sequence_kindle.lua',
    'run.sh': 'tools/transport_probe/run.sh',
    'menu.json': 'tools/reading_wire/sequence_menu.json',
    'config.xml': 'tools/reading_wire/sequence_config.xml',
}
INPUTS = {'private-pairing.json', 'server.pem', 'synthetic-fixture.json'}
RUNTIME = {'run.lock', 'launcher-status.txt', 'device-observation.json', 'device-observation.json.tmp'}
SEED = 'outbox-seed.sqlite3'
OUTBOX_NATIVE = {**NATIVE, 'sqlite_wrapper':'common/lua-ljsqlite3/init.lua',
    'posix':'ffi/posix_h.lua', 'sqlite':'libs/libsqlite3.so.0',
    'filesystem':'libs/libkoreader-lfs.so', 'luajit':'luajit'}
OUTBOX = ProbeDefinition(NAME,SOURCE_MAP,OUTBOX_NATIVE)
OUTBOX_RUNTIME = {'outbox-state','seed-observation.json','seed-observation.json.tmp'}


def native_context(binding):
    return (isinstance(binding,dict)
        and isinstance(binding.get('device_id'),str)
        and isinstance(binding.get('source_epoch'),str)
        and re.fullmatch(r'qrd_[a-f0-9]{32}',binding['device_id']) is not None
        and re.fullmatch(r'probe_[a-f0-9]{32}',binding['source_epoch']) is not None)


def inspect_outbox_bytes(data,binding,pending,review,expected_schema=None):
    # SQL opens ONLY this new private copy, never the supplied/mounted source.
    if not 0 < len(data) <= 65536 or not native_context(binding):
        raise ValueError('Invalid synthetic outbox seed')
    with tempfile.TemporaryDirectory(prefix='quartzo-outbox-private-inspection-') as temporary:
        path=pathlib.Path(temporary)/'state.sqlite3'
        with path.open('xb') as stream:stream.write(data)
        conn=sqlite3.connect(path.as_uri()+'?mode=ro&immutable=1',uri=True)
        try:
            if (conn.execute('PRAGMA user_version').fetchone()!=(1,)
                    or conn.execute('PRAGMA quick_check').fetchall()!=[('ok',)]):
                raise ValueError('Unhealthy private synthetic outbox copy')
            objects=conn.execute('SELECT name,type FROM sqlite_master LIMIT 6').fetchall()
            expected={('identity','table'),('pending','table'),('review','table'),
                ('sqlite_autoindex_pending_1','index'),('sqlite_autoindex_review_1','index')}
            if len(objects)!=5 or set(objects)!=expected:
                raise ValueError('Unsupported private outbox objects')
            declarations=conn.execute('SELECT name,type,sql FROM sqlite_master ORDER BY name LIMIT 6').fetchall()
            if expected_schema is not None and declarations!=expected_schema:
                raise ValueError('Synthetic outbox declarations changed')
            if conn.execute('SELECT id,device_id,source_epoch FROM identity LIMIT 2').fetchall()!=[
                    (1,binding['device_id'],binding['source_epoch'])]:
                raise ValueError('Synthetic outbox context mismatch')
            for name,count in (('pending',pending),('review',review)):
                if conn.execute('SELECT COUNT(*) FROM (SELECT 1 FROM '+name+' LIMIT 1001)').fetchone()!=(count,):
                    raise ValueError('Synthetic outbox count mismatch')
            expected_review=([(1791946202,'17','0','10','120','integer,integer,integer,integer,integer')]
                if review==1 else [])
            if conn.execute('SELECT started_at,book_id,page,duration,pages,types FROM review LIMIT 2').fetchall()!=expected_review:
                raise ValueError('Synthetic retained review changed')
        finally:
            conn.close()
    return declarations


def compact(value):
    # Independent verification only; canonical events are still produced by
    # Dart and persisted by the app, never serialized/written by this collector.
    return json.dumps(value,ensure_ascii=False,separators=(',',':')).encode('utf-8')


def native_binding(line):
    event=parse(line.encode('utf-8'))
    started=datetime.datetime.fromisoformat(event['started_at_utc'].replace('Z','+00:00'))
    identity='qre_'+sha(compact(['quartzo-reading-event-v1',event['device_id'],event['source_epoch'],
        event['book_row_id'],event['page'],int(started.timestamp())]))
    if compact(event) != line.encode('utf-8') or event['event_id'] != identity:
        raise ValueError('Synthetic native identity mismatch')
    native=dict(event)
    native.pop('observed_at_utc')
    return event,sha(compact(native))


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
    pairing = parse(values['private-pairing.json'])
    if (len(values['private-pairing.json']) > 8192 or set(pairing) != {'pairing_version','receiver_role',
            'endpoint','certificate_pem','peer_certificate_sha256','binding','token','not_before_utc','expires_at_utc'}
            or type(pairing['pairing_version']) is not int or pairing['pairing_version'] != 1
            or pairing['receiver_role'] != 'canonical_reading_activity_v1'
            or not isinstance(pairing['token'],str) or re.fullmatch(r'[A-Za-z0-9_-]{43}',pairing['token']) is None
            or not isinstance(pairing['endpoint'],str)):
        raise ValueError('Invalid app-issued private pairing')
    match = re.fullmatch(r'https://([0-9.]+):([0-9]+)', pairing['endpoint'])
    if not match or not 1024 <= int(match[2]) <= 65535:
        raise ValueError('Explicit private HTTPS endpoint required')
    address = ipaddress.IPv4Address(match[1])
    if not any(address in ipaddress.IPv4Network(network) for network in
               ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16', '127.0.0.1/32')):
        raise ValueError('Unsupported diagnostic network')
    first,last = [datetime.datetime.fromisoformat(pairing[key].replace('Z','+00:00'))
                  for key in ('not_before_utc','expires_at_utc')]
    start,expiry=first.timestamp(),last.timestamp()
    if first.utcoffset() != datetime.timedelta(0) or last.utcoffset() != datetime.timedelta(0) or not 0 < expiry-start <= 1800:
        raise ValueError('Invalid diagnostic lifetime')
    if live and not start <= time.time() < expiry-30:
        raise ValueError('Diagnostic session not currently usable')
    if (not isinstance(pairing['certificate_pem'],str) or len(values['server.pem']) > 4096
            or values['server.pem'] != pairing['certificate_pem'].encode('ascii')
            or b'PRIVATE KEY' in values['server.pem']
            or sha(ssl.PEM_cert_to_DER_cert(pairing['certificate_pem'])) != pairing['peer_certificate_sha256']):
        raise ValueError('Exact app-issued public certificate required')
    fixture = parse(values['synthetic-fixture.json'])
    binding=pairing['binding']
    if (not isinstance(binding,dict) or set(binding) != {'binding_id','vault_scope','device_id','source_epoch'}
            or not all(isinstance(value,str) for value in binding.values())
            or re.fullmatch(r'qrp_[a-f0-9]{32}',binding['binding_id']) is None
            or not hexadecimal(binding['vault_scope'],64) or not hexadecimal(fixture.get('run_id'),32)):
        raise ValueError('Invalid finite app binding')
    scope = 'synthetic-wire-' + fixture['run_id']
    if (type(fixture.get('schema_version')) is not int or fixture.get('schema_version') != 1
            or fixture.get('fixture_revision') != 'canonical-wire-synthetic-v1'
            or fixture.get('canonical_ack') is not False
            or fixture.get('physical_execution_attested') is not False
            or fixture.get('binding') != binding
            or not (native_context(binding) or (binding['device_id']=='synthetic-wire-device'
                and binding['source_epoch']==scope))
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
    return values, dict(run_id=fixture['run_id'],not_before_utc=pairing['not_before_utc'],
        expires_at_utc=pairing['expires_at_utc']), fixture


def prepare(session_directory, output, revision, *, outbox_seed=None):
    source, output = private_directory(session_directory), private_directory(output, fresh=True)
    values, session, fixture = inputs(source, live=True)
    native=native_context(fixture['binding'])
    if native != (outbox_seed is not None):
        raise ValueError('Native context requires its explicit empty outbox seed')
    if native:
        values[SEED]=read(outbox_seed,65536)
        inspect_outbox_bytes(values[SEED],fixture['binding'],0,0)
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
    actual = {entry.name for entry in directory.iterdir()}
    if not (set(SOURCE_MAP)|INPUTS|{'bundle-manifest.json'})<=actual:
        raise ValueError('Incomplete TLS bundle')
    values, session, fixture = inputs(directory)
    native=native_context(fixture['binding'])
    if native:
        values[SEED]=read(directory/SEED,65536)
        inspect_outbox_bytes(values[SEED],fixture['binding'],0,0)
    expected = set(SOURCE_MAP) | INPUTS | {'bundle-manifest.json'} | ({SEED} if native else set())
    runtime=RUNTIME | (OUTBOX_RUNTIME if native else set())
    if not expected <= actual or actual - expected - (runtime if allow_runtime else set()):
        raise ValueError('Unexpected TLS bundle entry')
    for name in actual:
        path = directory / name
        if path.is_symlink() or path.is_junction():
            raise ValueError('Linked TLS bundle entry refused')
        if name == 'run.lock':
            if not path.is_dir() or any(path.iterdir()):
                raise ValueError('Invalid single-use lock')
        elif name=='outbox-state' and native and allow_runtime:
            if not path.is_dir():raise ValueError('Invalid diagnostic outbox root')
            for entry in path.iterdir():
                if (entry.name not in ('quartzo_sync_state.sqlite3','quartzo_sync_state.sqlite3-journal')
                        or entry.is_symlink() or entry.is_junction() or not entry.is_file()
                        or entry.stat().st_size>262144):
                    raise ValueError('Unexpected diagnostic outbox artifact; preserved')
        elif not path.is_file():
            raise ValueError('Regular TLS bundle file required')
    manifest_bytes = read(directory / 'bundle-manifest.json', 8192)
    manifest = parse(manifest_bytes)
    if (set(manifest) != {'probe_revision', 'run_id', 'koreader_baseline', 'source_commit', 'files'}
            or manifest['probe_revision'] != REVISION or manifest['koreader_baseline'] != BASELINE
            or not isinstance(manifest['files'], dict)
            or set(manifest['files']) != set(SOURCE_MAP) | INPUTS | ({SEED} if native else set())):
        raise ValueError('Unsupported TLS bundle manifest')
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
    _,_,fixture=inputs(bundle, live=True)
    context_native=native_context(fixture['binding'])
    native = native_snapshot(root,OUTBOX) if context_native else native_snapshot(root)
    extensions = plain_root(root / 'extensions')
    if extensions.parent != root or shutil.disk_usage(root).free < 4*1024*1024:
        raise ValueError('Mounted target unavailable')
    target = extensions / NAME
    if target.exists() or target.is_symlink() or target.is_junction():
        raise ValueError('Existing diagnostic preserved')
    target.mkdir(exist_ok=False)
    for name in set(SOURCE_MAP) | INPUTS | {'bundle-manifest.json'} | ({SEED} if context_native else set()):
        with (target / name).open('xb') as stream:
            stream.write(read(bundle / name, 65536))
    after_native=native_snapshot(root,OUTBOX) if context_native else native_snapshot(root)
    if verify_bundle(target) != (manifest, digest) or after_native != native:
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
    _,session,fixture=inputs(target)
    context_native=native_context(fixture['binding'])
    snapshot=native_snapshot(root,OUTBOX) if context_native else native_snapshot(root)
    expected = dict(probe_revision=REVISION, run_id=manifest['run_id'], source_commit=manifest['source_commit'],
                    manifest_digest=digest, native_source_sha256=snapshot, canonical_ack=False,
                    physical_execution_attested=False, production_changed=False)
    if encoded(parse(read(observation, 4096))) != encoded(expected):
        raise ValueError('Installation observation mismatch')
    if read(target / 'launcher-status.txt', 64).strip() != b'completed' or (target / 'device-observation.json.tmp').exists():
        raise ValueError('Launcher/report incomplete')
    if not (target / 'run.lock').is_dir():
        raise ValueError('Single-use launch not observed')
    device = parse(read(target / 'device-observation.json', 12288))
    required = dict(probe_revision=REVISION, phase='paired_receipts_checked', source_data='synthetic',
        run_id=manifest['run_id'], source_commit=manifest['source_commit'], manifest_digest=digest,
        canonical_ack=False, canonical_persistence_proven=False, physical_execution_attested=False,
        source_cursor_changed=False, statistics_accessed=False, wifi_changed=False,
        attempts=6, checked_receipts=5, deliberately_discarded_responses=1,
        lua_version='Lua 5.1', jit_arch='arm', koreader_version=BASELINE,
        native_source_sha256=expected['native_source_sha256'])
    selected=[batch['event_lines'][-1] for batch in fixture['batches']]
    selected.sort(key=lambda line:native_binding(line)[0]['event_id'])
    selected_digests=[sha(line.encode('utf-8')) for line in selected]
    dynamic={'steps','jit_version','json_version','luasec_version'}
    if context_native:
        required.update(outbox_initial_pending=3,outbox_review_retained=1,outbox_pruned=3,
            outbox_final_pending=0,outbox_identity_preserved=True,outbox_raw_receipt_rejections=5,
            outbox_selected_sha256=selected_digests,distinct_seed_and_replay_processes=True)
        dynamic|={'source_process_id','seed_process_id'}
        for key in ('source_process_id','seed_process_id'):
            if type(device.get(key)) is not int or not 1 < device[key] < 2**31:
                raise ValueError('Invalid diagnostic process observation')
        if device['source_process_id']==device['seed_process_id']:
            raise ValueError('Seed and replay must be distinct processes')
    if set(device) != set(required) | dynamic:
        raise ValueError('Unexpected device observation')
    for key, value in required.items():
        if type(device[key]) is not type(value) or device[key] != value:
            raise ValueError('Device sequence observations mismatch')
    for key, pattern in (('jit_version', r'LuaJIT 2\.1[ A-Za-z0-9.()_-]{0,96}'),
                         ('json_version', r'dkjson [0-9]+\.[0-9]+'),
                         ('luasec_version', r'[A-Za-z0-9 .()_-]{1,64}')):
        if not isinstance(device[key], str) or re.fullmatch(pattern, device[key]) is None:
            raise ValueError('Unsupported native runtime observation')
    steps=['seed_1','seed_2','mixed_1','mixed_2','within_request_conflict_1','within_request_conflict_2']
    if not isinstance(device['steps'], list) or len(device['steps']) != 6:
        raise ValueError('Incomplete finite sequence')
    first,last=[datetime.datetime.fromisoformat(session[key].replace('Z','+00:00'))
                for key in ('not_before_utc','expires_at_utc')]
    binding=fixture['binding']
    batches = []
    for index, (step, name) in enumerate(zip(device['steps'], steps), 1):
        nonce = 'qrtr_' + manifest['run_id'][:16] + format(index, '016x')
        step_keys={'step','request_id','batch_id','request_sha256','issued_at_utc','expires_at_utc','receipt_event'}
        if context_native:step_keys.add('outbox_pending')
        if (set(step) != step_keys
                or step['step'] != name or step['request_id'] != nonce):
            raise ValueError('Sequence request binding mismatch')
        if context_native and (type(step['outbox_pending']) is not int
                or step['outbox_pending']!=[3,2,1,1,0,0][index-1]):
            raise ValueError('Unexpected paired outbox pruning progression')
        batch_index=(index-1)//2
        lines=fixture['batches'][batch_index]['event_lines']
        batch='qrtb_'+sha(compact(['quartzo-reading-transport-batch-v1',binding['binding_id'],
            binding['vault_scope'],binding['device_id'],binding['source_epoch'],lines]))
        request=dict(protocol_version=1,**{key:binding[key] for key in ('binding_id','vault_scope','device_id','source_epoch')},
            request_id=nonce,issued_at_utc=step['issued_at_utc'],expires_at_utc=step['expires_at_utc'],
            batch_id=batch,event_lines=lines)
        issued,expires=[datetime.datetime.fromisoformat(step[key].replace('Z','+00:00'))
                        for key in ('issued_at_utc','expires_at_utc')]
        if (not first <= issued < last or (expires-issued).total_seconds() != 30
                or step['batch_id'] != batch or step['request_sha256'] != sha(compact(request))):
            raise ValueError('Independent request bytes or window mismatch')
        if index == 1:
            if step['receipt_event'] is not None:
                raise ValueError('Discarded receipt was acknowledged')
        else:
            event,native_digest=native_binding(lines[-1])
            receipt=dict(index=len(lines)-1,line_digest=sha(lines[-1].encode('utf-8')),event_id=event['event_id'],
                native_digest=native_digest,canonical_commit='qrc_'+fixture['expected_shards'][batch_index]['sha256'])
            if encoded(step['receipt_event']) != encoded(receipt):
                raise ValueError('Independent acknowledged event binding mismatch')
        batches.append(step['batch_id'])
    if len(set(batches)) != 3 or any(batches[i] != batches[i+1] for i in (0,2,4)):
        raise ValueError('Immutable retry batch mismatch')
    if context_native:
        if (target/'seed-observation.json.tmp').exists():
            raise ValueError('Incomplete seed observation; preserved')
        seed=parse(read(target/'seed-observation.json',12288))
        seed_required=dict(probe_revision=REVISION,phase='outbox_seed_receipt_discarded',
            source_data='synthetic',canonical_ack=False,canonical_persistence_proven=False,
            physical_execution_attested=False,source_cursor_changed=False,statistics_accessed=False,
            wifi_changed=False,attempts=1,checked_receipts=1,deliberately_discarded_responses=1,
            run_id=manifest['run_id'],outbox_initial_pending=3,outbox_review_retained=1,outbox_pruned=0,
            outbox_selected_sha256=selected_digests,outbox_raw_receipt_rejections=0,
            outbox_final_pending=3,outbox_identity_preserved=True,source_process_id=device['seed_process_id'])
        if set(seed)!=set(seed_required)|{'steps'}:
            raise ValueError('Unexpected seed observation')
        for key,value in seed_required.items():
            if type(seed[key]) is not type(value) or seed[key]!=value:
                raise ValueError('Seed observation mismatch')
        if not isinstance(seed['steps'],list) or len(seed['steps'])!=1:
            raise ValueError('Incomplete seed request')
        step=seed['steps'][0]
        nonce='qrtr_'+manifest['run_id'][:16]+format(7,'016x')
        if (set(step)!={'step','request_id','batch_id','request_sha256','issued_at_utc','expires_at_utc','receipt_event'}
                or step['step']!='seed_discard_before_ack' or step['request_id']!=nonce
                or step['receipt_event'] is not None or step['batch_id']!=batches[0]):
            raise ValueError('Seed request binding mismatch')
        request=dict(protocol_version=1,**{key:binding[key] for key in ('binding_id','vault_scope','device_id','source_epoch')},
            request_id=nonce,issued_at_utc=step['issued_at_utc'],expires_at_utc=step['expires_at_utc'],
            batch_id=batches[0],event_lines=fixture['batches'][0]['event_lines'])
        issued,expires=[datetime.datetime.fromisoformat(step[key].replace('Z','+00:00'))
            for key in ('issued_at_utc','expires_at_utc')]
        replay_issued=datetime.datetime.fromisoformat(device['steps'][0]['issued_at_utc'].replace('Z','+00:00'))
        if (not first<=issued<=replay_issued<last or (expires-issued).total_seconds()!=30
                or step['request_sha256']!=sha(compact(request))):
            raise ValueError('Independent seed request/window mismatch')
        state=plain_root(target/'outbox-state')
        if {entry.name for entry in state.iterdir()}!={'quartzo_sync_state.sqlite3'}:
            raise ValueError('Incomplete or unexpected outbox artifacts; preserved')
        schema=inspect_outbox_bytes(read(target/SEED,65536),binding,0,0)
        inspect_outbox_bytes(read(state/'quartzo_sync_state.sqlite3',65536),binding,0,1,schema)
    phone = parse(read(android / 'completed.json', 16384))
    phone_required = dict(probe_revision='canonical-paired-wire-v1', phase='completed', run_id=manifest['run_id'],
        source_data='synthetic',synthetic_account=True,credential_cleanup_failed=False,unique_events=3,native_seconds=120,
        canonical_ack=False,source_cursor_changed=False,
        statistics_accessed=False, wifi_changed=False, physical_execution_attested=False,
        credential_revoked=True, control_failed=False, production_registered=False, cloud_delivery_proven=False)
    if (set(phone) != set(phone_required) | {'canonical_paths','pending_queue_actions'}
            or type(phone['pending_queue_actions']) is not int
            or not 3 <= phone['pending_queue_actions'] <= (7 if context_native else 6)):
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
    events={}
    for shard in fixture['expected_shards']:
        value = read(android / 'vault' / shard['path'], 8192)
        if value != base64.b64decode(shard['bytes_base64'], validate=True):
            raise ValueError('Actual canonical bytes mismatch')
        for line in value.decode('utf-8').splitlines():
            event,native_digest=native_binding(line)
            previous=events.get(event['event_id'])
            if previous is not None and previous[1] != native_digest:
                raise ValueError('Canonical native payload conflict')
            events[event['event_id']]=(event,native_digest)
    if len(events) != 3 or sum(event['duration_seconds'] for event,_ in events.values()) != 120:
        raise ValueError('Independent native event/time counts mismatch')
    # All evidence can be synthesized on a host: correlation is not attestation.
    result=dict(probe_revision=REVISION, proof='correlated_paired_receipts_and_owner_observations',
                run_id=manifest['run_id'], source_commit=manifest['source_commit'], observations_match=True,
                fixture_sha256=manifest['files']['synthetic-fixture.json'], canonical_paths=sorted(expected_paths),
                unique_events=3,native_seconds=120,checked_receipts=5,credential_revocation_observed=True,
                canonical_ack=False, physical_execution_attested=False, cloud_delivery_proven=False,
                source_cursor_changed=False, production_changed=False)
    if context_native:
        result.update(native_outbox_identity_and_selected_bytes_correlated=True,
            distinct_source_process_observations=True,seed_checked_receipts=1,
            outbox_pending=0,outbox_review_retained=1,outbox_raw_receipt_rejections=5,
            paired_outbox_observations_match=True,source_generation_verified=False,gate4_passed=False)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare_parser = commands.add_parser('prepare')
    prepare_parser.add_argument('--session', type=pathlib.Path, required=True)
    prepare_parser.add_argument('--source-commit', required=True)
    prepare_parser.add_argument('--output', type=pathlib.Path, required=True)
    prepare_parser.add_argument('--outbox-seed', type=pathlib.Path)
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
            prepare(args.session, args.output, args.source_commit,outbox_seed=args.outbox_seed)
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
