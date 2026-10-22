"""Owned SQLite outbox transactions. No device/canonical-delivery claim."""
import json
import hashlib
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import unittest

from lupa.luajit21 import LuaRuntime as LuaJITRuntime
import test_collector as collector
from test_collector import OBSERVED, ROOT
import test_statistics as statistics


class OutboxTest(unittest.TestCase):
    lua_type = statistics.LuaRuntime
    allow_owned_writes = True
    make_sdk = statistics.StatisticsTest.make_sdk
    trace = statistics.StatisticsTest.trace
    mutate = statistics.StatisticsTest.mutate

    def setUp(self):
        collector.CollectorTest.setUp(self)
        self.outbox = self.lua.execute((ROOT / "quartzo.koplugin/quartzo/outbox.lua").read_text())
        wrap = self.lua.eval("function(f) return function(...) return f(...) end end")
        self.runtime = self.lua.table(sqlite=self.sdk, codec=self.codec,
                                      entropy=self.lua.eval("function() return string.rep('A',16) end"),
                                      attributes=wrap(lambda name: self.lua.table(mode="file") if Path(name).is_file() else None))
        self.root = Path(self.temp.name)
        self.owned = self.root / "quartzo_sync_state.sqlite3"
        self.queue = self.outbox.create(str(self.root), "db_epoch_fixture", self.runtime)
        self.assertNotIsInstance(self.queue, tuple)

    def batch(self, **options):
        fields = dict(self.queue.context().items())
        fields.update(observed_at_utc=OBSERVED)
        fields.update(options)
        result = self.collector.collect(str(self.path), self.lua.table_from(fields), self.codec, self.sdk)
        self.assertNotIsInstance(result, tuple)
        return result

    def seed(self):
        self.mutate("""INSERT INTO book(id,title,md5) VALUES(1,'private title','0123456789abcdef0123456789abcdef');
        INSERT INTO page_stat_data VALUES(1,1,100,20,10),(1,2,101,30,10),(1,0,102,20,10);""")

    def reopen(self):
        queue = self.outbox.open(str(self.root), self.runtime)
        self.assertNotIsInstance(queue, tuple)
        return queue

    def test_identity_pending_bytes_and_review_survive_reopen(self):
        self.seed()
        context = dict(self.queue.context().items())
        before = self.path.read_bytes()
        self.assertEqual(context["device_id"], "qrd_" + "41"*16)
        batch = self.batch()
        result = self.queue.stage(batch)
        self.assertEqual((result.pending,result.review,result.canonical_ack), (2,1,False))
        later = self.reopen()
        self.assertEqual(dict(later.context().items()), context)
        self.assertEqual(set(later.pending().event_lines.values()), set(batch.event_lines.values()))
        self.assertEqual(later.status().review, 1)
        self.assertEqual(before, self.path.read_bytes())
        self.assertTrue(all(mode in ("ro","rw","rwc") for op,mode in self.calls if op=="open"))

    def test_duplicate_stage_preserves_original_observation_and_does_not_grow_review(self):
        self.seed()
        first = self.batch()
        self.queue.stage(first)
        later = self.batch(observed_at_utc="2026-10-17T12:00:00.000Z")
        result = self.queue.stage(later)
        self.assertEqual((result.pending,result.review), (2,1))
        self.assertEqual(set(self.queue.pending().event_lines.values()), set(first.event_lines.values()))

    def test_native_payload_conflict_rolls_back_new_neighbors_and_preserves_original(self):
        self.seed()
        original = self.batch()
        self.queue.stage(original)
        self.mutate("UPDATE page_stat_data SET duration=21 WHERE page=1; INSERT INTO page_stat_data VALUES(1,3,103,20,10)")
        self.assertEqual(self.queue.stage(self.batch()), (None,"outbox_native_conflict"))
        self.assertEqual(set(self.reopen().pending().event_lines.values()), set(original.event_lines.values()))

    def test_transaction_failure_rolls_back_pending_and_review_and_reopens_cleanly(self):
        self.seed()
        self.calls.clear()
        armed = [True]

        def fail(operation, value):
            if armed[0] and operation=="exec" and value=="COMMIT":
                armed[0]=False
                raise RuntimeError("private simulated disk-full path")

        self.query_hook=fail
        self.assertEqual(self.queue.stage(self.batch()), (None,"outbox_unavailable"))
        self.query_hook=None
        result=self.reopen().status()
        self.assertEqual((result.pending,result.review), (0,0))
        self.assertEqual(self.queue.stage(self.batch()).pending, 2)

    def test_missing_corrupt_future_state_never_reenrolls_or_overwrites(self):
        initial=self.owned.read_bytes()
        self.assertEqual(self.outbox.create(str(self.root),"other_epoch",self.runtime), (None,"outbox_exists"))
        self.assertEqual(initial,self.owned.read_bytes())
        with statistics.closing(sqlite3.connect(self.owned)) as conn,conn:
            conn.execute("PRAGMA user_version=99")
        future=self.owned.read_bytes()
        self.assertEqual(self.outbox.open(str(self.root),self.runtime), (None,"unsupported_outbox_schema"))
        self.assertEqual(future,self.owned.read_bytes())
        self.owned.write_bytes(b"synthetic corrupt owned fixture")
        corrupt=self.owned.read_bytes()
        self.assertEqual(self.outbox.open(str(self.root),self.runtime), (None,"outbox_unavailable"))
        self.assertEqual(corrupt,self.owned.read_bytes())
        self.owned.unlink()  # Owned test file, never source Statistics.
        self.assertEqual(self.outbox.open(str(self.root),self.runtime), (None,"outbox_missing"))
        self.assertFalse(self.owned.exists())

    def test_create_race_does_not_reconfigure_an_existing_unknown_database(self):
        with statistics.closing(sqlite3.connect(self.owned)) as conn,conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA user_version=99")
        before=self.owned.read_bytes()
        self.runtime.attributes=self.lua.eval("function() return nil end")  # Stale initial observation.
        self.assertEqual(self.outbox.create(str(self.root),"new_epoch",self.runtime),(None,"outbox_exists"))
        self.assertEqual(before,self.owned.read_bytes())
        with statistics.closing(sqlite3.connect(self.owned)) as conn:
            self.assertEqual(conn.execute("PRAGMA journal_mode").fetchone()[0],"wal")

    def test_selected_bytes_survive_source_history_deletion(self):
        self.seed()
        self.queue.stage(self.batch())
        before=set(self.queue.pending().event_lines.values())
        self.mutate("DELETE FROM page_stat_data; DELETE FROM book")
        self.assertEqual(set(self.reopen().pending().event_lines.values()),before)
        self.assertEqual(self.queue.status().review,1)

    def snapshot(self):
        snapshot=self.queue.backup()
        self.assertNotIsInstance(snapshot,tuple)
        backup=self.root/snapshot.backup_leaf
        self.assertTrue(backup.is_file())
        return snapshot,backup

    def test_backup_restore_preserves_identity_selected_bytes_and_review(self):
        self.seed()
        self.queue.stage(self.batch())
        original=set(self.queue.pending().event_lines.values())
        context=dict(self.queue.context().items())
        source=self.path.read_bytes()
        state=self.owned.read_bytes()
        snapshot,backup=self.snapshot()
        self.assertEqual(state,self.owned.read_bytes())
        self.assertEqual(source,self.path.read_bytes())
        self.assertEqual((snapshot.pending,snapshot.review,snapshot.canonical_ack),(2,1,False))
        preview=self.outbox.inspect_backup(str(self.root),snapshot.backup_leaf,self.runtime)
        self.assertEqual((preview.pending,preview.review),(2,1))
        saved=backup.read_bytes()
        self.mutate("DELETE FROM page_stat_data; DELETE FROM book")
        self.owned.unlink()  # Owned synthetic state-loss fixture only.
        self.runtime.entropy=self.lua.eval("function() error('restore must not generate identity') end")
        restored=self.outbox.restore(str(self.root),snapshot.backup_leaf,self.runtime)
        self.assertNotIsInstance(restored,tuple)
        self.assertEqual(dict(restored.context().items()),context)
        self.assertEqual(set(restored.pending().event_lines.values()),original)
        self.assertEqual(restored.status().review,1)
        self.assertIsNone(restored.status().source_watermark)
        self.assertEqual(saved,backup.read_bytes())

    def test_restore_preserves_an_existing_damaged_primary_and_immutable_backup(self):
        self.seed()
        self.queue.stage(self.batch())
        snapshot,backup=self.snapshot()
        self.owned.write_bytes(b"owned damaged state remains available for review")
        before=self.owned.read_bytes()
        saved=backup.read_bytes()
        self.assertEqual(self.outbox.restore(str(self.root),snapshot.backup_leaf,self.runtime),(None,"outbox_exists"))
        self.assertEqual(before,self.owned.read_bytes())
        self.assertEqual(saved,backup.read_bytes())

    def test_backup_collision_never_replaces_the_older_snapshot(self):
        self.seed()
        self.queue.stage(self.batch())
        snapshot,backup=self.snapshot()
        saved=backup.read_bytes()
        self.mutate("INSERT INTO page_stat_data VALUES(1,5,105,20,10)")
        self.queue.stage(self.batch())
        self.assertEqual(self.queue.backup(),(None,"outbox_exists"))
        self.assertEqual(saved,backup.read_bytes())
        self.runtime.entropy=self.lua.eval("function() return string.rep('B',16) end")
        newer,new_path=self.snapshot()
        self.assertNotEqual(newer.backup_leaf,snapshot.backup_leaf)
        self.assertEqual((newer.pending,newer.review),(3,1))
        self.assertEqual(saved,backup.read_bytes())
        self.assertEqual(self.outbox.inspect_backup(str(self.root),snapshot.backup_leaf,self.runtime).pending,2)

    def test_invalid_or_missing_backup_path_cannot_create_state(self):
        self.owned.unlink()
        for leaf in ("../statistics.sqlite3","file:/statistics.sqlite3",
                     "quartzo_sync_recovery_"+"a"*31+".sqlite3",
                     "quartzo_sync_recovery_"+"A"*32+".sqlite3"):
            self.assertEqual(self.outbox.restore(str(self.root),leaf,self.runtime),(None,"invalid_outbox_state"))
        missing="quartzo_sync_recovery_"+"a"*32+".sqlite3"
        self.assertEqual(self.outbox.restore(str(self.root),missing,self.runtime),(None,"outbox_backup_missing"))
        self.assertFalse(self.owned.exists())

    def test_future_backup_and_unknown_columns_are_preserved_without_target_creation(self):
        self.seed()
        self.queue.stage(self.batch())
        snapshot,backup=self.snapshot()
        self.owned.unlink()
        with statistics.closing(sqlite3.connect(backup)) as conn,conn:
            conn.execute("PRAGMA user_version=99")
        before=backup.read_bytes()
        self.assertEqual(self.outbox.restore(str(self.root),snapshot.backup_leaf,self.runtime),(None,"unsupported_outbox_schema"))
        self.assertEqual(before,backup.read_bytes())
        self.assertFalse(self.owned.exists())
        with statistics.closing(sqlite3.connect(backup)) as conn,conn:
            conn.execute("PRAGMA user_version=1")
            conn.execute("ALTER TABLE pending ADD COLUMN unknown TEXT")
        before=backup.read_bytes()
        self.assertEqual(self.outbox.restore(str(self.root),snapshot.backup_leaf,self.runtime),(None,"invalid_outbox_state"))
        self.assertEqual(before,backup.read_bytes())
        self.assertFalse(self.owned.exists())

    def test_corrupt_or_foreign_pending_in_backup_is_not_restored(self):
        self.seed()
        self.queue.stage(self.batch())
        snapshot,backup=self.snapshot()
        self.owned.unlink()
        with statistics.closing(sqlite3.connect(backup)) as conn,conn:
            line=conn.execute("SELECT line FROM pending ORDER BY event_id LIMIT 1").fetchone()[0]
            event=json.loads(line)
            event.pop("event_id")
            event["device_id"]="qrd_foreign"
            foreign=self.codec.encode_event(self.to_lua(event))
            info=self.codec.inspect_event(foreign)
            conn.execute("UPDATE pending SET event_id=?,line=?,native_digest=? WHERE line=?",
                         (info.event_id,foreign,info.native_digest,line))
        before=backup.read_bytes()
        self.assertEqual(self.outbox.restore(str(self.root),snapshot.backup_leaf,self.runtime),(None,"outbox_scope_mismatch"))
        self.assertEqual(before,backup.read_bytes())
        self.assertFalse(self.owned.exists())

    def test_backup_transaction_failure_preserves_original_and_partial_artifact(self):
        self.seed()
        self.queue.stage(self.batch())
        context=dict(self.queue.context().items())

        def fail(operation,value):
            if operation=="exec" and value=="COMMIT": raise RuntimeError("owned simulated snapshot interruption")

        self.query_hook=fail
        self.assertEqual(self.queue.backup(),(None,"outbox_unavailable"))
        self.query_hook=None
        self.assertEqual((self.reopen().status().pending,self.queue.status().review),(2,1))
        self.assertEqual(dict(self.queue.context().items()),context)
        artifacts=list(self.root.glob("quartzo_sync_recovery_*.sqlite3"))
        self.assertEqual(len(artifacts),1)
        preview=self.outbox.inspect_backup(str(self.root),artifacts[0].name,self.runtime)
        self.assertEqual(preview,(None,"unsupported_outbox_schema"))
        self.assertTrue(artifacts[0].is_file())

    def receipt_owner(self):
        # Trust boundary fixture for this store only: real pairing's separate
        # suite proves its opaque handles/delivery checks. No public list setter.
        owner = self.lua.execute('''local saved=setmetatable({}, {__mode='k'})
            local session={}
            return {session=session, mint=function(claims,request)
                local receipt={}; saved[receipt]={claims=claims,request=request}; return receipt
            end, acknowledged=function(handle,receipt,request)
                local value=saved[receipt]
                if handle~=session or not value or value.request~=request then return nil end
                return value.claims
            end}
        ''')
        self.lua.globals().package.loaded["quartzo/paired_exchange"]=owner
        return owner

    def test_raw_claims_wrong_session_request_or_line_never_prune(self):
        self.seed()
        self.queue.stage(self.batch())
        owner=self.receipt_owner()
        line=self.queue.pending().event_lines[1]
        info=self.codec.inspect_event(line)
        claims=self.lua.table_from([info])
        receipt=owner.mint(claims,"request-a")
        for session,claim,request in ((owner.session,claims,"request-a"),
                                      (self.lua.table(),receipt,"request-a"),
                                      (owner.session,receipt,"request-b")):
            self.assertEqual(self.queue.consume_receipt(session,claim,request),(None,"unverified_reading_receipt"))
            self.assertEqual(self.queue.status().pending,2)
        info.line_digest="0"*64
        self.assertEqual(self.queue.consume_receipt(owner.session,receipt,"request-a"),(None,"unverified_reading_receipt"))
        self.assertEqual(self.reopen().status().pending,2)

    def test_partial_verified_receipt_prunes_only_matching_bytes_and_retains_review(self):
        self.seed()
        self.queue.stage(self.batch())
        owner=self.receipt_owner()
        line=self.queue.pending().event_lines[1]
        info=self.codec.inspect_event(line)
        receipt=owner.mint(self.lua.table_from([info]),"request-a")
        result=self.queue.consume_receipt(owner.session,receipt,"request-a")
        self.assertEqual((result.removed,result.review_retained,result.canonical_ack),(1,1,False))
        self.assertIsNone(result.source_watermark)
        self.assertEqual(self.reopen().status().pending,1)
        replay=self.queue.consume_receipt(owner.session,receipt,"request-a")
        self.assertEqual(replay.removed,0)

    def test_actual_pairing_owner_and_shared_carrier_isolate_partial_receipt(self):
        self.seed()
        self.queue.stage(self.batch())
        # Reuse the existing pinned carrier's native-API SDK model; do not invent
        # a second response->receipt implementation for this integration test.
        wire_root=ROOT/"tools/reading_wire"
        sys.path.insert(0,str(wire_root))
        import test_pinned_transport as pinned
        self.lua.globals().carrier=self.lua.execute((ROOT/"tools/transport_probe/client.lua").read_text())
        binding=dict(self.queue.context().items())
        binding.update(binding_id="qrb_fixture",vault_scope="vault_fixture")
        self.lua.globals().config=self.to_lua(dict(endpoint="https://127.0.0.1:8443",
                                                  binding_id="qrb_fixture",ca_file="/fixture/ca.pem",
                                                  peer_certificate_sha256="1"*64))
        fixture=pinned.PinnedTransportTest("runTest")
        fixture.lua,fixture.pin,fixture.config=self.lua,b"1"*64,self.lua.globals().config
        _,_,http,https=fixture.make()
        paired=self.lua.execute((ROOT/"quartzo.koplugin/quartzo/paired_exchange.lua").read_text())
        self.lua.globals().package.loaded["quartzo/paired_exchange"]=paired
        now="2026-10-17T12:00:01.000Z"
        lines=list(self.queue.pending().event_lines.values())
        request=dict(protocol_version=1,**binding,request_id="qrtr_"+"a"*32,
                     issued_at_utc="2026-10-17T12:00:00.000Z",expires_at_utc="2026-10-17T12:01:00.000Z",
                     event_lines=lines)
        request_bytes=self.codec.encode_request(self.to_lua(request),self.to_lua(binding),now)
        self.assertIsInstance(request_bytes,str)
        sent=json.loads(request_bytes)
        results=[]
        for i,line in enumerate(lines):
            entry=self.codec.inspect_event(line)
            results.append(dict(index=i,line_digest=entry.line_digest,event_id=entry.event_id,
                                native_digest=entry.native_digest,outcome="duplicate" if i==0 else "retryable",
                                canonical_commit="qrc_fixture" if i==0 else None))
        response=dict(protocol_version=1,**binding,request_id=request["request_id"],batch_id=sent["batch_id"],results=results)
        # Canonical response order is binding,vault,device,epoch,request,batch,results.
        response={key:response[key] for key in ("protocol_version","binding_id","vault_scope","device_id",
                                               "source_epoch","request_id","batch_id","results")}
        self.lua.globals().response_bytes=json.dumps(response,separators=(",", ":"))
        document=dict(pairing_version=1,receiver_role="canonical_reading_activity_v1",endpoint="https://127.0.0.1:8443",
                      certificate_pem="-----BEGIN CERTIFICATE-----\nsynthetic\n-----END CERTIFICATE-----\n",
                      peer_certificate_sha256="1"*64,binding=binding,token="t"*43,
                      not_before_utc="2026-10-17T12:00:00.000Z",expires_at_utc="2026-10-17T12:30:00.000Z")
        document_bytes=json.dumps(document,separators=(",", ":"))
        runtime=self.lua.table(deps=self.codec_dependencies,codec=self.codec,carrier=self.lua.globals().carrier,
                               now=self.lua.eval("function() return '2026-10-17T12:00:01.000Z' end"),
                               http=http,https=https,ca_file="/fixture/ca.pem",
                               ltn12=self.lua.eval("{source={string=function(s) return function() local v=s;s=nil;return v end end}}"))
        session=paired.open(document_bytes,hashlib.sha256(document_bytes.encode()).hexdigest(),runtime)
        self.assertNotIsInstance(session,tuple)
        receipt,failure=paired.attempt(session,request_bytes)
        self.assertIsNone(failure)
        # Parsed matching claims cannot stand in for the actual opaque receipt.
        forged=self.to_lua(response["results"])
        self.assertEqual(self.queue.consume_receipt(session,forged,request_bytes),(None,"unverified_reading_receipt"))
        result=self.queue.consume_receipt(session,receipt,request_bytes)
        self.assertEqual((result.removed,result.review_retained),(1,1))
        self.assertEqual(self.reopen().status().pending,1)
        self.assertIsNone(result.source_watermark)
        paired.close(session)
        self.assertEqual(self.queue.consume_receipt(session,receipt,request_bytes),(None,"unverified_reading_receipt"))

    def test_prune_commit_failure_retains_original_pending_for_safe_replay(self):
        self.seed()
        self.queue.stage(self.batch())
        owner=self.receipt_owner()
        info=self.codec.inspect_event(self.queue.pending().event_lines[1])
        receipt=owner.mint(self.lua.table_from([info]),"request-a")

        def fail(operation,value):
            if operation=="exec" and value=="COMMIT":
                raise RuntimeError("owned synthetic commit failure")

        self.query_hook=fail
        self.assertEqual(self.queue.consume_receipt(owner.session,receipt,"request-a"),(None,"outbox_unavailable"))
        self.query_hook=None
        self.assertEqual(self.reopen().status().pending,2)

    def test_later_receipt_mismatch_rolls_back_earlier_matching_prune(self):
        self.seed()
        self.queue.stage(self.batch())
        owner=self.receipt_owner()
        claims=[self.codec.inspect_event(line) for line in self.queue.pending().event_lines.values()]
        claims[1].line_digest="0"*64
        receipt=owner.mint(self.lua.table_from(claims),"request-a")
        self.assertEqual(self.queue.consume_receipt(owner.session,receipt,"request-a"),(None,"unverified_reading_receipt"))
        self.assertEqual(self.reopen().status().pending,2)

    def test_delivery_selection_obeys_wire_byte_bound_without_deleting_excess(self):
        lines=[]
        context=dict(self.queue.context().items())
        for page in range(1,101):
            event=dict(schema_version=1,source="koreader_statistics",**context,book_row_id=1,page=page,
                       started_at_utc="2026-10-14T02:50:00.000Z",duration_seconds=20,total_pages=100,
                       observed_at_utc=OBSERVED,source_schema_version="s"*6000)
            line=self.codec.encode_event(self.to_lua(event))
            self.assertIsInstance(line,str)
            lines.append(line)
        batch=self.lua.table(event_lines=self.lua.table_from(lines),rejections=self.lua.table(),scanned_count=100)
        self.assertEqual(self.queue.stage(batch).pending,100)
        selected=self.queue.pending(100)
        self.assertLess(len(selected.event_lines),100)
        self.assertLessEqual(sum(len(line.encode())+1 for line in selected.event_lines.values()),524288)
        self.assertEqual(self.reopen().status().pending,100)

    def test_scope_tamper_corrupt_line_and_symlink_fail_closed(self):
        self.seed()
        self.queue.stage(self.batch())
        with statistics.closing(sqlite3.connect(self.owned)) as conn,conn:
            conn.execute("UPDATE identity SET source_epoch='other'")
        self.assertEqual(self.queue.status(),(None,"outbox_scope_mismatch"))
        with statistics.closing(sqlite3.connect(self.owned)) as conn,conn:
            conn.execute("UPDATE identity SET source_epoch='db_epoch_fixture'")
            conn.execute("UPDATE pending SET line='private malformed data'")
        self.assertEqual(self.queue.pending(),(None,"invalid_outbox_state"))
        self.runtime.attributes=self.lua.eval("function() return {mode='link'} end")
        self.assertEqual(self.outbox.open(str(self.root),self.runtime),(None,"unsupported_outbox_file"))

    def test_entropy_missing_wrong_length_and_invalid_epoch_do_not_create_identity(self):
        other=self.root/"fresh"
        other.mkdir()
        self.runtime.entropy=self.lua.eval("function() return 'short' end")
        self.assertEqual(self.outbox.create(str(other),"epoch",self.runtime),(None,"outbox_entropy_unavailable"))
        with statistics.closing(sqlite3.connect(other/"quartzo_sync_state.sqlite3")) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0],0)
        self.assertEqual(self.outbox.create(str(other),"invalid epoch",self.runtime),(None,"invalid_outbox_state"))

    def test_capacity_failure_is_atomic_and_does_not_discard_older_pending(self):
        self.seed()
        self.queue.stage(self.batch())
        with statistics.closing(sqlite3.connect(self.owned)) as conn,conn:
            conn.executemany("INSERT INTO review VALUES(?,?,?,?,?,?)",
                             ((n,"1","0","20","10","integer,integer,integer,integer,integer") for n in range(10000,10997)))
        self.assertEqual(self.queue.status().pending+self.queue.status().review,1000)
        self.mutate("INSERT INTO page_stat_data VALUES(1,4,104,20,10)")
        self.assertEqual(self.queue.stage(self.batch()),(None,"outbox_capacity"))
        self.assertEqual((self.reopen().status().pending,self.queue.status().review),(2,998))

    def killed_child(self, phase, expected_pending, expected_review):
        self.seed()
        batch=self.batch()
        fields=dict(event_lines=list(batch.event_lines.values()), rejections=[], scanned_count=2)
        inputs=self.root/(phase+".json")
        inputs.write_text(json.dumps(fields))
        marker=self.root/(phase+".ready")
        script=r'''
import json,sys
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import test_outbox
case=getattr(test_outbox,sys.argv[6])('runTest')
case.setUp()
try:
    root,phase,marker,input_path=sys.argv[2:6]
    case.runtime.sqlite=case.lua.execute("""local sdk=...
        return {open=function(path,mode)
            local c=sdk.open(path,mode)
            c:exec('PRAGMA cache_size=1')
            c:exec('PRAGMA cache_spill=ON')
            local exec=c.exec
            c.exec=function(_,sql)
                if sql=='PRAGMA recovery.synchronous=EXTRA' then
                    exec(c,'PRAGMA recovery.cache_size=1')
                    exec(c,'PRAGMA recovery.cache_spill=ON')
                end
                return exec(c,sql)
            end
            return c
        end}
    """,case.sdk)
    queue=None
    if not phase.startswith('restore'):
        queue=case.outbox.open(root,case.runtime)
        assert not isinstance(queue,tuple)
    def convert(value):
        if isinstance(value,dict): return case.lua.table_from({k:convert(v) for k,v in value.items()})
        if isinstance(value,list): return case.lua.table_from([convert(v) for v in value])
        return value
    batch=convert(json.loads(Path(input_path).read_text()))
    def stop_here():
        Path(marker).write_text('READY')
        sys.stdin.read(1)
    def hook(operation,value):
        if phase.endswith('before_commit') and operation=='exec' and value=='COMMIT': stop_here()
    case.query_hook=hook
    if phase.startswith('restore'):
        result=case.outbox.restore(root,'quartzo_sync_recovery_'+'41'*16+'.sqlite3',case.runtime)
    elif phase.startswith('backup'):
        result=queue.backup()
    elif phase.startswith('prune'):
        owner=case.receipt_owner()
        info=case.codec.inspect_event(queue.pending().event_lines[1])
        receipt=owner.mint(case.lua.table_from([info]),'request-a')
        result=queue.consume_receipt(owner.session,receipt,'request-a')
    else:
        result=queue.stage(batch)
    assert not isinstance(result,tuple)
    stop_here()
finally:
    case.doCleanups()
'''
        child=subprocess.Popen([sys.executable,"-c",script,str(ROOT/"tools/plugin"),str(self.root),phase,
                                str(marker),str(inputs),type(self).__name__],
                               stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            deadline=time.monotonic()+10
            while not marker.exists() and child.poll() is None and time.monotonic()<deadline:
                time.sleep(.01)
            if not marker.exists():
                if child.poll() is not None:
                    _,error=child.communicate(timeout=5)
                    self.fail("Owned child exited before readiness: "+error)
                self.fail("Owned child readiness timed out")
            if phase.endswith("before_commit"):
                journal_root=self.owned
                if phase.startswith("backup"):
                    journal_root=self.root/("quartzo_sync_recovery_"+"41"*16+".sqlite3")
                journal=Path(str(journal_root)+"-journal")
                self.assertTrue(journal.is_file())
                self.assertNotEqual(journal.read_bytes()[:8],b"\0"*8)
            child.kill()  # Only this test's owned process; no finally/SQLite close.
            child.communicate(timeout=5)
            if phase=="restore_before_commit":
                self.assertEqual(self.outbox.open(str(self.root),self.runtime),(None,"unsupported_outbox_schema"))
            else:
                status=self.reopen().status()
                self.assertEqual((status.pending,status.review),(expected_pending,expected_review))
                self.assertFalse(status.canonical_ack)
                self.assertIsNone(status.source_watermark)
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate(timeout=5)

    def test_process_stop_before_commit_rolls_back_and_recovers_hot_journal(self):
        self.killed_child("stage_before_commit",0,0)

    def test_process_stop_after_commit_preserves_selected_bytes(self):
        self.killed_child("stage_after_commit",2,0)

    def test_process_stop_during_receipt_prune_preserves_retryable_originals(self):
        self.seed()
        self.queue.stage(self.batch())
        # killed_child seeds its own source rows; remove only the synthetic source.
        self.mutate("DELETE FROM page_stat_data; DELETE FROM book")
        self.killed_child("prune_before_commit",2,1)

    def test_process_stop_after_receipt_commit_retains_unacknowledged_and_review(self):
        self.seed()
        self.queue.stage(self.batch())
        self.mutate("DELETE FROM page_stat_data; DELETE FROM book")
        self.killed_child("prune_after_commit",1,1)

    def test_process_stop_before_backup_commit_keeps_original_and_rejects_partial(self):
        self.seed()
        self.queue.stage(self.batch())
        self.mutate("DELETE FROM page_stat_data; DELETE FROM book")
        self.killed_child("backup_before_commit",2,1)
        leaf="quartzo_sync_recovery_"+"41"*16+".sqlite3"
        self.assertEqual(self.outbox.inspect_backup(str(self.root),leaf,self.runtime),(None,"unsupported_outbox_schema"))

    def test_process_stop_after_backup_commit_keeps_valid_recovery_snapshot(self):
        self.seed()
        self.queue.stage(self.batch())
        self.mutate("DELETE FROM page_stat_data; DELETE FROM book")
        self.killed_child("backup_after_commit",2,1)
        leaf="quartzo_sync_recovery_"+"41"*16+".sqlite3"
        snapshot=self.outbox.inspect_backup(str(self.root),leaf,self.runtime)
        self.assertNotIsInstance(snapshot,tuple)
        self.assertEqual((snapshot.pending,snapshot.review),(2,1))

    def test_process_stop_before_restore_commit_preserves_backup_without_empty_identity(self):
        self.seed()
        self.queue.stage(self.batch())
        snapshot,backup=self.snapshot()
        before=backup.read_bytes()
        self.owned.unlink()
        self.mutate("DELETE FROM page_stat_data; DELETE FROM book")
        self.killed_child("restore_before_commit",None,None)
        self.assertTrue(self.owned.is_file())  # Preserve interrupted destination for review.
        self.assertEqual(before,backup.read_bytes())
        preview=self.outbox.inspect_backup(str(self.root),snapshot.backup_leaf,self.runtime)
        self.assertEqual((preview.pending,preview.review),(2,1))

    def test_process_stop_after_restore_commit_keeps_original_device_and_epoch(self):
        self.seed()
        self.queue.stage(self.batch())
        context=dict(self.queue.context().items())
        snapshot,backup=self.snapshot()
        self.owned.unlink()
        self.mutate("DELETE FROM page_stat_data; DELETE FROM book")
        self.killed_child("restore_after_commit",2,1)
        self.assertEqual(dict(self.reopen().context().items()),context)


class OutboxLuaJITTest(OutboxTest):
    lua_type=LuaJITRuntime


@unittest.skipUnless(sys.platform=="linux","Actual KOReader POSIX/SQLite SDK fixture requires Linux")
class NativeOutboxTest(OutboxTest):
    lua_type=LuaJITRuntime
    make_sdk=statistics.NativeStatisticsTest.make_sdk

    def test_native_rw_attach_requires_an_explicitly_created_destination(self):
        destination=self.root/"owned-attach-fixture.sqlite3"
        conn=self.sdk.open(str(self.owned),"rw")
        try:
            stmt=conn.prepare(conn,"ATTACH DATABASE ? AS scratch")
            stmt.bind(stmt,str(destination))
            try:
                with self.assertRaises(Exception) as raised:
                    stmt.step(stmt)
                self.assertIn("unable to open database",str(raised.exception).lower())
            finally:
                stmt.close(stmt)
            self.assertFalse(destination.exists())
            created=self.sdk.open(str(destination),"rwc")
            created.close(created)
            stmt=conn.prepare(conn,"ATTACH DATABASE ? AS scratch")
            stmt.bind(stmt,str(destination))
            stmt.step(stmt)
            stmt.close(stmt)
            self.assertEqual(self.lua.eval("tonumber")(conn.rowexec(conn,"SELECT COUNT(*) FROM scratch.sqlite_master")),0)
        finally:
            conn.close(conn)

    def test_actual_linux_entropy_creates_non_fixture_device_identity(self):
        root=self.root/"native-entropy"
        root.mkdir()
        self.runtime.entropy=None
        queue=self.outbox.create(str(root),"explicit_source_epoch",self.runtime)
        self.assertNotIsInstance(queue,tuple)
        self.assertRegex(queue.context().device_id,r"^qrd_[0-9a-f]{32}$")
        self.assertNotEqual(queue.context().device_id,"qrd_"+"41"*16)


if __name__=="__main__":
    unittest.main()
