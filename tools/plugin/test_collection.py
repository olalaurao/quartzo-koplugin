"""Source selection, durable coverage and ACK frontier; synthetic owner fixtures."""
import json
import subprocess
import tempfile
import time
from pathlib import Path
import sqlite3
import sys
import unittest

import test_enrollment as enrollment
import test_outbox as outbox
import test_statistics as statistics
from test_collector import OBSERVED


class CollectionTest(unittest.TestCase):
    lua_type = statistics.LuaRuntime
    allow_owned_writes = True
    make_sdk = statistics.StatisticsTest.make_sdk
    trace = statistics.StatisticsTest.trace
    mutate = statistics.StatisticsTest.mutate
    setUp = enrollment.EnrollmentTest.setUp
    review = enrollment.EnrollmentTest.review
    enroll = enrollment.EnrollmentTest.enroll
    reopen = enrollment.EnrollmentTest.reopen
    receipt_owner = outbox.OutboxTest.receipt_owner
    batch = outbox.OutboxTest.batch
    paired_delivery_fixture = outbox.OutboxTest.paired_delivery_fixture
    send_selected = outbox.OutboxTest.send_selected

    def capture(self, limit=100):
        preview = self.queue.review_collection(str(self.path), OBSERVED, limit)
        self.assertNotIsInstance(preview, tuple)
        staged = self.queue.stage_collection(preview["pass"])
        self.assertNotIsInstance(staged, tuple)
        return preview, staged

    def acknowledge(self, owner, seconds=None):
        claims = []
        for line in self.queue.pending(100).event_lines.values():
            info = self.codec.inspect_event(line)
            if seconds is None or info.started_at_seconds in seconds:
                claims.append(info)
        receipt = owner.mint(self.lua.table_from(claims), "request")
        result = self.queue.consume_receipt(owner.session, receipt, "request")
        self.assertNotIsInstance(result, tuple)
        return result

    def test_selected_source_is_not_staged_until_confirmed_and_has_no_ack(self):
        self.queue = self.enroll()
        before = self.path.read_bytes()
        preview = self.queue.review_collection(str(self.path), OBSERVED, 1)
        self.assertEqual((preview.event_count, preview.review_count), (1, 0))
        preview.event_count = 100  # Public observations cannot replace private selection.
        self.assertEqual(self.queue.status().pending, 0)
        self.assertEqual(self.queue.stage_collection(self.lua.table()), (None, "outbox_collection_review_required"))
        self.assertEqual(self.queue.next_collection(preview["pass"], OBSERVED),
                         (None, "outbox_collection_review_required"))
        result = self.queue.stage_collection(preview["pass"])
        self.assertEqual(result.pending, 1)
        self.assertIsNone(self.queue.status().source_watermark)
        self.assertEqual(self.queue.stage_collection(preview["pass"]), (None, "outbox_collection_review_required"))
        following = self.queue.next_collection(preview["pass"], OBSERVED)
        self.assertTrue(following.complete)
        self.assertEqual(self.queue.stage_collection(preview["pass"]).pending, 2)
        self.assertEqual(self.path.read_bytes(), before)

    def test_out_of_order_partial_ack_cannot_pass_earlier_pending_and_survives_reopen(self):
        self.queue = self.enroll()
        self.capture()
        owner = self.receipt_owner()
        self.assertEqual(self.acknowledge(owner, {110}).source_watermark, 99)
        self.queue = self.reopen()
        self.assertEqual(self.queue.status().source_watermark, 99)
        self.assertEqual(self.acknowledge(owner, {100}).source_watermark, 109)
        self.assertEqual(self.queue.status().pending, 0)

    def test_pending_review_blocks_frontier_and_resolution_never_fabricates_ack(self):
        self.mutate("INSERT INTO page_stat_data VALUES(1,0,105,20,10)")
        self.queue = self.enroll()
        self.capture()
        owner = self.receipt_owner()
        self.assertEqual(self.acknowledge(owner).source_watermark, 104)
        review = self.queue.review_rejections()
        self.assertEqual((review.count, review.remaining), (1, 0))
        self.assertEqual(self.queue.resolve_rejections(self.lua.table()), (None, "outbox_review_changed"))
        self.assertEqual(self.queue.resolve_rejections(review.review).retained, 1)
        self.assertEqual(self.queue.status().unresolved_review, 0)
        self.assertEqual(self.queue.status().source_watermark, 104)
        # A new pass intentionally overlaps and preserves the resolution.
        self.capture()
        self.assertEqual(self.queue.status().unresolved_review, 0)
        self.assertEqual(self.acknowledge(owner).source_watermark, 109)
        self.assertEqual(self.queue.status().review, 1)

    def test_large_same_second_group_and_restart_overlap_do_not_skip_or_regress(self):
        self.mutate("DELETE FROM page_stat_data")
        with statistics.closing(sqlite3.connect(self.path)) as conn, conn:
            conn.executemany("INSERT INTO page_stat_data VALUES(1,?,100,20,400)", ((page,) for page in range(1, 251)))
            conn.execute("INSERT INTO page_stat_data VALUES(1,251,101,20,400)")
        self.queue = self.enroll()
        preview, staged = self.capture()
        owner = self.receipt_owner()
        observed_ids = set()
        while True:
            observed_ids.update(self.codec.inspect_event(line).event_id for line in self.queue.pending(100).event_lines.values())
            ack = self.acknowledge(owner)
            self.assertEqual(ack.source_watermark, 100 if staged.complete else 99)
            if staged.complete:
                break
            preview = self.queue.next_collection(preview["pass"], OBSERVED)
            staged = self.queue.stage_collection(preview["pass"])
        self.assertEqual(len(observed_ids), 251)
        self.queue = self.reopen()
        _, staged = self.capture()
        self.assertEqual(staged.pending, 100)  # Inclusive overlap replays known native IDs.
        self.assertEqual(self.acknowledge(owner).source_watermark, 100)

    def test_stage_commit_failure_rolls_back_coverage_and_selection_can_be_retried(self):
        self.queue = self.enroll()
        preview = self.queue.review_collection(str(self.path), OBSERVED)
        def fail(operation, value):
            if operation == "exec" and value == "COMMIT":
                raise RuntimeError("synthetic selected-source commit failure")
        self.query_hook = fail
        self.assertEqual(self.queue.stage_collection(preview["pass"]), (None, "outbox_unavailable"))
        self.query_hook = None
        with statistics.closing(sqlite3.connect(self.owned)) as conn:
            self.assertEqual(conn.execute("SELECT ack_watermark,scan_before FROM progress").fetchone(), (None, None))
        self.assertEqual(self.reopen().status().pending, 0)
        self.assertEqual(self.queue.stage_collection(preview["pass"]).pending, 2)
        self.assertIsNone(self.queue.status().source_watermark)

    def test_source_change_or_vacuum_between_review_and_confirmation_stages_nothing(self):
        self.queue = self.enroll()
        preview = self.queue.review_collection(str(self.path), OBSERVED)
        self.identity["ino"] += 1
        self.assertEqual(self.queue.stage_collection(preview["pass"]), (None, "statistics_source_changed"))
        self.identity["ino"] -= 1
        with statistics.closing(sqlite3.connect(self.path)) as conn:
            conn.execute("VACUUM")
        self.assertEqual(self.queue.stage_collection(preview["pass"]), (None, "outbox_collection_changed"))
        self.assertEqual(self.queue.status().pending, 0)

    def test_review_resolution_rechecks_exact_cases_and_rolls_back_changed_neighbor(self):
        self.mutate("INSERT INTO page_stat_data VALUES(1,0,105,20,10),(1,0,106,20,10)")
        self.queue = self.enroll()
        self.capture()
        preview = self.queue.review_rejections()
        with statistics.closing(sqlite3.connect(self.owned)) as conn, conn:
            conn.execute("UPDATE review SET duration='21' WHERE started_at=106")
        self.assertEqual(self.queue.resolve_rejections(preview.review), (None, "outbox_review_changed"))
        self.assertEqual(self.queue.status().unresolved_review, 2)

    def test_recovery_preserves_frontier_and_review_decisions(self):
        self.mutate("INSERT INTO page_stat_data VALUES(1,0,105,20,10)")
        self.queue = self.enroll()
        self.capture()
        owner = self.receipt_owner()
        self.acknowledge(owner)
        self.queue.resolve_rejections(self.queue.review_rejections().review)
        saved = self.queue.backup()
        preview = self.outbox.inspect_backup(str(self.root), saved.backup_leaf, self.runtime)
        self.owned.unlink()  # Only this fixture's primary; backup is preserved.
        restored = self.outbox.restore(str(self.root), saved.backup_leaf, self.runtime, preview)
        self.assertNotIsInstance(restored, tuple)
        self.assertEqual((restored.status().source_watermark, restored.status().unresolved_review), (104, 0))

    def test_initially_empty_source_gains_witnesses_atomically_without_changing_identity(self):
        self.mutate("DELETE FROM page_stat_data; DELETE FROM book; DELETE FROM sqlite_sequence")
        self.queue = self.enroll()
        context = dict(self.queue.context().items())
        self.mutate("INSERT INTO book(title) VALUES('new'); INSERT INTO page_stat_data VALUES(1,1,100,20,10)")
        preview, staged = self.capture()
        self.assertTrue(staged.source_reopen_required)
        self.queue = self.reopen()
        self.assertEqual(dict(self.queue.context().items()), context)
        self.assertEqual(self.queue.check_source(str(self.path)).source_state, "matches_enrollment")
        with statistics.closing(sqlite3.connect(self.owned)) as conn:
            first, boundary = conn.execute("SELECT first_event,history_boundary FROM source").fetchone()
            self.assertEqual((first, boundary), ("1,1,100,20,10", ""))
        self.mutate("DELETE FROM page_stat_data; DELETE FROM book; DELETE FROM sqlite_sequence")
        self.assertEqual(self.queue.check_source(str(self.path)), (None, "statistics_source_changed"))
        self.assertEqual(self.queue.status().pending, 1)

    def test_empty_reset_requires_settled_work_and_preserves_device_and_old_recovery(self):
        self.queue = self.enroll()
        old = dict(self.queue.context().items())
        self.capture()
        self.mutate("DELETE FROM page_stat_data; DELETE FROM book; DELETE FROM sqlite_sequence")
        self.assertEqual(self.queue.review_new_generation(str(self.path)), (None, "outbox_source_not_settled"))
        self.acknowledge(self.receipt_owner())  # Old pending facts can still finish after a source reset.
        self.runtime.entropy = self.lua.eval("(function() local n=65;return function() n=n+1;return string.rep(string.char(n),16) end end)()")
        preview = self.queue.review_new_generation(str(self.path))
        changed = self.queue.begin_new_generation(preview.review)
        self.assertNotIsInstance(changed, tuple)
        current = dict(changed.queue.context().items())
        self.assertEqual(current["device_id"], old["device_id"])
        self.assertNotEqual(current["source_epoch"], old["source_epoch"])
        self.assertIsNone(changed.queue.status().source_watermark)
        backup = self.outbox.inspect_backup(str(self.root), changed.backup_leaf, self.runtime)
        self.assertEqual((backup.device_id, backup.source_epoch), (old["device_id"], old["source_epoch"]))
        self.assertEqual(changed.queue.check_source(str(self.path)).source_state, "matches_enrollment")

    def test_unchanged_or_nonempty_replacement_cannot_silently_rotate_epoch(self):
        self.queue = self.enroll()
        self.assertEqual(self.queue.review_new_generation(str(self.path)), (None, "statistics_source_unchanged"))
        before = self.owned.read_bytes()
        self.identity["ino"] += 1
        self.assertEqual(self.queue.review_new_generation(str(self.path)),
                         (None, "statistics_source_reconciliation_required"))
        self.assertEqual(self.owned.read_bytes(), before)

    def test_receipt_commit_failure_rolls_back_prune_and_watermark_together(self):
        self.queue = self.enroll()
        self.capture()
        owner = self.receipt_owner()
        def fail(operation, value):
            if operation == "exec" and value == "COMMIT":
                raise RuntimeError("synthetic ACK commit failure")
        self.query_hook = fail
        self.assertEqual(self.queue.consume_receipt(owner.session,
            owner.mint(self.lua.table_from([self.codec.inspect_event(line) for line in self.queue.pending().event_lines.values()]), "request"),
            "request"), (None, "outbox_unavailable"))
        self.query_hook = None
        self.assertEqual(self.reopen().status().pending, 2)
        self.assertIsNone(self.queue.status().source_watermark)

    def test_corrupt_pending_neighbor_cannot_advance_frontier_when_another_receipt_arrives(self):
        self.queue = self.enroll()
        self.capture()
        entries = [self.codec.inspect_event(line) for line in self.queue.pending().event_lines.values()]
        earlier = next(entry for entry in entries if entry.started_at_seconds == 100)
        later = next(entry for entry in entries if entry.started_at_seconds == 110)
        raw = json.loads(next(line for line in self.queue.pending().event_lines.values()
                              if self.codec.inspect_event(line).started_at_seconds == 100))
        raw.pop("event_id")
        raw["started_at_utc"] = "1970-01-01T00:03:20.000Z"
        changed = self.codec.encode_event(self.to_lua(raw))
        changed_info = self.codec.inspect_event(changed)
        with statistics.closing(sqlite3.connect(self.owned)) as conn, conn:
            conn.execute("UPDATE pending SET line=?,native_digest=? WHERE event_id=?",
                         (changed, changed_info.native_digest, earlier.event_id))
        owner = self.receipt_owner()
        receipt = owner.mint(self.lua.table_from([later]), "request")
        self.assertEqual(self.queue.consume_receipt(owner.session, receipt, "request"),
                         (None, "invalid_outbox_state"))
        self.assertEqual(self.reopen().status().pending, 2)
        self.assertIsNone(self.queue.status().source_watermark)

    def test_explicit_full_rescan_restarts_progress_with_same_identity_and_catches_backdated_fact(self):
        self.queue = self.enroll()
        context = dict(self.queue.context().items())
        self.capture()
        owner = self.receipt_owner()
        self.assertEqual(self.acknowledge(owner).source_watermark, 109)
        self.mutate("INSERT INTO page_stat_data VALUES(1,3,105,20,10)")
        preview = self.queue.review_collection(str(self.path), OBSERVED, 100, "all_history")
        self.assertEqual(self.queue.status().source_watermark, 109)  # Review alone is inert.
        self.assertEqual(preview.event_count, 3)
        self.assertEqual(self.queue.stage_collection(preview["pass"]).pending, 3)
        self.assertIsNone(self.queue.status().source_watermark)
        self.assertEqual(dict(self.queue.context().items()), context)
        self.assertEqual(self.acknowledge(owner, {100, 110}).source_watermark, 104)
        self.assertEqual(self.acknowledge(owner, {105}).source_watermark, 109)

    def test_failed_full_rescan_preserves_old_progress_and_all_retained_cases(self):
        self.queue = self.enroll()
        self.capture()
        self.acknowledge(self.receipt_owner())
        with statistics.closing(sqlite3.connect(self.owned)) as conn, conn:
            conn.executemany("INSERT INTO review VALUES(?,'1','0','20','10','integer,integer,integer,integer,integer',1)",
                             ((n,) for n in range(10000, 10999)))
        preview = self.queue.review_collection(str(self.path), OBSERVED, 100, "all_history")
        self.assertEqual(self.queue.stage_collection(preview["pass"]), (None, "outbox_capacity"))
        self.assertEqual((self.reopen().status().source_watermark, self.queue.status().pending,
                          self.queue.status().review), (109, 0, 999))

    def test_clock_rollback_reviews_full_history_without_skipping_earlier_new_fact(self):
        self.queue = self.enroll()
        self.capture()
        self.acknowledge(self.receipt_owner())
        self.mutate("INSERT INTO page_stat_data VALUES(1,3,50,20,10)")
        preview = self.queue.review_collection(str(self.path), "1970-01-01T00:00:50.000Z", 100)
        self.assertTrue(preview.clock_reset)
        self.assertEqual(preview.event_count, 3)
        self.assertEqual(self.queue.status().source_watermark, 109)  # Consent has not happened.
        self.assertEqual(self.queue.stage_collection(preview["pass"]).pending, 3)
        self.assertIsNone(self.queue.status().source_watermark)

    def test_backward_clock_during_transient_pass_requires_fresh_review(self):
        self.queue = self.enroll()
        preview, _ = self.capture(1)
        self.assertEqual(self.queue.next_collection(preview["pass"], "1970-01-01T00:00:50.000Z"),
                         (None, "outbox_collection_changed"))
        self.assertEqual(self.queue.status().pending, 1)

    def test_new_generation_commit_failure_keeps_identity_and_mandatory_backup(self):
        self.queue = self.enroll()
        context = dict(self.queue.context().items())
        self.capture()
        self.acknowledge(self.receipt_owner())
        self.mutate("DELETE FROM page_stat_data; DELETE FROM book; DELETE FROM sqlite_sequence")
        self.runtime.entropy = self.lua.eval("(function() local n=65;return function() n=n+1;return string.rep(string.char(n),16) end end)()")
        preview = self.queue.review_new_generation(str(self.path))
        commits = []
        def fail(operation, value):
            if operation == "exec" and value == "COMMIT":
                commits.append(True)
                if len(commits) == 2:
                    raise RuntimeError("synthetic epoch commit failure")
        self.query_hook = fail
        self.assertEqual(self.queue.begin_new_generation(preview.review), (None, "outbox_unavailable"))
        self.query_hook = None
        self.assertEqual(dict(self.reopen().context().items()), context)
        backups = list(self.root.glob("quartzo_sync_recovery_*.sqlite3"))
        self.assertEqual(len(backups), 1)
        saved = self.outbox.inspect_backup(str(self.root), backups[0].name, self.runtime)
        self.assertEqual((saved.device_id, saved.source_epoch), (context["device_id"], context["source_epoch"]))

    def schema2_queue(self):
        legacy = self.outbox.create(str(self.root), "legacy_epoch", self.runtime)
        self.assertNotIsInstance(legacy, tuple)
        with statistics.closing(sqlite3.connect(self.owned)) as conn, conn:
            conn.execute("CREATE TABLE source(id INTEGER PRIMARY KEY CHECK(id=1),volume TEXT NOT NULL,inode TEXT NOT NULL,"
                         "book_sequence TEXT NOT NULL,first_event TEXT NOT NULL,last_event TEXT NOT NULL,history_boundary TEXT NOT NULL)")
            conn.execute("INSERT INTO source VALUES(1,'7','11','1','1,1,100,20,10','1,2,110,30,10','110')")
            conn.execute("PRAGMA user_version=2")
        return self.reopen()

    def test_legacy_schema2_recovery_is_recognized_without_progress_migration(self):
        current = self.schema2_queue()
        before = self.owned.read_bytes()
        self.assertEqual(current.check_source(str(self.path)).source_state, "matches_enrollment")
        self.assertFalse(current.status().collection_supported)
        self.assertEqual(current.review_collection(str(self.path), OBSERVED), (None, "outbox_collection_review_required"))
        self.assertEqual(self.owned.read_bytes(), before)
        saved = current.backup()
        preview = self.outbox.inspect_backup(str(self.root), saved.backup_leaf, self.runtime)
        self.owned.unlink()
        restored = self.outbox.restore(str(self.root), saved.backup_leaf, self.runtime, preview)
        self.assertEqual(restored.context().source_epoch, "legacy_epoch")
        with statistics.closing(sqlite3.connect(self.owned)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 2)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='progress'").fetchone()[0], 0)

    def test_explicit_schema2_upgrade_preserves_identity_bytes_review_and_old_recovery(self):
        self.mutate("INSERT INTO page_stat_data VALUES(1,0,105,20,10)")
        self.queue = self.schema2_queue()
        self.queue.stage(self.batch())
        context = dict(self.queue.context().items())
        lines = list(self.queue.pending().event_lines.values())
        preview = self.queue.review_upgrade(str(self.path))
        upgraded = self.queue.upgrade_queue(preview.review)
        self.assertNotIsInstance(upgraded, tuple)
        self.queue = upgraded.queue
        self.assertEqual(dict(self.queue.context().items()), context)
        self.assertEqual(list(self.queue.pending().event_lines.values()), lines)
        self.assertEqual(self.queue.status().unresolved_review, 1)
        self.assertIsNone(self.queue.status().source_watermark)
        self.assertTrue(self.queue.status().collection_supported)
        with statistics.closing(sqlite3.connect(self.root / upgraded.backup_leaf)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 2)

    def test_schema_upgrade_rechecks_source_and_rolls_back_failed_ddl_commit(self):
        self.queue = self.schema2_queue()
        self.queue.stage(self.batch())
        context = dict(self.queue.context().items())
        lines = list(self.queue.pending().event_lines.values())
        preview = self.queue.review_upgrade(str(self.path))
        before = self.owned.read_bytes()
        self.identity["ino"] += 1
        self.assertEqual(self.queue.upgrade_queue(preview.review), (None, "statistics_source_changed"))
        self.assertEqual(self.owned.read_bytes(), before)
        self.identity["ino"] -= 1
        preview = self.queue.review_upgrade(str(self.path))
        commits = []
        def fail(operation, value):
            if operation == "exec" and value == "COMMIT":
                commits.append(True)
                if len(commits) == 2:
                    raise RuntimeError("synthetic migration commit failure")
        self.query_hook = fail
        self.assertEqual(self.queue.upgrade_queue(preview.review), (None, "outbox_unavailable"))
        self.query_hook = None
        self.queue = self.reopen()
        self.assertEqual(dict(self.queue.context().items()), context)
        self.assertEqual(list(self.queue.pending().event_lines.values()), lines)
        self.assertTrue(self.queue.status().upgrade_supported)
        with statistics.closing(sqlite3.connect(self.owned)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 2)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name IN ('progress','review_schema2')").fetchone()[0], 0)

    def test_actual_pairing_owner_frontier_is_bounded_by_retained_review_and_pending(self):
        self.mutate("INSERT INTO page_stat_data VALUES(1,0,105,20,10)")
        self.queue = self.enroll()
        self.capture()
        self.already_selected = True
        second = self.codec.inspect_event(self.queue.pending().event_lines[2])
        self.expected_source_watermark = min(109, 104, second.started_at_seconds - 1)
        # Same real paired owner/carrier fixture, not a second receipt issuer.
        outbox.OutboxTest.test_actual_pairing_owner_and_shared_carrier_isolate_partial_receipt(self)

    def test_send_selected_schema3_facts_keeps_frontier_bounded_after_source_loss(self):
        self.mutate("INSERT INTO page_stat_data VALUES(1,0,105,20,10)")
        self.queue=self.enroll()
        self.capture()
        self.already_selected=True
        second=self.codec.inspect_event(self.queue.pending().event_lines[2])
        self.expected_source_watermark=min(109,104,second.started_at_seconds-1)
        outbox.OutboxTest.test_send_pending_uses_real_pairing_partial_receipt_and_closed_sqlite_handles(self)

    def stopped_collection(self, after_commit):
        self.mutate("DELETE FROM page_stat_data; DELETE FROM book; DELETE FROM sqlite_sequence")
        self.queue = self.enroll()
        context = dict(self.queue.context().items())
        self.mutate("INSERT INTO book(title) VALUES('new'); INSERT INTO page_stat_data VALUES(1,1,100,20,10)")
        marker = self.root / "collection-ready"
        child_temp = self.root / "child-fixtures"
        child_temp.mkdir()
        script = '''
import sys,tempfile
from pathlib import Path
sys.path.insert(0,sys.argv[1])
import test_collection
root,source,marker,child_temp,after_commit=sys.argv[2:7]
tempfile.tempdir=child_temp
case=getattr(test_collection,sys.argv[7])('runTest')
case.setUp()
case.root,case.path=Path(root),Path(source)
case.owned=case.root/'quartzo_sync_state.sqlite3'
case.runtime.sqlite=case.lua.execute("""local sdk=...
    return {open=function(path,mode)
        local c=sdk.open(path,mode)
        if mode~='ro' then c:exec('PRAGMA cache_size=1');c:exec('PRAGMA cache_spill=ON') end
        return c
    end}
""",case.sdk)
case.queue=case.reopen()
preview=case.queue.review_collection(source,'2026-10-24T00:00:00.000Z')
assert not isinstance(preview,tuple)
def stop_here():
    Path(marker).write_text('ready')
    sys.stdin.read(1)
def hook(operation,value):
    if after_commit=='False' and operation=='exec' and value=='COMMIT': stop_here()
case.query_hook=hook
result=case.queue.stage_collection(preview['pass'])
assert not isinstance(result,tuple)
stop_here()
'''
        child = subprocess.Popen([sys.executable, "-c", script, str(Path(__file__).parent),
            str(self.root), str(self.path), str(marker), str(child_temp), str(after_commit), type(self).__name__],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 15
            while not marker.exists() and child.poll() is None and time.monotonic() < deadline:
                time.sleep(.01)
            if not marker.exists():
                self.fail("Owned collection child failed before readiness: " + str(child.communicate(timeout=5)))
            if not after_commit:
                journal = Path(str(self.owned) + "-journal")
                self.assertTrue(journal.is_file())
                self.assertNotEqual(journal.read_bytes()[:8], b"\0" * 8)
            child.kill()  # This fixture's own process only; no SQLite close/finally.
            child.communicate(timeout=5)
            self.queue = self.reopen()
            self.assertEqual(dict(self.queue.context().items()), context)
            self.assertEqual(self.queue.status().pending, 1 if after_commit else 0)
            self.assertIsNone(self.queue.status().source_watermark)
            with statistics.closing(sqlite3.connect(self.owned)) as conn:
                self.assertEqual(conn.execute("SELECT scan_before FROM progress").fetchone()[0],
                                 "99" if after_commit else None)
                self.assertEqual(conn.execute("SELECT first_event FROM source").fetchone()[0],
                                 "1,1,100,20,10" if after_commit else "")
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate(timeout=5)

    def test_process_stop_before_collection_commit_recovers_events_coverage_and_witnesses_together(self):
        self.stopped_collection(False)

    def test_process_stop_after_collection_commit_keeps_events_coverage_and_witnesses_together(self):
        self.stopped_collection(True)


class CollectionLuaJITTest(CollectionTest):
    lua_type = statistics.LuaJITRuntime


@unittest.skipUnless(sys.platform == "linux", "Actual KOReader POSIX/SQLite SDK fixture requires Linux")
class NativeCollectionTest(CollectionTest):
    lua_type = statistics.LuaJITRuntime
    make_sdk = statistics.NativeStatisticsTest.make_sdk


if __name__ == "__main__":
    unittest.main()
