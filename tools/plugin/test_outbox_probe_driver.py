"""Driver I/O/manifest model only; native process proof is a separate CLI test."""
import hashlib
import json
import unittest

from lupa.luajit21 import LuaRuntime
import outbox_probe_bundle as bundle
from test_native_provider import provider_modules


class OutboxProbeDriverTest(unittest.TestCase):
    def driver(self,mutate=None,native_change=False):
        lua=LuaRuntime(unpack_returned_tuples=True,encoding=None)
        deps,json_module,sha_module=provider_modules(lua)
        values={name:(bundle.base.ROOT/source).read_bytes().replace(b"\r\n",b"\n")
                for name,source in bundle.SOURCES.items()}
        values["run.sh"]=values["run.sh"].replace(b"quartzo-transport-probe",bundle.NAME.encode())
        prefix=b"/mnt/us/extensions/quartzo-outbox-probe/"
        manifest=dict(probe_version=1,run_id="a"*32,koreader_baseline=bundle.base.BASELINE,source_commit="b"*40,
                      files={name:hashlib.sha256(data).hexdigest() for name,data in values.items()})
        encoded=bundle.base.encoded(manifest)
        fs=lua.table_from({prefix+name.encode():data for name,data in values.items()})
        fs[prefix+b"bundle-manifest.json"]=encoded
        fs[prefix+b"public-session.json"]=bundle.base.encoded(dict(probe_version=1,run_id="a"*32,
                                                       manifest_digest=bundle.base.sha(encoded)))
        fs[b"git-rev"]=b"v2026.07.1\n"
        for path in bundle.NATIVE.values(): fs[path.encode()]=b"synthetic native fingerprint"
        if mutate: mutate(fs,prefix)
        io_stub,os_stub,loader,dofile_stub,reads,output=lua.execute("""
            local fs,json,sha,prefix,changed=...
            local reads,output,native_reads={},{},0
            local io={open=function(path,mode)
                if mode=='rb' then
                    reads[#reads+1]=path
                    local bytes=fs[path]
                    if bytes==nil then return nil end
                    if path=='libs/libsqlite3.so.0' then
                        native_reads=native_reads+1
                        if changed and native_reads==2 then bytes='changed native fixture' end
                    end
                    return {read=function(_,limit) return bytes:sub(1,limit) end,close=function() return true end}
                end
                assert(mode=='wb' and path==prefix..'device-observation.json.tmp' and fs[path]==nil)
                local bytes=''
                return {write=function(_,value) bytes=bytes..value;return true end,
                    close=function() fs[path]=bytes;return true end}
            end}
            local os={clock=function() return 0 end,exit=function(code) output.exit_code=code end,
                rename=function(source,target)
                    assert(source==prefix..'device-observation.json.tmp' and target==prefix..'device-observation.json')
                    assert(fs[source] and fs[target]==nil)
                    fs[target]=fs[source];fs[source]=nil;return true
                end}
            local function loader(name)
                if name=='setupkoenv' then return true end
                if name=='dkjson' then return json end
                if name=='ffi/sha2' then return sha end
                if name=='lua-ljsqlite3/init' or name=='libs/libkoreader-lfs' then return {} end
                error('unexpected_driver_module')
            end
            local function load(path)
                assert(fs[path])
                if path==prefix..'probe.lua' then
                    -- Only the driver boundary is modeled here. Actual fork,
                    -- native SQLite and entropy run in the standalone fixture.
                    return {run=function(root,run_id,outbox,codec,sdk,lfs)
                        assert(root==prefix..'state' and run_id==string.rep('a',32))
                        output.probe_calls=(output.probe_calls or 0)+1
                        return {phase='passed',canonical_ack=false,driver_model_only=true}
                    end}
                end
                return assert(loadstring(fs[path]))()
            end
            return io,os,loader,load,reads,output
        """,fs,json_module,sha_module,prefix,native_change)
        lua.globals()[b"io"],lua.globals()[b"os"]=io_stub,os_stub
        lua.globals()[b"require"],lua.globals()[b"dofile"]=loader,dofile_stub
        # Model metadata, never claim an ARM runtime in this host fixture.
        lua.globals()[b"jit"]=lua.table_from({b"os":b"Linux",b"arch":b"arm",b"version":b"LuaJIT 2.1.0-beta3"})
        lua.execute(values["kindle.lua"])
        return json.loads(fs[prefix+b"device-observation.json"]),list(reads.values()),output

    def test_source_bound_driver_reads_only_allowlisted_inputs_and_writes_one_report(self):
        report,reads,output=self.driver()
        self.assertEqual(report["phase"],"passed")
        self.assertEqual(output[b"exit_code"],0)
        self.assertEqual(output[b"probe_calls"],1)
        self.assertTrue(report["driver_model_only"])
        self.assertIs(report["canonical_ack"],False)
        prefix=b"/mnt/us/extensions/quartzo-outbox-probe/"
        allowed={prefix+name.encode() for name in (*bundle.SOURCES,"bundle-manifest.json","public-session.json")}
        allowed.update(path.encode() for path in bundle.NATIVE.values())
        allowed.add(b"git-rev")
        self.assertLessEqual(set(reads),allowed)
        self.assertEqual(set(report["native_source_sha256"]),set(bundle.NATIVE))
        self.assertFalse(any(b"statistics" in name or b"sidecar" in name for name in reads))

    def test_tampered_sources_and_wrong_baseline_fail_before_core(self):
        for mutation in (lambda fs,prefix:fs.__setitem__(prefix+b"outbox.lua",b"changed"),
                         lambda fs,prefix:fs.__setitem__(b"git-rev",b"other-version"),
                         lambda fs,prefix:fs.__setitem__(b"libs/libsqlite3.so.0",None)):
            with self.subTest(mutation=mutation):
                report,_,output=self.driver(mutation)
                self.assertEqual(report["phase"],"failed")
                self.assertEqual(report["error_code"],"outbox_probe_exception")
                self.assertEqual(output[b"exit_code"],1)
                self.assertIsNone(output[b"probe_calls"])

    def test_native_change_after_core_suppresses_success(self):
        report,_,output=self.driver(native_change=True)
        self.assertEqual(report["phase"],"failed")
        self.assertEqual(output[b"exit_code"],1)
        self.assertEqual(output[b"probe_calls"],1)


if __name__=="__main__": unittest.main()
