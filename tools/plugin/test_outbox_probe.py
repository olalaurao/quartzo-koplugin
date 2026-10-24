"""Six actual process stops in standalone official Linux LuaJIT, not device proof."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import prepare_sqlite_reference
import outbox_probe_bundle

ROOT = Path(__file__).resolve().parents[2]
CASES = {f"{operation}_{position}_commit" for operation in ("stage", "backup", "restore")
         for position in ("before", "after")}


@unittest.skipUnless(sys.platform == "linux", "Official standalone LuaJIT fixture requires Linux")
class OfflineOutboxProbeTest(unittest.TestCase):
    def test_source_lifecycle_native_stops_same_second_recovery_generation_and_upgrade(self):
        reference = Path(os.environ["READING_SQLITE_REFERENCE_DIR"]).resolve(strict=True)
        wire = Path(os.environ["READING_WIRE_REFERENCE_DIR"]).resolve(strict=True)
        prepare_sqlite_reference.verify(reference)
        sys.path.insert(0, str(ROOT / "tools/reading_wire"))
        import prepare_reference_runtime
        prepare_reference_runtime.verify_reference(wire)
        with tempfile.TemporaryDirectory(prefix="quartzo-source-lifecycle-fixture-") as temporary:
            result = subprocess.run([str(reference / "luajit"),
                str(ROOT / "tools/plugin/outbox_probe_native_test.lua"),temporary,
                str(reference),str(wire),str(ROOT),"source_lifecycle"],capture_output=True,timeout=45)
            self.assertEqual(result.returncode,0,result.stdout.decode()+result.stderr.decode())
            report=json.loads(result.stdout)
            self.assertEqual(report["phase"],"passed")
            self.assertEqual(report["case_checks"],dict.fromkeys(outbox_probe_bundle.SOURCE_CASES,True))
            self.assertEqual(report["process_stop_cases"],2)
            self.assertEqual(report["same_second_events"],251)
            self.assertIs(report["user_statistics_accessed"],False)
            self.assertIs(report["synthetic_statistics_accessed"],True)
            for field in ("network_accessed","wifi_changed","canonical_ack","ack_watermark_changed",
                          "source_epoch_verified","gate4_passed"):
                self.assertIs(report[field],False,field)
            hashes=outbox_probe_bundle.inspect_source_state(Path(temporary)/"state")
            self.assertEqual(len(hashes),16)
            # Reports alone cannot hide a broken joined progress/event state.
            import sqlite3
            path=Path(temporary)/"state/collection_after_commit/quartzo_sync_state.sqlite3"
            original=path.read_bytes()
            with sqlite3.connect(path) as connection:
                connection.execute("UPDATE progress SET ack_watermark='99'")
            with self.assertRaises(ValueError):
                outbox_probe_bundle.inspect_source_state(Path(temporary)/"state")
            path.write_bytes(original)
            with sqlite3.connect(path) as connection:
                connection.execute("UPDATE pending SET line='{}' WHERE event_id=(SELECT event_id FROM pending LIMIT 1)")
            with self.assertRaises(ValueError):
                outbox_probe_bundle.inspect_source_state(Path(temporary)/"state")

    def test_actual_native_crash_recovery_and_untrusted_receipt_rejection(self):
        reference = Path(os.environ["READING_SQLITE_REFERENCE_DIR"]).resolve(strict=True)
        wire = Path(os.environ["READING_WIRE_REFERENCE_DIR"]).resolve(strict=True)
        prepare_sqlite_reference.verify(reference)
        sys.path.insert(0, str(ROOT / "tools/reading_wire"))
        import prepare_reference_runtime
        prepare_reference_runtime.verify_reference(wire)
        with tempfile.TemporaryDirectory(prefix="quartzo-offline-outbox-fixture-") as temporary:
            result = subprocess.run([str(reference / "luajit"),
                str(ROOT / "tools/plugin/outbox_probe_native_test.lua"),temporary,
                str(reference),str(wire),str(ROOT)], capture_output=True, timeout=45)
            self.assertEqual(result.returncode, 0, result.stdout.decode()+result.stderr.decode())
            report = json.loads(result.stdout)
            self.assertEqual(report["phase"], "passed")
            self.assertEqual(report["case_checks"], dict.fromkeys(CASES, True))
            self.assertEqual(report["process_stop_cases"], 6)
            self.assertEqual(report["native_entropy_cases"], 6)
            self.assertEqual(report["raw_receipt_rejections"], 5)
            self.assertIs(report["identity_and_pending_verified"], True)
            for field in ("statistics_accessed", "network_accessed", "wifi_changed",
                          "source_cursor_changed", "canonical_ack", "canonical_persistence_proven",
                          "paired_receipt_proven", "source_epoch_verified", "gate4_passed"):
                self.assertIs(report[field], False, field)
            state = Path(temporary) / "state"
            self.assertEqual({entry.name for entry in state.iterdir()}, CASES)
            for directory in state.iterdir():
                self.assertEqual((directory / "gate.ready").read_bytes(), b"ready")
                self.assertFalse(any("journal" in item.name for item in directory.iterdir()))
            self.assertEqual(len(outbox_probe_bundle.inspect_state(state,"a"*32)),12)


if __name__ == "__main__":
    unittest.main()
