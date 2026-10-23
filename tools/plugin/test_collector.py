"""Bounded extraction over real synthetic SQLite; no private/device data."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

from lupa.lua51 import LuaRuntime
from lupa.luajit21 import LuaRuntime as LuaJITRuntime
import test_statistics as statistics

ROOT = Path(__file__).resolve().parents[2]
OBSERVED = "2026-10-16T12:00:00.000Z"


class CollectorTest(unittest.TestCase):
    lua_type = LuaRuntime
    make_sdk = statistics.StatisticsTest.make_sdk
    trace = statistics.StatisticsTest.trace
    mutate = statistics.StatisticsTest.mutate
    assert_closed_read_only = statistics.StatisticsTest.assert_closed_read_only

    def setUp(self):
        statistics.StatisticsTest.setUp(self)
        self.lua.globals().package.loaded["quartzo/statistics"] = self.module
        self.collector = self.lua.execute((ROOT / "quartzo.koplugin/quartzo/collector.lua").read_text())
        self.null = self.lua.table()
        self.lua.globals().collector_null = self.null
        kind = self.lua.eval("function(v) if v==collector_null then return 'null' end; "
                             "if type(v)=='table' then local m=getmetatable(v); return m and m.wire_kind end; return type(v) end")
        mark = self.lua.eval("function(t,k) return setmetatable(t,{wire_kind=k}) end")

        def convert(value):
            if value is None:
                return self.null
            if isinstance(value, dict):
                return mark(self.lua.table_from({k: convert(v) for k, v in value.items()}), "object")
            if isinstance(value, list):
                return mark(self.lua.table_from([convert(v) for v in value]), "array")
            return value

        wrap = self.lua.eval("function(f) return function(...) return f(...) end end")
        deps = self.lua.table(sha256=wrap(lambda b: hashlib.sha256(b.encode()).hexdigest()),
                              decode_json=wrap(lambda b: convert(json.loads(b))), kind=kind, null=self.null)
        deps.object=self.lua.eval("function(t) return setmetatable(t,{wire_kind='object'}) end")
        self.to_lua,self.codec_dependencies=convert,deps
        self.codec = self.lua.execute((ROOT / "quartzo.koplugin/quartzo/codec.lua").read_text()).new(deps)

    def collect(self, **options):
        fields = dict(device_id="qrd_fixture", source_epoch="db_epoch_fixture",
                      observed_at_utc=OBSERVED, **options)
        before = self.path.read_bytes()
        result = self.collector.collect(str(self.path), self.lua.table_from(fields), self.codec, self.sdk)
        self.assertEqual(before, self.path.read_bytes())
        return result

    def lines(self, batch):
        return [batch.event_lines[i] for i in range(1, len(batch.event_lines)+1)]

    def fixture(self):
        self.mutate("""
        INSERT INTO book(id,title,authors,md5) VALUES
          (17,'one','a','0123456789abcdef0123456789abcdef'),
          (18,'different','b','0123456789ABCDEF0123456789ABCDEF');
        INSERT INTO page_stat_data VALUES(17,4,1791946200,1800,120),
          (18,4,1791946200,20,100),(17,4,1791946201,10,140);
        """)

    def test_exact_upstream_native_identity_and_canonical_line(self):
        self.fixture()
        batch = self.collect()
        event = json.loads(batch.event_lines[1])
        vector = json.loads((ROOT / "tools/reading_wire/upstream/vectors.json").read_text())
        event_id = vector["event"]["event_id"]
        self.assertEqual(event["event_id"], event_id)
        # Reference expected bytes are independently constructed by the ratified
        # Dart/Python contract, with only the observed actual schema substituted.
        expected = dict(schema_version=1, event_id=event_id, source="koreader_statistics",
                        device_id="qrd_fixture", source_epoch="db_epoch_fixture", book_row_id=17,
                        page=4, started_at_utc="2026-10-14T02:50:00.000Z", duration_seconds=1800,
                        total_pages=120, observed_at_utc=OBSERVED, source_schema_version="20221111")
        self.assertEqual(batch.event_lines[1], json.dumps(expected, ensure_ascii=False, separators=(",", ":")))
        self.assert_closed_read_only()

    def test_replay_title_changes_and_md5_group_never_collapse_native_rows(self):
        self.fixture()
        first = self.collect()
        self.assertEqual(self.lines(first), self.lines(self.collect()))
        self.mutate("UPDATE book SET title='renamed',authors='new author' WHERE id=17")
        self.assertEqual(self.lines(first), self.lines(self.collect()))
        self.assertEqual(len({json.loads(line)["event_id"] for line in self.lines(first)}), 3)
        ids = first.md5_groups["0123456789abcdef0123456789abcdef"]
        self.assertEqual(list(ids.values()), [17, 18])
        self.assertNotIn("renamed", "".join(self.lines(first)))

    def test_same_second_larger_than_batch_makes_progress_and_matches_unsplit(self):
        self.mutate("INSERT INTO book(id,md5) VALUES(1,'0123456789abcdef0123456789abcdef')")
        with statistics.closing(statistics.sqlite3.connect(self.path)) as conn, conn:
            conn.executemany("INSERT INTO page_stat_data VALUES(1,?,1791946200,20,500)",
                             ((page,) for page in range(1, 251)))
        all_lines, after, sizes = [], None, []
        for _ in range(10):
            batch = self.collect(limit=37, after=after)
            sizes.append(len(batch.event_lines))
            all_lines.extend(self.lines(batch))
            if batch.complete:
                break
            after = batch.next_scan
        self.assertEqual(sizes, [37]*6+[28])
        self.assertEqual(len({json.loads(line)["event_id"] for line in all_lines}), 250)
        expected_ids = {"qre_" + hashlib.sha256(json.dumps(
            ["quartzo-reading-event-v1", "qrd_fixture", "db_epoch_fixture", 1, page, 1791946200],
            separators=(",", ":")).encode()).hexdigest() for page in range(1, 251)}
        self.assertEqual({json.loads(line)["event_id"] for line in all_lines}, expected_ids)
        self.assertFalse(batch.canonical_ack)
        self.assertIsNone(batch.acknowledged_watermark)

    def test_time_overlap_replays_only_existing_ids_after_simulated_ack(self):
        self.fixture()
        first = self.collect()
        original = {json.loads(line)["event_id"] for line in self.lines(first)}
        overlap = self.collect(from_started_at=1791946200)  # last second minus one.
        self.assertEqual(original, {json.loads(line)["event_id"] for line in self.lines(overlap)})
        empty = self.collect(from_started_at=1791946202)
        self.assertTrue(empty.complete)
        self.assertEqual(self.lines(empty), [])
        self.assertIsNone(empty.next_scan)
        self.assertFalse(empty.canonical_ack)

    def test_changed_duration_conflicts_by_same_id_and_reflow_keeps_raw_pages(self):
        self.fixture()
        before = [json.loads(line) for line in self.lines(self.collect())]
        self.mutate("UPDATE page_stat_data SET duration=21,total_pages=150 WHERE id_book=18")
        after = [json.loads(line) for line in self.lines(self.collect())]
        self.assertEqual(before[1]["event_id"], after[1]["event_id"])
        self.assertNotEqual(before[1], after[1])
        self.assertEqual([item["total_pages"] for item in after], [120, 150, 140])

    def test_device_and_epoch_are_explicit_scopes(self):
        self.fixture()
        first = json.loads(self.collect().event_lines[1])["event_id"]
        for name in ("device_id", "source_epoch"):
            fields = dict(device_id="qrd_fixture", source_epoch="db_epoch_fixture", observed_at_utc=OBSERVED)
            fields[name] = "other_scope"
            result = self.collector.collect(str(self.path), self.lua.table_from(fields), self.codec, self.sdk)
            self.assertNotEqual(first, json.loads(result.event_lines[1])["event_id"])

    def test_missing_book_missing_md5_and_blank_metadata_preserve_history(self):
        self.mutate("""INSERT INTO book(id,title,authors,md5) VALUES(1,'','',''),(2,NULL,NULL,NULL);
        INSERT INTO page_stat_data VALUES(1,1,100,20,10),(2,1,101,20,10),(3,1,102,20,10);""")
        batch = self.collect()
        self.assertEqual(len(batch.event_lines), 3)
        self.assertEqual(len(batch.md5_groups), 0)
        self.assertFalse(batch.books[1].missing_book)
        self.assertTrue(batch.books[3].missing_book)
        self.assertTrue(all(batch.books[i].md5 is None for i in range(1, 4)))

    def test_invalid_rows_remain_pending_review_without_canonical_acceptance(self):
        for field, value in (("duration", "0"), ("duration", "86401"), ("duration", "'private'"),
                             ("page", "-1"), ("total_pages", "0"), ("id_book", "NULL"),
                             ("start_time", "253402300800"), ("duration", "1.5")):
            with self.subTest(field=field, value=value):
                self.mutate("DELETE FROM page_stat_data; INSERT INTO page_stat_data VALUES(1,1,100,20,10);")
                self.mutate(f"UPDATE page_stat_data SET {field}={value}")
                result = self.collect()
                self.assertEqual((len(result.event_lines), len(result.rejections), result.scanned_count), (0, 1, 1))
                self.assertEqual(result.rejections[1].reason, "invalid_statistics_event")
                self.assertFalse(result.canonical_ack)
                self.assertIsNone(result.acknowledged_watermark)
                self.assertIsNotNone(result.next_scan)

    def test_page_zero_review_preserves_raw_integer_and_does_not_block_valid_neighbors(self):
        self.mutate("""INSERT INTO page_stat_data VALUES(1,0,100,20,10),
          (1,1,100,20,10),(1,2,101,20,10);""")
        first = self.collect(limit=1)
        self.assertEqual((len(first.event_lines), len(first.rejections)), (0, 1))
        self.assertEqual(first.rejections[1].integer_fields.page, "0")
        self.assertFalse(first.complete)
        second = self.collect(limit=2, after=first.next_scan)
        self.assertTrue(second.complete)
        self.assertEqual((len(second.event_lines), len(second.rejections)), (2, 0))
        self.assertFalse(second.canonical_ack)

    def test_corrupt_large_text_is_not_copied_and_int64_rejection_is_lossless(self):
        self.mutate("""INSERT INTO page_stat_data VALUES(1,1,100,20,10),(1,1,101,20,10);
          UPDATE page_stat_data SET duration=CAST(zeroblob(1048576) AS TEXT) WHERE start_time=100;
          UPDATE page_stat_data SET duration=9223372036854775807 WHERE start_time=101;""")
        result = self.collect()
        self.assertEqual(len(result.rejections), 2)
        self.assertEqual(result.rejections[1].field_types[4], "text")
        self.assertIsNone(result.rejections[1].integer_fields.duration_seconds)
        self.assertEqual(result.rejections[2].integer_fields.duration_seconds, "9223372036854775807")

    def test_unrepresentable_scan_key_blocks_without_an_unsafe_continuation(self):
        for value in ("'private source text'", "9223372036854775807"):
            self.mutate("DELETE FROM page_stat_data; INSERT INTO page_stat_data VALUES(1,1,100,20,10)")
            self.mutate("UPDATE page_stat_data SET start_time=" + value)
            self.assertEqual(self.collect(), (None, "invalid_statistics_event"))

    def test_invalid_context_scan_and_limits_are_rejected(self):
        self.fixture()
        for options in (dict(limit=0), dict(limit=101), dict(limit=1.5),
                        dict(after=self.lua.table(started_at=100,row_id=1)),
                        dict(from_started_at="100")):
            self.assertEqual(self.collect(**options), (None, "invalid_statistics_collection"))
        fields = dict(device_id="qrd_fixture", source_epoch="db_epoch_fixture", observed_at_utc="invalid")
        result = self.collector.collect(str(self.path), self.lua.table_from(fields), self.codec, self.sdk)
        self.assertEqual(result, (None, "invalid_statistics_event"))

    def test_book_enumeration_is_bounded_including_rows_without_events(self):
        self.fixture()
        self.mutate("INSERT INTO book(id,md5) VALUES(30,'not-a-digest')")
        first = self.collector.books(str(self.path), self.lua.table(limit=1), self.sdk)
        self.assertEqual(first.books[1].book_row_id, 17)
        self.assertFalse(first.complete)
        second = self.collector.books(str(self.path), self.lua.table(limit=2,after_book_row_id=17), self.sdk)
        self.assertEqual([item.book_row_id for item in second.books.values()], [18, 30])
        self.assertTrue(second.complete)
        self.assertIsNone(second.books[2].md5)

    def test_schema_error_never_returns_collected_events(self):
        self.mutate("PRAGMA user_version=42")
        self.assertEqual(self.collect(), (None, "unsupported_statistics_schema"))
        self.assert_closed_read_only()

    def test_missing_statistics_does_not_create_or_enable_a_database(self):
        self.path.unlink()  # Owned synthetic fixture only; never a device path.
        result = self.collector.collect(str(self.path), self.lua.table(
            device_id="qrd_fixture", source_epoch="db_epoch_fixture", observed_at_utc=OBSERVED), self.codec, self.sdk)
        self.assertEqual(result, (None, "statistics_unavailable"))
        self.assertFalse(self.path.exists())

    def test_module_load_has_no_database_or_statistics_settings_access(self):
        self.assertEqual(self.calls, [])
        self.assertIsNone(self.collector.enabled)

    def test_close_error_discards_collected_events_and_sanitizes_private_detail(self):
        self.fixture()
        self.sdk = self.lua.execute('''local sdk = ...
            return {open=function(path, mode)
                local c=sdk.open(path,mode)
                return setmetatable({close=function()
                    c:close(); error('private source path',0)
                end}, {__index=function(_,name)
                    return function(_,...) return c[name](c,...) end
                end})
            end}
        ''', self.sdk)
        self.assertEqual(self.collect(), (None, "statistics_read_failed"))
        self.assert_closed_read_only()

    def test_wal_concurrent_insert_is_observed_only_by_the_next_snapshot(self):
        self.fixture()
        writer = statistics.sqlite3.connect(self.path)
        self.addCleanup(writer.close)
        writer.execute("PRAGMA journal_mode=WAL")

        def concurrent_write(operation, sql):
            if operation == "query" and sql.startswith("SELECT rowid"):
                self.query_hook = None
                writer.executescript("INSERT INTO page_stat_data VALUES(17,8,1791946202,10,150)")

        self.query_hook = concurrent_write
        # Legitimate Statistics-side write: bytes need not remain identical.
        batch = self.collector.collect(str(self.path), self.lua.table(
            device_id="qrd_fixture", source_epoch="db_epoch_fixture", observed_at_utc=OBSERVED), self.codec, self.sdk)
        self.assertEqual(len(batch.event_lines), 3)
        later = self.collect()
        self.assertEqual(len(later.event_lines), 4)

    def test_utc_conversion_is_independent_of_host_zone_and_32bit_time_t(self):
        self.mutate("""INSERT INTO page_stat_data VALUES(1,1,-62135596800,1,10),
          (1,1,0,1,10),(1,1,2147483648,1,10),(1,1,253402300799,1,10);""")
        starts = [json.loads(line)["started_at_utc"] for line in self.lines(self.collect())]
        self.assertEqual(starts, ["0001-01-01T00:00:00.000Z", "1970-01-01T00:00:00.000Z",
                                  "2038-01-19T03:14:08.000Z", "9999-12-31T23:59:59.000Z"])

    def test_time_index_keyset_has_no_sort_or_history_materialization(self):
        self.fixture()
        first = self.collect(limit=1)
        self.calls.clear()
        self.collect(limit=1, after=first.next_scan)
        query = next(sql for op, sql in self.calls if op == "query" and sql.startswith("SELECT rowid"))
        with statistics.closing(statistics.sqlite3.connect(self.path)) as conn:
            plan = conn.execute("EXPLAIN QUERY PLAN " + query,
                                (first.next_scan.started_at, first.next_scan.row_id, 2)).fetchall()
        self.assertIn("page_stat_data_start_time", str(plan))
        self.assertIn("SEARCH", str(plan))
        self.assertNotIn("TEMP B-TREE", str(plan))
        self.assertNotIn("OFFSET", query)

    def test_large_equal_second_resume_uses_bounded_sql_work(self):
        with statistics.closing(statistics.sqlite3.connect(self.path)) as conn, conn:
            conn.executemany("INSERT INTO page_stat_data VALUES(1,?,100,20,10000)",
                             ((page,) for page in range(1, 10001)))
        after = self.lua.table(device_id="qrd_fixture", source_epoch="db_epoch_fixture",
                               started_at=100, row_id=9990)
        result = self.collect(limit=10, after=after)
        self.assertEqual(len(result.event_lines), 10)
        self.assertTrue(result.complete)
        queries = [sql for op, sql in self.calls if op == "query" and sql.startswith("SELECT rowid")]
        self.assertEqual(len(queries), 2)
        steps = [0]

        def progress():
            steps[0] += 1
            return 0

        with statistics.closing(statistics.sqlite3.connect(self.path)) as conn:
            conn.set_progress_handler(progress, 1)
            rows = conn.execute(queries[0], (100, 9990, 11)).fetchall()
            later = conn.execute(queries[1], (100, 1)).fetchall()
        self.assertEqual((len(rows), later), (10, []))
        self.assertLess(steps[0], 1500)


class CollectorLuaJITTest(CollectorTest):
    lua_type = LuaJITRuntime


@unittest.skipUnless(sys.platform == "linux", "Actual KOReader POSIX/SQLite SDK fixture requires Linux")
class NativeCollectorTest(CollectorTest):
    lua_type = LuaJITRuntime
    make_sdk = statistics.NativeStatisticsTest.make_sdk


if __name__ == "__main__":
    unittest.main()
