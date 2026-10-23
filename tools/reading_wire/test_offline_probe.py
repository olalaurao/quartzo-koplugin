"""Synthetic host harness/driver tests; no Kindle or physical attestation."""
import hashlib
import json
import pathlib
import unittest

from lupa.luajit21 import LuaRuntime
from test_native_provider import provider_modules
from probe_bundle import SOURCE_MAP

ROOT = pathlib.Path(__file__).resolve().parent


def source_values():
    values = {name: (ROOT.parents[1] / source).read_bytes().replace(b"\r\n", b"\n") for name, source in SOURCE_MAP.items()}
    values["run.sh"] = values["run.sh"].replace(b"quartzo-transport-probe", b"quartzo-wire-probe")
    return values


class OfflineProbeTest(unittest.TestCase):
    def setUp(self):
        self.lua = LuaRuntime(unpack_returned_tuples=True, encoding=None)
        self.deps, self.json, self.sha = provider_modules(self.lua)
        self.codec = self.lua.execute((ROOT.parents[1] / "quartzo.koplugin/quartzo/codec.lua").read_bytes())
        self.probe = self.lua.execute((ROOT / "probe.lua").read_bytes())
        self.wire = self.deps[b"decode_json"]((ROOT / "upstream/transport_vectors.json").read_bytes().rstrip())
        self.reference = self.deps[b"decode_json"]((ROOT / "dart_reference.json").read_bytes().rstrip())

    def run_probe(self):
        return self.probe[b"run"](self.deps, self.codec, self.wire, self.reference, self.json[b"encode"])

    def test_real_library_harness_passes_exact_offline_cases_without_ack(self):
        report = self.run_probe()
        self.assertEqual(report[b"phase"], b"passed")
        for key, count in ((b"golden_checks", 3), (b"negative_cases", 12), (b"native_reference_cases", 5), (b"conflicting_positions", 3), (b"isolated_entries", 3)):
            self.assertEqual(report[key], count)
        for key in (b"canonical_ack", b"canonical_persistence_proven", b"statistics_accessed", b"source_cursor_changed", b"network_accessed", b"wifi_changed"):
            self.assertFalse(report[key])
        self.assertTrue(report[b"uses_synthetic_clock"])
        self.assertTrue(report[b"expired_request_rejected"])

    def test_changed_golden_or_reference_cannot_pass(self):
        self.reference[b"cases"][1][b"native_payload"] = b"wrong native payload"
        report = self.run_probe()
        self.assertEqual(report[b"phase"], b"failed")
        self.assertEqual(report[b"error_code"], b"wire_probe_check_failed")

    def test_committed_claim_cannot_be_relabelled_as_ack_by_the_harness(self):
        self.lua.eval("function(module) local create=module.new; module.new=function(deps) "
                      "local api=create(deps); local decode=api.decode_response; api.decode_response=function(...) "
                      "local result=decode(...); if result then result.canonical_ack=true end; return result end; return api end end")(self.codec)
        self.assertEqual(self.run_probe()[b"phase"], b"failed")

    def driver(self, mutate=None):
        values = source_values()
        prefix = b"/mnt/us/extensions/quartzo-wire-probe/"
        manifest = dict(probe_version=1, run_id="a" * 32, koreader_baseline="v2026.07.1", source_commit="b" * 40,
                        files={name: hashlib.sha256(value).hexdigest() for name, value in values.items()})
        manifest_bytes = json.dumps(manifest, separators=(",", ":")).encode()
        session = dict(probe_version=1, run_id=manifest["run_id"], manifest_digest=hashlib.sha256(manifest_bytes).hexdigest())
        fs = self.lua.table_from({prefix + name.encode(): value for name, value in values.items()})
        fs[prefix + b"bundle-manifest.json"] = manifest_bytes
        fs[prefix + b"public-session.json"] = json.dumps(session, separators=(",", ":")).encode()
        fs[b"git-rev"] = b"v2026.07.1\n"
        fs[b"common/dkjson.lua"] = b"synthetic installed library identity only"
        fs[b"ffi/sha2.lua"] = b"synthetic installed hash identity only"
        if mutate:
            mutate(fs, prefix)
        # Driver-only I/O is mapped to a fixed in-memory allow-list. No native
        # path, process exit, module loader or filesystem is used by this host test.
        io_stub, os_stub, load, dofile_stub, reads, output = self.lua.execute("""
            local fs, json, sha = ...
            local reads, output = {}, {}
            local io = {open=function(path, mode)
              if mode=='rb' then
                reads[#reads+1]=path
                if fs[path]==nil then return nil end
                return {read=function(_,size) return fs[path]:sub(1,size) end,close=function() return true end}
              end
              if mode~='wb' or fs[path]~=nil then return nil end
              local data=''
              return {write=function(_,bytes) data=data..bytes; return true end,
                close=function() fs[path]=data; return true end}
            end}
            local os={clock=function() return 0 end,exit=function(code) output.exit_code=code end,
              rename=function(source,target) if fs[source]==nil or fs[target]~=nil then return nil end
                fs[target]=fs[source]; fs[source]=nil; return true end}
            local function loader(name)
              if name=='setupkoenv' then return true end
              if name=='dkjson' then return json end
              if name=='ffi/sha2' then return sha end
              error('unexpected_native_module')
            end
            local function dofile(path) assert(fs[path]); return assert(loadstring(fs[path]))() end
            return io,os,loader,dofile,reads,output
        """, fs, self.json, self.sha)
        self.lua.globals()[b"io"] = io_stub
        self.lua.globals()[b"os"] = os_stub
        self.lua.globals()[b"require"] = load
        self.lua.globals()[b"dofile"] = dofile_stub
        self.lua.execute(values["kindle.lua"])
        return json.loads(fs[prefix + b"device-observation.json"]), list(reads.values()), output[b"exit_code"]

    def test_actual_driver_accepts_lf_fixtures_and_produces_bounded_host_observation(self):
        report, reads, exit_code = self.driver()
        self.assertEqual(report["phase"], "passed")
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["jit_arch"], "x64")
        self.assertEqual(report["run_id"], "a" * 32)
        self.assertFalse(report["canonical_ack"])
        self.assertLess(len(json.dumps(report).encode()), 8192)
        allowed = {b"git-rev", b"common/dkjson.lua", b"ffi/sha2.lua"}
        prefix = b"/mnt/us/extensions/quartzo-wire-probe/"
        allowed.update(prefix + name.encode() for name in (*SOURCE_MAP, "bundle-manifest.json", "public-session.json"))
        self.assertTrue(set(reads) <= allowed)
        self.assertFalse(any(b"statistics" in path or b"sidecar" in path for path in reads))

    def test_driver_rejects_changed_bundle_or_unavailable_native_identity(self):
        for mutation in (lambda fs, prefix: fs.__setitem__(prefix + b"codec.lua", b"changed source"),
                         lambda fs, prefix: fs.__setitem__(b"common/dkjson.lua", None)):
            with self.subTest(mutation=mutation):
                # Each driver run needs its own clean injected runtime.
                self.setUp()
                report, _, exit_code = self.driver(mutation)
                self.assertEqual(report["phase"], "failed")
                self.assertEqual(exit_code, 1)
                self.assertEqual(report["error_code"], "wire_probe_exception")
                self.assertFalse(report["canonical_ack"])
