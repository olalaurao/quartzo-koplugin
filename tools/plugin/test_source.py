"""Explicit source reviews and conservative native continuity; no device claim."""
import sys
import unittest

import test_statistics as statistics


class SourceTest(unittest.TestCase):
    lua_type = statistics.LuaRuntime
    make_sdk = statistics.StatisticsTest.make_sdk
    trace = statistics.StatisticsTest.trace
    mutate = statistics.StatisticsTest.mutate

    def setUp(self):
        statistics.StatisticsTest.setUp(self)
        self.identity = dict(mode="file", dev=7, ino=11)
        wrap = self.lua.eval("function(f) return function(...) return f(...) end end")
        self.runtime = self.lua.table(sqlite=self.sdk,
            attributes=wrap(lambda path: self.lua.table_from(self.identity)))

    def seed(self):
        self.mutate("""INSERT INTO book(title,md5) VALUES('private title','private-md5');
            INSERT INTO page_stat_data VALUES(1,1,100,20,10),(1,2,110,30,10);""")

    def review(self):
        result = self.module.review_source(str(self.path), self.runtime)
        self.assertNotIsInstance(result, tuple)
        return result

    def checkpoint(self):
        review = self.review()
        checkpoint = self.module.accept_source_review(review.review, self.lua.eval("function(value) return value end"))
        self.assertNotIsInstance(checkpoint, tuple)
        return checkpoint

    def check(self, checkpoint):
        return self.module.with_source_snapshot(str(self.path), checkpoint, self.runtime,
                                                self.lua.eval("function(conn) return {matches=true} end"))

    def test_empty_explicit_review_is_read_only_one_use_and_has_no_fake_history(self):
        before = self.path.read_bytes()
        review = self.review()
        self.assertFalse(review.has_history)
        self.assertIsNone(review.history_boundary)
        # A boolean or copied/public review summary cannot enroll a source.
        for forged in (True, self.lua.table(), review):
            self.assertEqual(self.module.accept_source_review(forged, self.lua.eval("function(value) return value end")),
                             (None, "statistics_source_review_required"))
        checkpoint = self.module.accept_source_review(review.review, self.lua.eval("function(value) return value end"))
        self.assertEqual(dict(checkpoint.items()), dict(volume="7", inode="11", book_sequence="0",
                         first_event="", last_event="", history_boundary=""))
        self.assertEqual(self.module.accept_source_review(review.review, self.lua.eval("function(value) return value end")),
                         (None, "statistics_source_review_required"))
        self.assertEqual(before, self.path.read_bytes())
        self.assertTrue(all(mode == "ro" for operation, mode in self.calls if operation == "open"))

    def test_review_cannot_be_confirmed_after_history_or_native_file_changes(self):
        self.seed()
        review = self.review()
        self.mutate("INSERT INTO page_stat_data VALUES(1,3,120,30,10)")
        self.assertEqual(self.module.accept_source_review(review.review, self.lua.eval("function(value) return value end")),
                         (None, "statistics_source_changed"))
        review = self.review()
        self.identity["ino"] += 1
        self.assertEqual(self.module.accept_source_review(review.review, self.lua.eval("function(value) return value end")),
                         (None, "statistics_source_changed"))

    def test_enrolled_guards_accept_growth_and_title_changes_without_using_them_as_identity(self):
        self.seed()
        checkpoint = self.checkpoint()
        self.mutate("""UPDATE book SET title='changed title';
            INSERT INTO book(title) VALUES('second');
            INSERT INTO page_stat_data VALUES(2,1,200,40,20);""")
        before = self.path.read_bytes()
        self.assertTrue(self.check(checkpoint).matches)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(checkpoint.history_boundary, "110")  # Never a moving ACK watermark.
        source_queries = [value for operation, value in self.calls if operation == "query" and "SELECT" in value]
        self.assertFalse(any("SELECT title" in value or "SELECT md5" in value for value in source_queries))

    def test_deletion_payload_change_sequence_reset_or_replacement_require_review(self):
        self.seed()
        checkpoint = self.checkpoint()
        for change, repair in (
            ("DELETE FROM page_stat_data WHERE page=1", "INSERT INTO page_stat_data VALUES(1,1,100,20,10)"),
            ("UPDATE page_stat_data SET duration=21 WHERE page=1", "UPDATE page_stat_data SET duration=20 WHERE page=1"),
            ("UPDATE sqlite_sequence SET seq=0 WHERE name='book'", "UPDATE sqlite_sequence SET seq=1 WHERE name='book'"),
        ):
            self.mutate(change)
            self.assertEqual(self.check(checkpoint), (None, "statistics_source_changed"))
            self.mutate(repair)
            self.assertTrue(self.check(checkpoint).matches)
        self.identity["ino"] += 1
        self.assertEqual(self.check(checkpoint), (None, "statistics_source_changed"))

    def test_native_file_replaced_during_snapshot_suppresses_callback_result(self):
        self.seed()
        checkpoint = self.checkpoint()
        def replaced(operation, value):
            if operation == "close":
                self.identity["ino"] += 1
        self.query_hook = replaced
        self.assertEqual(self.check(checkpoint), (None, "statistics_source_changed"))

    def test_missing_native_identity_links_and_provider_errors_cannot_mint_review(self):
        for identity in (dict(mode="file"), dict(mode="link", dev=7, ino=11),
                         dict(mode="file", dev=7, ino=0), dict(mode="file", dev=7, ino=2**54)):
            self.identity = identity
            self.assertEqual(self.module.review_source(str(self.path), self.runtime),
                             (None, "statistics_source_unverifiable"))
        self.runtime.attributes = self.lua.eval("function() error('private file path') end")
        self.assertEqual(self.module.review_source(str(self.path), self.runtime),
                         (None, "statistics_source_unverifiable"))

    def test_checkpoint_fields_are_bounded_canonical_and_copied(self):
        self.seed()
        checkpoint = self.checkpoint()
        checked = self.module.validate_source_checkpoint(checkpoint)
        checked.volume = "9"
        self.assertEqual(checkpoint.volume, "7")
        for key, value in (("volume", "07"), ("inode", "0"), ("first_event", "1,1,100,20,10,1"),
                           ("last_event", ""), ("history_boundary", "99"), ("extra", "private")):
            invalid = self.lua.table_from(dict(checkpoint.items()))
            invalid[key] = value
            self.assertEqual(self.module.validate_source_checkpoint(invalid),
                             (None, "statistics_source_unverifiable"))

    def test_malformed_anchor_fails_closed_without_copying_private_text(self):
        self.seed()
        self.mutate("UPDATE page_stat_data SET duration='private corrupt contents' WHERE page=1")
        self.assertEqual(self.module.review_source(str(self.path), self.runtime),
                         (None, "statistics_source_unverifiable"))

    def test_empty_history_cannot_establish_continuity_after_file_replacement(self):
        checkpoint = self.checkpoint()
        self.identity["ino"] += 1
        self.assertEqual(self.module.review_source(str(self.path), self.runtime, checkpoint),
                         (None, "statistics_source_unverifiable"))


class SourceLuaJITTest(SourceTest):
    lua_type = statistics.LuaJITRuntime


@unittest.skipUnless(sys.platform == "linux", "Actual KOReader POSIX/SQLite SDK fixture requires Linux")
class NativeSourceTest(SourceTest):
    lua_type = statistics.LuaJITRuntime
    make_sdk = statistics.NativeStatisticsTest.make_sdk


if __name__ == "__main__":
    unittest.main()
