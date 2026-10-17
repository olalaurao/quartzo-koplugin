"""POSIX process deadline/single-use tests in an owned host fixture only."""
import os
import pathlib
import shlex
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.name == "posix" and pathlib.Path("/proc/self/stat").exists(),
    "Actual POSIX/proc process semantics require Linux; Windows checks syntax separately")
class LauncherProcessTest(unittest.TestCase):
    def fixture(self, root, executable):
        owned, runtime = root / "owned", root / "runtime"
        owned.mkdir()
        runtime.mkdir()
        (runtime / "git-rev").write_text("v2026.07.1\n")
        binary = runtime / "luajit"
        binary.write_text("#!/bin/sh\n" + executable + "\n")
        binary.chmod(0o700)
        source = pathlib.Path(__file__).with_name("run.sh").read_text()
        source = source.replace("OWNED=/mnt/us/extensions/quartzo-transport-probe",
            "OWNED=" + shlex.quote(str(owned)))
        source = source.replace("/mnt/us/koreader/git-rev", str(runtime / "git-rev"))
        source = source.replace("cd /mnt/us/koreader", "cd " + shlex.quote(str(runtime)))
        source = source.replace("DEADLINE_SECONDS=120", "DEADLINE_SECONDS=1")
        script = root / "run.sh"
        script.write_text(source)
        return owned, script

    def test_success_is_single_use_and_refuses_second_execution(self):
        with tempfile.TemporaryDirectory(prefix="quartzo-launcher-test-") as temporary:
            owned, script = self.fixture(pathlib.Path(temporary), "exit 0")
            result = subprocess.run(["sh", str(script)], timeout=5, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((owned / "launcher-status.txt").read_text().strip(), "completed")
            result = subprocess.run(["sh", str(script)], timeout=5, capture_output=True)
            self.assertNotEqual(result.returncode, 0)

    def test_watchdog_stops_only_owned_child_and_reports_failure(self):
        with tempfile.TemporaryDirectory(prefix="quartzo-launcher-test-") as temporary:
            owned, script = self.fixture(pathlib.Path(temporary), "exec sleep 30")
            unrelated = subprocess.Popen(["sleep", "30"])
            try:
                result = subprocess.run(["sh", str(script)], timeout=6, capture_output=True)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((owned / "launcher-status.txt").read_text().strip(), "failed_or_timed_out")
                self.assertIsNone(unrelated.poll())
            finally:
                unrelated.terminate()
                unrelated.wait(timeout=5)


if __name__ == "__main__": unittest.main()
