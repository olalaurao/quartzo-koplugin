"""Real synthetic SQLite fixtures; native SDK coverage is explicit Linux-only."""
import hashlib
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

from lupa.lua51 import LuaRuntime
from lupa.luajit21 import LuaRuntime as LuaJITRuntime

from prepare_sqlite_reference import verify

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = """
PRAGMA user_version=20221111;
CREATE TABLE book(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, authors TEXT,
 notes INTEGER, last_open INTEGER, highlights INTEGER, pages INTEGER, series TEXT,
 language TEXT, md5 TEXT, total_read_time INTEGER, total_read_pages INTEGER);
CREATE UNIQUE INDEX book_title_authors_md5 ON book(title,authors,md5);
CREATE TABLE page_stat_data(id_book INTEGER, page INTEGER NOT NULL DEFAULT 0,
 start_time INTEGER NOT NULL DEFAULT 0, duration INTEGER NOT NULL DEFAULT 0,
 total_pages INTEGER NOT NULL DEFAULT 0, UNIQUE(id_book,page,start_time),
 FOREIGN KEY(id_book) REFERENCES book(id));
CREATE INDEX page_stat_data_start_time ON page_stat_data(start_time);
"""


class StatisticsTest(unittest.TestCase):
    lua_type = LuaRuntime

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "statistics.sqlite3"
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.executescript(SCHEMA)
        self.lua = self.lua_type(unpack_returned_tuples=True)
        self.module = self.lua.execute((ROOT / "quartzo.koplugin/quartzo/statistics.lua").read_text())
        self.calls = []
        self.query_hook = None
        self.connections = []
        self.sdk = self.make_sdk()
        self.addCleanup(lambda: [c.close() for c in self.connections])

    def trace(self, operation, value=None):
        self.calls.append((operation, value))
        if self.query_hook:
            self.query_hook(operation, value)

    def make_sdk(self):
        # Exercise real SQLite through a test-only implementation of the SQ3 API.
        def open_db(path, mode):
            self.trace("open", mode)
            self.assertEqual(mode, "ro")
            conn = sqlite3.connect(Path(path).as_uri() + "?mode=ro", uri=True)
            self.connections.append(conn)
            cursors = []

            def rowexec(_, sql):
                self.trace("query", sql)
                with closing(conn.execute(sql)) as cursor:
                    row = cursor.fetchone()
                return row[0] if row else None

            def prepare(_, sql):
                self.trace("query", sql)
                cursor = None
                parameters = ()

                def bind(_, *values):
                    nonlocal parameters
                    parameters = values

                def step(_):
                    nonlocal cursor
                    if cursor is None:
                        cursor = conn.execute(sql, parameters)
                        cursors.append(cursor)
                    row = cursor.fetchone()
                    return self.lua.table_from(row) if row else None

                def close_statement(_):
                    if cursor is not None:
                        cursor.close()
                    if cursor in cursors:
                        cursors.remove(cursor)

                return self.lua.table(step=step, bind=bind, close=close_statement)

            def execute(_, sql):
                self.trace("exec", sql)
                with closing(conn.execute(sql)):
                    pass

            def busy(_, milliseconds):
                self.trace("busy", milliseconds)
                with closing(conn.execute("PRAGMA busy_timeout=" + str(milliseconds))):
                    pass

            def close(_):
                # Match actual SQ3: close any statement still open after errors.
                for cursor in cursors:
                    cursor.close()
                cursors.clear()
                conn.close()
                self.trace("close")

            return self.lua.table(rowexec=rowexec, prepare=prepare, exec=execute,
                                  set_busy_timeout=busy, close=close)

        return self.lua.table(open=open_db)

    def mutate(self, sql):
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.executescript(sql)

    def probe(self):
        before = hashlib.sha256(self.path.read_bytes()).digest()
        names = set(Path(self.temp.name).iterdir())
        result = self.module.probe(str(self.path), self.sdk)
        self.assertEqual(before, hashlib.sha256(self.path.read_bytes()).digest())
        self.assertEqual(set(Path(self.temp.name).iterdir()), names)
        return result

    def assert_closed_read_only(self):
        self.assertIn(("open", "ro"), self.calls)
        self.assertIn(("busy", 1000), self.calls)
        self.assertEqual(sum(c[0] == "open" for c in self.calls),
                         sum(c[0] == "close" for c in self.calls))
        self.assertEqual([value for op, value in self.calls if op == "exec"], ["BEGIN DEFERRED"])

    def test_empty_database_has_no_fake_dates_and_closes_read_only_snapshot(self):
        result = self.probe()
        self.assertEqual(result.schema_version, 20221111)
        self.assertEqual(result.book_count, 0)
        self.assertEqual(result.event_count, 0)
        self.assertIsNone(result.first_started_at)
        self.assertIsNone(result.last_started_at)
        self.assert_closed_read_only()

    def test_duplicate_md5_rows_and_extra_simpleui_index_are_preserved(self):
        self.mutate("""
        CREATE INDEX idx_simpleui_book_md5 ON book(md5);
        INSERT INTO book(title,authors,md5) VALUES('one','a','same'),('two','b','same');
        INSERT INTO page_stat_data VALUES(1,1,100,20,10),(2,1,200,30,20);
        """)
        result = self.probe()
        self.assertEqual((result.book_count, result.event_count), (2, 2))
        self.assertEqual((result.first_started_at, result.last_started_at), (100, 200))
        self.assert_closed_read_only()

    def test_unknown_version_fails_before_counting_and_closes(self):
        self.mutate("PRAGMA user_version=20270101")
        self.assertEqual(self.probe(), (None, "unsupported_statistics_schema"))
        self.assert_closed_read_only()
        self.assertFalse(any("COUNT" in str(value) for _, value in self.calls))

    def test_changed_columns_fail_closed_even_with_same_user_version(self):
        self.mutate("ALTER TABLE page_stat_data ADD COLUMN surprise TEXT")
        self.assertEqual(self.probe(), (None, "unsupported_statistics_schema"))
        self.assert_closed_read_only()

    def test_wrong_nonunique_or_partial_index_does_not_grant_schema_support(self):
        self.mutate("DROP INDEX book_title_authors_md5; CREATE INDEX book_title_authors_md5 ON book(title,authors,md5)")
        self.assertEqual(self.probe(), (None, "unsupported_statistics_schema"))
        self.assert_closed_read_only()

    def test_partial_time_index_cannot_hide_the_earliest_event(self):
        self.mutate("DROP INDEX page_stat_data_start_time; CREATE INDEX page_stat_data_start_time ON page_stat_data(start_time) WHERE start_time > 100")
        self.assertEqual(self.probe(), (None, "unsupported_statistics_schema"))
        self.assert_closed_read_only()

    def test_wal_writer_commits_while_the_probe_keeps_one_read_snapshot(self):
        writer = sqlite3.connect(self.path)
        self.addCleanup(writer.close)
        writer.execute("PRAGMA journal_mode=WAL")
        writer.executescript("INSERT INTO book(title) VALUES('one'); INSERT INTO page_stat_data VALUES(1,1,100,20,10);")

        def concurrent_write(operation, sql):
            if operation == "query" and sql.startswith("SELECT COUNT(*) FROM (SELECT 1 FROM book"):
                self.query_hook = None
                writer.executescript("INSERT INTO book(title) VALUES('two'); INSERT INTO page_stat_data VALUES(2,1,200,20,10);")

        self.query_hook = concurrent_write
        # An independent legitimate writer changes WAL bytes in this case.
        # Check snapshot/lock behavior rather than falsely asserting no changes.
        result = self.module.probe(str(self.path), self.sdk)
        self.assertEqual((result.book_count, result.event_count), (1, 1))
        self.assertEqual((result.first_started_at, result.last_started_at), (100, 100))
        self.assertEqual(writer.execute("SELECT COUNT(*) FROM page_stat_data").fetchone()[0], 2)
        self.assert_closed_read_only()

    def test_close_failure_suppresses_summary_and_private_sdk_error(self):
        failing = self.lua.execute('''
            local sdk = ...
            return {open = function(path, mode)
                local c = sdk.open(path, mode)
                return setmetatable({close = function()
                    c:close(); error("synthetic private close detail", 0)
                end}, {__index = function(_, method)
                    return function(_, ...) return c[method](c, ...) end
                end})
            end}
        ''', self.sdk)
        self.assertEqual(self.module.probe(str(self.path), failing), (None, "statistics_read_failed"))
        self.assert_closed_read_only()

    def test_cap_is_reported_without_loading_full_history(self):
        with closing(sqlite3.connect(self.path)) as conn, conn:
            conn.executemany("INSERT INTO page_stat_data VALUES(1,1,?,1,10)",
                             ((i,) for i in range(100001)))
        result = self.probe()
        self.assertEqual(result.event_count, 100000)
        self.assertTrue(result.event_count_limited)
        self.assertEqual((result.first_started_at, result.last_started_at), (0, 100000))
        self.assertTrue(any("LIMIT 100001" in str(value) for _, value in self.calls))
        self.assert_closed_read_only()

    def test_missing_database_is_not_created_and_errors_are_redacted(self):
        missing = Path(self.temp.name) / "private-secret-name.sqlite3"
        self.assertEqual(self.module.probe(str(missing), self.sdk), (None, "statistics_unavailable"))
        self.assertFalse(missing.exists())

    def test_corrupt_database_preserved_and_error_redacted(self):
        self.path.write_bytes(b"synthetic corrupt database; private marker")
        self.assertEqual(self.probe(), (None, "statistics_unavailable"))
        self.assert_closed_read_only()

    def test_exclusive_writer_is_bounded_busy_and_no_retry_or_write(self):
        # POSIX locks belong to the process. Python's SQLite and the independent
        # KOReader library in one PID cannot model a competing process lock.
        marker = Path(self.temp.name) / "writer-ready"
        script = '''
import sqlite3, sys
from pathlib import Path
c = sqlite3.connect(sys.argv[1])
c.execute("BEGIN EXCLUSIVE")
Path(sys.argv[2]).write_text("locked")
sys.stdin.readline()
c.rollback()
c.close()
'''
        with subprocess.Popen([sys.executable, "-c", script, str(self.path), str(marker)],
                              stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL, text=True) as writer:
            try:
                deadline = time.monotonic() + 5
                while not marker.exists() and writer.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertTrue(marker.exists(), "Synthetic writer did not acquire its lock")
                start = time.monotonic()
                self.assertEqual(self.probe(), (None, "statistics_busy"))
                self.assertLess(time.monotonic() - start, 3)
                self.assert_closed_read_only()
            finally:
                try:
                    writer.communicate("release\n", timeout=5)
                except subprocess.TimeoutExpired:
                    writer.kill()  # Only this test's owned child process.
                    writer.communicate(timeout=5)

    def test_real_read_only_connection_rejects_a_write_to_synthetic_fixture(self):
        before = self.path.read_bytes()
        conn = self.sdk.open(str(self.path), "ro")
        try:
            with self.assertRaises(Exception) as raised:
                conn.exec(conn, "PRAGMA user_version=1")
            self.assertIn("readonly", str(raised.exception).lower())
        finally:
            conn.close(conn)
        self.assertEqual(before, self.path.read_bytes())


class StatisticsLuaJITTest(StatisticsTest):
    lua_type = LuaJITRuntime


@unittest.skipUnless(sys.platform == "linux", "Actual KOReader POSIX/SQLite SDK fixture requires Linux")
class NativeStatisticsTest(StatisticsTest):
    lua_type = LuaJITRuntime

    def make_sdk(self):
        directory = Path(os.environ["READING_SQLITE_REFERENCE_DIR"])
        verify(directory)  # Missing/mismatched native references fail, never skip.
        return self.lua.execute('''
            local root, trace = ...
            bit = require("bit")
            local ffi = require("ffi")
            ffi.loadlib = function(name, version)
                assert(name == "sqlite3" and version == "0")
                return ffi.load(root .. "/libs/libsqlite3.so.0")
            end
            package.path = root .. "/?.lua;" .. package.path
            local native = dofile(root .. "/common/lua-ljsqlite3/init.lua")
            return {open = function(path, mode)
                trace("open", mode)
                local c = native.open(path, mode)
                return {
                    set_busy_timeout = function(_, ms) trace("busy", ms); return c:set_busy_timeout(ms) end,
                    exec = function(_, sql) trace("exec", sql); return c:exec(sql) end,
                    rowexec = function(_, sql) trace("query", sql); return c:rowexec(sql) end,
                    prepare = function(_, sql) trace("query", sql); return c:prepare(sql) end,
                    close = function() c:close(); trace("close") end,
                }
            end}
        ''', str(directory), self.trace)


if __name__ == "__main__":
    unittest.main()
