"""Owned synthetic mount tests; matching reports never establish real hardware."""
import copy
import json
import pathlib
import shutil
import subprocess
import tempfile
import types
import unittest
from unittest import mock

import probe_bundle as bundle
from test_offline_probe import source_values


class ProbeBundleTest(unittest.TestCase):
    def setUp(self):
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="quartzo-wire-bundle-")).resolve()
        self.values = source_values()
        self.source_patch = mock.patch.object(bundle, "read_sources", return_value=self.values)
        self.source_patch.start()
        self.addCleanup(self.source_patch.stop)
        self.output = self.root / "bundle"
        self.manifest = bundle.prepare(self.output, "b" * 40)
        self.mount = self.root / "synthetic-mount"
        (self.mount / "koreader/common").mkdir(parents=True)
        (self.mount / "koreader/ffi").mkdir()
        (self.mount / "extensions").mkdir()
        (self.mount / "koreader/git-rev").write_bytes(b"v2026.07.1\n")
        (self.mount / "koreader/luajit").write_bytes(b"synthetic runtime placeholder")
        (self.mount / "koreader/common/dkjson.lua").write_bytes(b"owned native JSON source fixture")
        (self.mount / "koreader/ffi/sha2.lua").write_bytes(b"owned native SHA source fixture")
        self.statistics = self.mount / "koreader/statistics.sqlite3"
        self.statistics.write_bytes(b"owned Statistics preservation sentinel")
        self.observation = self.root / "installation-observation.json"

    def tearDown(self):
        # Recursive removal is restricted to this test's verified owned root.
        self.assertFalse(self.root.is_symlink() or self.root.is_junction())
        resolved = self.root.resolve()
        self.assertEqual(resolved, self.root)
        self.assertTrue(resolved.is_relative_to(pathlib.Path(tempfile.gettempdir()).resolve()))
        self.assertTrue(resolved.name.startswith("quartzo-wire-bundle-"))
        shutil.rmtree(resolved)

    def installed(self):
        observation = bundle.install(self.output, self.mount)
        self.observation.write_bytes(bundle.encoded(observation))
        self.target = self.mount / "extensions" / bundle.NAME
        return observation

    def completed(self):
        observation = self.installed()
        report = dict(probe_version=1, phase="passed", source_data="synthetic", uses_synthetic_clock=True,
            canonical_ack=False, canonical_persistence_proven=False, statistics_accessed=False,
            source_cursor_changed=False, network_accessed=False, wifi_changed=False,
            golden_checks=3, negative_cases=12, native_reference_cases=5, conflicting_positions=3,
            isolated_entries=3, expired_request_rejected=True, run_id=observation["run_id"],
            manifest_digest=observation["manifest_digest"], source_commit=observation["source_commit"],
            lua_version="Lua 5.1", jit_version="LuaJIT 2.1.0-beta3", jit_arch="arm", json_version="dkjson 2.10",
            koreader_version=bundle.BASELINE, native_source_sha256=observation["native_source_sha256"], cpu_seconds=0.125)
        (self.target / "run.lock").mkdir()
        (self.target / "launcher-status.txt").write_bytes(b"completed\n")
        (self.target / "device-observation.json").write_bytes(bundle.encoded(report))
        return report

    def test_prepare_preserves_existing_output_and_has_no_secret_or_reference_libraries(self):
        before = {path.name: path.read_bytes() for path in self.output.iterdir()}
        with self.assertRaises(ValueError):
            bundle.prepare(self.output, "b" * 40)
        self.assertEqual({path.name: path.read_bytes() for path in self.output.iterdir()}, before)
        self.assertEqual(set(before), set(bundle.SOURCE_MAP) | bundle.METADATA)
        self.assertNotIn("sha2.lua", before)
        self.assertNotIn("dkjson.lua", before)

    def test_changed_source_extra_file_and_duplicate_metadata_are_rejected(self):
        path = self.output / "codec.lua"
        original = path.read_bytes()
        path.write_bytes(b"changed source")
        with self.assertRaises(ValueError):
            bundle.verify_bundle(self.output)
        path.write_bytes(original)
        metadata = self.output / "public-session.json"
        saved = metadata.read_bytes()
        metadata.write_bytes(saved.replace(b'"probe_version":1', b'"probe_version":1,"probe_version":1'))
        with self.assertRaises(ValueError):
            bundle.verify_bundle(self.output)
        metadata.write_bytes(saved)
        (self.output / "foreign.txt").write_bytes(b"owned foreign fixture")
        with self.assertRaises(ValueError):
            bundle.verify_bundle(self.output)

    def test_install_only_creates_a_new_extension_and_preserves_native_files(self):
        before = {path.relative_to(self.mount): path.read_bytes() for path in (self.mount / "koreader").rglob("*") if path.is_file()}
        observation = self.installed()
        self.assertFalse(observation["canonical_ack"])
        self.assertFalse(observation["production_changed"])
        with self.assertRaises(ValueError):
            bundle.install(self.output, self.mount)
        self.assertEqual({path.relative_to(self.mount): path.read_bytes() for path in (self.mount / "koreader").rglob("*") if path.is_file()}, before)

    def test_wrong_baseline_missing_native_source_and_low_space_fail_before_copy(self):
        revision = self.mount / "koreader/git-rev"
        revision.write_bytes(b"other-version")
        with self.assertRaises(ValueError):
            bundle.install(self.output, self.mount)
        revision.write_bytes(b"v2026.07.1\n")
        native = self.mount / "koreader/common/dkjson.lua"
        native.unlink()
        with self.assertRaises(ValueError):
            bundle.install(self.output, self.mount)
        native.write_bytes(b"owned native JSON source fixture")
        with mock.patch.object(bundle.shutil, "disk_usage", return_value=types.SimpleNamespace(free=0)):
            with self.assertRaises(ValueError):
                bundle.install(self.output, self.mount)
        self.assertFalse((self.mount / "extensions" / bundle.NAME).exists())

    def test_junction_or_symbolic_extension_parent_does_not_redirect_installation(self):
        foreign = self.root / "foreign-owned-directory"
        foreign.mkdir()
        sentinel = foreign / "sentinel"
        sentinel.write_bytes(b"preserve")
        extensions = self.mount / "extensions"
        extensions.rmdir()
        if __import__("os").name == "nt":
            result = subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(extensions), str(foreign)], capture_output=True)
            self.assertEqual(result.returncode, 0)
            self.assertTrue(extensions.is_junction())
        else:
            extensions.symlink_to(foreign, target_is_directory=True)
        with self.assertRaises(ValueError):
            bundle.install(self.output, self.mount)
        self.assertEqual(sentinel.read_bytes(), b"preserve")
        self.assertFalse((foreign / bundle.NAME).exists())

    def test_matching_synthetic_observations_cannot_attest_physical_execution(self):
        self.completed()
        report = bundle.collect(self.output, self.mount, self.observation)
        self.assertTrue(report["observations_match"])
        self.assertFalse(report["physical_execution_attested"])
        self.assertFalse(report["canonical_ack"])
        self.assertFalse(report["canonical_persistence_proven"])
        self.assertFalse(report["source_cursor_changed"])
        self.assertEqual(self.statistics.read_bytes(), b"owned Statistics preservation sentinel")

    def test_missing_changed_or_ack_claiming_device_report_cannot_pass(self):
        report = self.completed()
        path = self.target / "device-observation.json"
        for changes in ({"canonical_ack": True}, {"network_accessed": True}, {"negative_cases": 11},
                        {"negative_cases": 12.0}, {"jit_arch": "x64"}, {"run_id": "c" * 32},
                        {"cpu_seconds": 120}, {"cpu_seconds": float("nan")}, {"private_extra": "sentinel"}):
            with self.subTest(changes=changes):
                path.write_bytes(bundle.encoded({**copy.deepcopy(report), **changes}))
                with self.assertRaises(ValueError):
                    bundle.collect(self.output, self.mount, self.observation)
        path.write_bytes(bundle.encoded(report))
        (self.target / "device-observation.json.tmp").write_bytes(b"unfinished")
        with self.assertRaises(ValueError):
            bundle.collect(self.output, self.mount, self.observation)

    def test_native_change_after_install_preserves_changed_source_and_blocks_collection(self):
        self.completed()
        native = self.mount / "koreader/common/dkjson.lua"
        native.write_bytes(b"different installed source")
        with self.assertRaises(ValueError):
            bundle.collect(self.output, self.mount, self.observation)
        self.assertEqual(native.read_bytes(), b"different installed source")
