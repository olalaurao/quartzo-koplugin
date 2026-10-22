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
