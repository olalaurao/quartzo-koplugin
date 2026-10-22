"""Synthetic mount/SQL adversaries; these fixtures cannot attest a Kindle."""
import copy
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest import mock

import outbox_probe_bundle as bundle


class OutboxProbeBundleTest(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix="quartzo-outbox-bundle-fixture-")
        self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name).resolve()
        self.output=self.root/"bundle"
        values={name:(bundle.base.ROOT/source).read_bytes().replace(b"\r\n",b"\n")
                for name,source in bundle.SOURCES.items()}
        values["run.sh"]=values["run.sh"].replace(b"quartzo-transport-probe",bundle.NAME.encode())
        patch=mock.patch.object(bundle.base,"read_sources",return_value=values)
        patch.start()
        self.addCleanup(patch.stop)
        self.manifest=bundle.base.prepare(self.output,"b"*40,bundle.DEFINITION)
        self.mount=self.root/"mount"
        (self.mount/"extensions").mkdir(parents=True)
        for key,relative in bundle.NATIVE.items():
            path=self.mount/"koreader"/relative
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(("synthetic native "+key).encode())
        (self.mount/"koreader/git-rev").write_bytes(b"v2026.07.1\n")
        self.sentinel=self.mount/"koreader/statistics.sqlite3"
        self.sentinel.write_bytes(b"preserve unrelated fixture")
        self.observation=self.root/"installed.json"
        self.installed=bundle.base.install(self.output,self.mount,bundle.DEFINITION)
        self.observation.write_bytes(bundle.base.encoded(self.installed))
        self.target=self.mount/"extensions"/bundle.NAME

    def completed(self):
        (self.target/"run.lock").mkdir()
        (self.target/"launcher-status.txt").write_bytes(b"completed\n")
        self.report=dict(probe_version=1,phase="passed",source_data="synthetic",uses_synthetic_clock=True,
            case_checks=dict.fromkeys(bundle.CASES,True),process_stop_cases=6,raw_receipt_rejections=5,
            native_entropy_cases=6,identity_and_pending_verified=True,run_id=self.manifest["run_id"],
            manifest_digest=self.installed["manifest_digest"],source_commit="b"*40,
            lua_version="Lua 5.1",jit_version="LuaJIT 2.1.0-beta3",jit_arch="arm",koreader_version=bundle.base.BASELINE,
            native_source_sha256=self.installed["native_source_sha256"],json_version="dkjson 2.10",cpu_seconds=0.1)
        self.report.update(dict.fromkeys(bundle.FALSE_FIELDS,False))
        self.report_path=self.target/"device-observation.json"
        self.report_path.write_bytes(bundle.base.encoded(self.report))
        for index,name in enumerate(sorted(bundle.CASES)):
            directory=self.target/"state"/name
            directory.mkdir(parents=True)
            (directory/"gate.ready").write_bytes(b"ready")
            device="qrd_"+format(index,"032x")
            self.database(directory/bundle.PRIMARY,device,name=="restore_before_commit",name!="stage_before_commit")
            if name.startswith(("backup_","restore_")):
                self.database(directory/("quartzo_sync_recovery_"+"c"*32+".sqlite3"),
                              device,name=="backup_before_commit",True)
            if name.startswith("restore_"):
                self.database(directory/bundle.PRESERVED,device,False,True)

    def database(self,path,device,partial,pending):
        conn=sqlite3.connect(path)
        try:
            if partial:
                # Materialized empty database, matching native rollback recovery.
                conn.execute("PRAGMA user_version=0")
                return
            conn.executescript("""PRAGMA user_version=1;
                CREATE TABLE identity(id INTEGER PRIMARY KEY CHECK(id=1),device_id TEXT NOT NULL,source_epoch TEXT NOT NULL);
                CREATE TABLE pending(event_id TEXT PRIMARY KEY,line TEXT NOT NULL,native_digest TEXT NOT NULL);
                CREATE TABLE review(started_at INTEGER NOT NULL,book_id TEXT NOT NULL,page TEXT NOT NULL,
                    duration TEXT NOT NULL,pages TEXT NOT NULL,types TEXT NOT NULL,
                    PRIMARY KEY(started_at,book_id,page,duration,pages,types));""")
            epoch="probe_"+self.manifest["run_id"]
            conn.execute("INSERT INTO identity VALUES(1,?,?)",(device,epoch))
            if pending:
                conn.executemany("INSERT INTO pending VALUES(?,?,?)",bundle.fixture_rows(device,epoch))
                conn.execute("INSERT INTO review VALUES(?,?,?,?,?,?)",(1791946202,"17","0","10","120","integer,integer,integer,integer,integer"))
            conn.commit()
        finally:
            conn.close()

    def collect(self):
        return bundle.collect(self.output,self.mount,self.observation)

    def test_matching_reports_and_independent_sql_still_cannot_attest_hardware_or_gate(self):
        self.completed()
        report=self.collect()
        self.assertTrue(report["observations_match"])
        for name in ("physical_execution_attested","canonical_ack","canonical_persistence_proven",
                     "paired_receipt_proven","source_epoch_verified","gate4_passed","production_changed"):
            self.assertIs(report[name],False)
        self.assertEqual(len(report["synthetic_state_sha256"]),12)
        self.assertEqual(self.sentinel.read_bytes(),b"preserve unrelated fixture")

    def test_forged_report_fields_counts_and_claims_are_refused(self):
        self.completed()
        for change in ({"canonical_ack":True},{"gate4_passed":True},{"source_epoch_verified":True},
                       {"raw_receipt_rejections":4},{"process_stop_cases":6.0},{"native_entropy_cases":5},
                       {"jit_arch":"x64"},{"cpu_seconds":float("nan")},{"private_extra":"sentinel"},
                       {"case_checks":dict.fromkeys(bundle.CASES,1)}):
            with self.subTest(change=change):
                self.report_path.write_bytes(bundle.base.encoded({**copy.deepcopy(self.report),**change}))
                with self.assertRaises(ValueError): self.collect()

    def test_only_two_expected_unregistered_partials_may_be_zero_bytes(self):
        self.completed()
        for name in ("backup_before_commit","restore_before_commit"):
            directory=self.target/"state"/name
            leaf=("quartzo_sync_recovery_"+"c"*32+".sqlite3") if name.startswith("backup_") else bundle.PRIMARY
            (directory/leaf).write_bytes(b"")
        self.assertTrue(self.collect()["observations_match"])
        (self.target/"state/stage_after_commit"/bundle.PRIMARY).write_bytes(b"")
        with self.assertRaises(ValueError): self.collect()

    def test_unknown_directory_and_journal_are_refused(self):
        self.completed()
        directory=self.target/"state/stage_before_commit"
        for leaf in ("unexpected","quartzo_sync_state.sqlite3-journal"):
            path=directory/leaf
            path.write_bytes(b"unexpected fixture")
            with self.assertRaises(ValueError): self.collect()
            path.unlink()  # Only this just-created file inside TemporaryDirectory.
        path=directory/"nested"
        path.mkdir()
        with self.assertRaises(ValueError): self.collect()

    def test_tampered_native_lines_schema_review_and_identity_are_refused(self):
        self.completed()
        path=self.target/"state/stage_after_commit"/bundle.PRIMARY
        original=path.read_bytes()
        for sql in ("UPDATE pending SET line='{}'", "DELETE FROM review", "UPDATE identity SET source_epoch='other'",
                    "CREATE TABLE unexpected(value TEXT)", "PRAGMA user_version=99", "DELETE FROM pending"):
            path.write_bytes(original)
            with closing(sqlite3.connect(path)) as conn,conn:
                conn.execute(sql)
            with self.subTest(sql=sql),self.assertRaises(ValueError): self.collect()

    def test_install_never_replaces_and_missing_native_rejects_before_copy(self):
        with self.assertRaises(ValueError): bundle.base.install(self.output,self.mount,bundle.DEFINITION)
        self.assertFalse((self.target/"state").exists())
        self.assertEqual(self.sentinel.read_bytes(),b"preserve unrelated fixture")
        # A fresh separate synthetic target, missing one required native library.
        mount=self.root/"missing-native"
        (mount/"extensions").mkdir(parents=True)
        (mount/"koreader").mkdir()
        (mount/"koreader/common").mkdir()
        (mount/"koreader/git-rev").write_bytes(b"v2026.07.1\n")
        (mount/"koreader/luajit").write_bytes(b"fixture")
        with self.assertRaises(ValueError): bundle.base.install(self.output,mount,bundle.DEFINITION)
        self.assertFalse((mount/"extensions"/bundle.NAME).exists())


if __name__=="__main__": unittest.main()
