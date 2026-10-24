"""Fresh explicitly reviewed source enrollment through the existing SQLite owner."""
from pathlib import Path
import json
import os
import sqlite3
import subprocess
import sys
import unittest

import test_collector as collector
import test_statistics as statistics


class EnrollmentTest(unittest.TestCase):
    lua_type = statistics.LuaRuntime
    allow_owned_writes = True
    make_sdk = statistics.StatisticsTest.make_sdk
    trace = statistics.StatisticsTest.trace
    mutate = statistics.StatisticsTest.mutate

    def setUp(self):
        collector.CollectorTest.setUp(self)
        self.lua.globals().package.loaded["quartzo/collector"] = self.collector
        self.outbox = self.lua.execute((collector.ROOT / "quartzo.koplugin/quartzo/outbox.lua").read_text(encoding="utf-8"))
        self.root = Path(self.temp.name) / "owned"
        self.root.mkdir()
        self.owned = self.root / "quartzo_sync_state.sqlite3"
        self.identity = dict(mode="file", dev=7, ino=11)
        wrap = self.lua.eval("function(f) return function(...) return f(...) end end")
        self.runtime = self.lua.table(sqlite=self.sdk, codec=self.codec,
            attributes=wrap(lambda path: self.lua.table_from(self.identity) if Path(path).is_file() else None),
            entropy=self.lua.eval("function() return string.rep('A',16) end"))
        self.runtime.filesystem = self.lua.execute('''
            local entries=...
            return {dir=function(root)
                local names=entries(root)
                local position=0
                return function() position=position+1;return names[position] end,{close=function() end}
            end}
        ''', wrap(lambda root: self.lua.table_from([entry.name for entry in Path(root).iterdir()])))
        self.mutate("""INSERT INTO book(title) VALUES('private title');
            INSERT INTO page_stat_data VALUES(1,1,100,20,10),(1,2,110,30,10);""")

    def review(self):
        result = self.outbox.review_source(str(self.root), str(self.path), self.runtime)
        self.assertNotIsInstance(result, tuple)
        return result

    def enroll(self):
        result = self.outbox.enroll(str(self.root), self.review().review, self.runtime)
        self.assertNotIsInstance(result, tuple)
        return result

    def reopen(self):
        result = self.outbox.open(str(self.root), self.runtime)
        self.assertNotIsInstance(result, tuple)
        return result

    def stage(self, queue):
        fields = dict(queue.context().items())
        fields["observed_at_utc"] = collector.OBSERVED
        batch = self.collector.collect(str(self.path), self.lua.table_from(fields), self.codec, self.sdk)
        self.assertNotIsInstance(batch, tuple)
        result = queue.stage(batch)  # Synthetic owner fixture; no production historical import.
        self.assertNotIsInstance(result, tuple)

    def test_review_is_inert_and_only_opaque_confirmation_creates_v2_identity(self):
        source = self.path.read_bytes()
        review = self.review()
        self.assertFalse(self.owned.exists())
        self.assertTrue(review.has_history)
        self.assertEqual(self.outbox.enroll(str(self.root), self.lua.table(verified=True), self.runtime),
                         (None, "statistics_source_review_required"))
        self.assertFalse(self.owned.exists())
        queue = self.outbox.enroll(str(self.root), review.review, self.runtime)
        self.assertNotIsInstance(queue, tuple)
        context = dict(queue.context().items())
        self.assertEqual(context, dict(device_id="qrd_" + "41"*16, source_epoch="qse_" + "41"*16))
        self.assertEqual((queue.status().pending, queue.status().review), (0, 0))
        self.assertEqual(queue.check_source(str(self.path)).source_state, "matches_enrollment")
        self.assertEqual(source, self.path.read_bytes())
        with statistics.closing(sqlite3.connect(self.owned)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 2)
            self.assertEqual(conn.execute("SELECT * FROM source").fetchone(), (1, "7", "11", "1",
                             "1,1,100,20,10", "1,2,110,30,10", "110"))
        self.assertEqual(dict(self.reopen().context().items()), context)

    def test_stale_review_never_creates_empty_or_new_identity(self):
        review = self.review()
        self.mutate("DELETE FROM page_stat_data")
        self.assertEqual(self.outbox.enroll(str(self.root), review.review, self.runtime),
                         (None, "statistics_source_changed"))
        self.assertFalse(self.owned.exists())

    def test_source_preview_uses_owned_scope_without_staging_or_advancing_state(self):
        queue = self.enroll()
        source_before, owned_before = self.path.read_bytes(), self.owned.read_bytes()
        preview = queue.preview_source(str(self.path), collector.OBSERVED, None, 1)
        self.assertNotIsInstance(preview, tuple)
        self.assertEqual(preview.scanned_count, 1)
        self.assertFalse(preview.complete)
        fields = json.loads(preview.event_lines[1])
        self.assertEqual((fields["device_id"], fields["source_epoch"]),
                         (queue.context().device_id, queue.context().source_epoch))
        later = queue.preview_source(str(self.path), collector.OBSERVED, preview.next_scan, 1)
        self.assertTrue(later.complete)
        self.assertNotEqual(preview.event_lines[1], later.event_lines[1])
        self.assertFalse(preview.canonical_ack)
        self.assertEqual((queue.status().pending, queue.status().review), (0, 0))
        self.assertIsNone(queue.status().source_watermark)
        self.assertEqual((self.path.read_bytes(), self.owned.read_bytes()), (source_before, owned_before))

    def test_source_preview_rejects_changed_source_before_raw_scan_and_foreign_continuation(self):
        queue = self.enroll()
        preview = queue.preview_source(str(self.path), collector.OBSERVED, None, 1)
        preview.next_scan.source_epoch = "foreign_epoch"
        self.assertEqual(queue.preview_source(str(self.path), collector.OBSERVED, preview.next_scan, 1),
                         (None, "invalid_statistics_collection"))
        self.identity["ino"] += 1
        self.calls.clear()
        self.assertEqual(queue.preview_source(str(self.path), collector.OBSERVED, None, 1),
                         (None, "statistics_source_changed"))
        self.assertFalse(any(operation == "query" and value.startswith("SELECT rowid")
                             for operation, value in self.calls))
        self.assertEqual(queue.status().pending, 0)

    def test_existing_primary_or_recovery_prevents_fresh_enrollment(self):
        queue = self.enroll()
        self.stage(queue)
        before = self.owned.read_bytes()
        self.assertEqual(self.outbox.review_source(str(self.root), str(self.path), self.runtime),
                         (None, "outbox_exists"))
        self.assertEqual(self.owned.read_bytes(), before)
        queue.backup()
        self.owned.unlink()  # This test's private state only.
        self.assertEqual(self.outbox.review_source(str(self.root), str(self.path), self.runtime),
                         (None, "outbox_recovery_review_required"))
        self.assertFalse(self.owned.exists())

    def test_reset_or_replaced_source_preserves_old_pending_identity_and_recovery(self):
        queue = self.enroll()
        self.stage(queue)
        context = dict(queue.context().items())
        lines = list(queue.pending().event_lines.values())
        self.identity["ino"] += 1
        self.assertEqual(queue.check_source(str(self.path)), (None, "statistics_source_changed"))
        self.assertEqual(list(queue.pending().event_lines.values()), lines)
        self.assertEqual(dict(self.reopen().context().items()), context)
        saved = queue.backup()
        self.assertNotIsInstance(saved, tuple)
        self.assertEqual(saved.pending, 2)

    def test_v2_recovery_preserves_original_context_checkpoint_and_selected_bytes(self):
        queue = self.enroll()
        self.stage(queue)
        context = dict(queue.context().items())
        lines = list(queue.pending().event_lines.values())
        saved = queue.backup()
        preview = self.outbox.inspect_backup(str(self.root), saved.backup_leaf, self.runtime)
        self.owned.unlink()
        restored = self.outbox.restore(str(self.root), saved.backup_leaf, self.runtime, preview)
        self.assertNotIsInstance(restored, tuple)
        self.assertEqual(dict(restored.context().items()), context)
        self.assertEqual(list(restored.pending().event_lines.values()), lines)
        self.assertEqual(restored.check_source(str(self.path)).source_state, "matches_enrollment")
        self.assertIsNone(restored.status().source_watermark)
        self.assertFalse(restored.status().canonical_ack)

    def test_recovery_review_binds_source_checkpoint_with_same_identity_and_counts(self):
        queue = self.enroll()
        saved = queue.backup()
        preview = self.outbox.inspect_backup(str(self.root), saved.backup_leaf, self.runtime)
        self.owned.unlink()
        with statistics.closing(sqlite3.connect(self.root / saved.backup_leaf)) as conn, conn:
            conn.execute("UPDATE source SET inode='12'")
        self.assertEqual(self.outbox.restore(str(self.root), saved.backup_leaf, self.runtime, preview),
                         (None, "outbox_backup_changed"))
        self.assertFalse(self.owned.exists())

    def test_enrollment_commit_failure_retains_unregistered_artifact_without_identity(self):
        review = self.review()
        def fail(operation, value):
            if operation == "exec" and value == "COMMIT":
                raise RuntimeError("synthetic private commit failure")
        self.query_hook = fail
        self.assertEqual(self.outbox.enroll(str(self.root), review.review, self.runtime),
                         (None, "outbox_unavailable"))
        self.query_hook = None
        self.assertTrue(self.owned.is_file())
        self.assertEqual(self.outbox.open(str(self.root), self.runtime), (None, "unsupported_outbox_schema"))
        self.assertEqual(self.outbox.enroll(str(self.root), review.review, self.runtime), (None, "outbox_exists"))

    def test_legacy_state_is_preserved_without_implicit_schema_or_epoch_migration(self):
        queue = self.outbox.create(str(self.root), "legacy_epoch", self.runtime)
        context = dict(queue.context().items())
        source_queries = len(self.calls)
        self.assertEqual(queue.check_source(str(self.path)).source_state, "review_required")
        self.assertEqual(queue.preview_source(str(self.path), collector.OBSERVED),
                         (None, "statistics_source_review_required"))
        self.assertFalse(any(operation == "open" and value == "ro" for operation, value in self.calls[source_queries:]))
        before = self.owned.read_bytes()
        self.assertEqual(self.reopen().status().source_state, "review_required")
        self.assertEqual(self.owned.read_bytes(), before)
        self.assertEqual(dict(queue.context().items()), context)
        with statistics.closing(sqlite3.connect(self.owned)) as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name='source'").fetchone()[0], 0)

    def test_explicit_continuity_renewal_retains_identity_queue_and_original_history_boundary(self):
        queue = self.enroll()
        self.stage(queue)
        context = dict(queue.context().items())
        lines = list(queue.pending().event_lines.values())
        self.identity["ino"] += 1
        self.mutate("INSERT INTO book(title) VALUES('new'); INSERT INTO page_stat_data VALUES(2,1,200,40,20)")
        self.assertEqual(queue.check_source(str(self.path)), (None, "statistics_source_changed"))
        preview = queue.review_source_change(str(self.path))
        self.assertNotIsInstance(preview, tuple)
        with statistics.closing(sqlite3.connect(self.owned)) as conn:
            self.assertEqual(conn.execute("SELECT inode,history_boundary FROM source").fetchone(), ("11", "110"))
        renewed = self.reopen().renew_source(preview.review)
        self.assertNotIsInstance(renewed, tuple)
        self.assertEqual(dict(renewed.context().items()), context)
        self.assertEqual(list(renewed.pending().event_lines.values()), lines)
        self.assertEqual(renewed.check_source(str(self.path)).source_state, "matches_enrollment")
        with statistics.closing(sqlite3.connect(self.owned)) as conn:
            self.assertEqual(conn.execute("SELECT inode,book_sequence,history_boundary FROM source").fetchone(),
                             ("12", "1", "110"))
        self.assertEqual(renewed.renew_source(preview.review), (None, "statistics_source_review_required"))

    def test_reset_history_cannot_renew_or_overwrite_the_original_source_context(self):
        queue = self.enroll()
        self.stage(queue)
        self.mutate("DELETE FROM page_stat_data; DELETE FROM book")
        before = self.owned.read_bytes()
        self.assertEqual(queue.review_source_change(str(self.path)), (None, "statistics_source_changed"))
        self.assertEqual(self.owned.read_bytes(), before)
        self.assertEqual(queue.status().pending, 2)

    def test_source_review_cannot_cross_queue_identity_or_be_replaced_by_bare_source_capability(self):
        queue = self.enroll()
        self.identity["ino"] += 1
        bare = self.module.review_source(str(self.path), self.runtime)
        self.assertEqual(queue.renew_source(bare.review), (None, "statistics_source_review_required"))
        preview = queue.review_source_change(str(self.path))
        with statistics.closing(sqlite3.connect(self.owned)) as conn, conn:
            conn.execute("UPDATE identity SET source_epoch='different_epoch'")
        self.assertEqual(self.reopen().renew_source(preview.review), (None, "outbox_scope_mismatch"))
        with statistics.closing(sqlite3.connect(self.owned)) as conn:
            self.assertEqual(conn.execute("SELECT inode FROM source").fetchone()[0], "11")

    def test_continuity_commit_failure_rolls_back_metadata_without_pruning_pending(self):
        queue = self.enroll()
        self.stage(queue)
        self.identity["ino"] += 1
        preview = queue.review_source_change(str(self.path))
        def fail(operation, value):
            if operation == "exec" and value == "COMMIT":
                raise RuntimeError("synthetic source continuity failure")
        self.query_hook = fail
        self.assertEqual(queue.renew_source(preview.review), (None, "outbox_unavailable"))
        self.query_hook = None
        self.assertEqual(self.reopen().status().pending, 2)
        self.assertEqual(queue.check_source(str(self.path)), (None, "statistics_source_changed"))
        with statistics.closing(sqlite3.connect(self.owned)) as conn:
            self.assertEqual(conn.execute("SELECT inode FROM source").fetchone()[0], "11")


class EnrollmentLuaJITTest(EnrollmentTest):
    lua_type = statistics.LuaJITRuntime


@unittest.skipUnless(sys.platform == "linux", "Actual KOReader POSIX/SQLite SDK fixture requires Linux")
class NativeEnrollmentTest(EnrollmentTest):
    lua_type = statistics.LuaJITRuntime
    make_sdk = statistics.NativeStatisticsTest.make_sdk

    def test_actual_lfs_entropy_recovery_and_fresh_process_reopen(self):
        reference = Path(os.environ["READING_SQLITE_REFERENCE_DIR"])
        wire = Path(os.environ["READING_WIRE_REFERENCE_DIR"])
        sys.path.insert(0, str(collector.ROOT / "tools/reading_wire"))
        import prepare_reference_runtime
        prepare_reference_runtime.verify_reference(wire)
        before = self.path.read_bytes()
        contexts = []
        for mode in ("enroll", "reopen"):
            result = subprocess.run([str(reference / "luajit"),
                str(collector.ROOT / "tools/plugin/source_native_test.lua"), mode, str(self.root),
                str(self.path), str(reference), str(wire), str(collector.ROOT)],
                capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            contexts.append(json.loads(result.stdout))
        self.assertEqual(contexts[0], contexts[1])
        self.assertEqual(self.path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
