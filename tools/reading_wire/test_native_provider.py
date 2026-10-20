"""Real pinned Lua libraries in host LuaJIT 2.1; never an ARM/PW3 acceptance."""
import os
import pathlib
import unittest

from lupa.luajit21 import LuaRuntime
from prepare_reference_runtime import verify_reference
import test_codec

ROOT = pathlib.Path(__file__).resolve().parent


def libraries():
    directory = os.environ.get("READING_WIRE_REFERENCE_DIR")
    if not directory:
        raise RuntimeError("Prepare exact references and set READING_WIRE_REFERENCE_DIR before native-provider tests")
    directory = pathlib.Path(directory)
    verify_reference(directory)
    return (directory / "dkjson.lua").read_bytes(), (directory / "sha2.lua").read_bytes()


def provider_modules(lua):
    json_bytes, sha_bytes = libraries()
    json_module = lua.execute(json_bytes)
    sha_module = lua.execute(sha_bytes)
    loader = lua.eval("function(json,sha) return function(name) if name=='dkjson' then return json end; "
                      "if name=='ffi/sha2' then return sha end; error('unsupported_reference_module') end end")(json_module, sha_module)
    adapter = lua.execute((ROOT / "koreader_deps.lua").read_bytes())
    return adapter[b"load"](loader), json_module, sha_module


def provider(lua):
    return provider_modules(lua)[0]


class NativeProviderCodecTest(test_codec.WireCodecTest):
    lua_type = LuaRuntime

    def setUp(self):
        super().setUp()
        self.assertTrue(self.lua.eval("jit.version").startswith(b"LuaJIT 2.1"))
        deps = provider(self.lua)
        self.assertNotIsInstance(deps, tuple)
        self.null = deps[b"null"]
        self.lua.globals()[b"wire_null"] = self.null
        self.codec = self.module[b"new"](deps)
        self.assertNotIsInstance(self.codec, tuple)


class ProviderBoundaryTest(unittest.TestCase):
    def test_missing_or_shape_losing_providers_fail_closed_without_excerpts(self):
        lua = LuaRuntime(unpack_returned_tuples=True, encoding=None)
        adapter = lua.execute((ROOT / "koreader_deps.lua").read_bytes())
        for loader in (
            "function() error('private-provider-sentinel') end",
            "function() return {} end",
            "function(name) if name=='dkjson' then return {null={},decode=function() return {},1 end} end; return {sha256=function() return string.rep('0',64) end} end",
        ):
            self.assertEqual(adapter[b"load"](lua.eval(loader)), (None, b"unsupported_reading_wire_dependencies"))

    def test_real_providers_preserve_empty_containers_null_and_constructor_shapes(self):
        lua = LuaRuntime(unpack_returned_tuples=True, encoding=None)
        deps = provider(lua)
        value = deps[b"decode_json"](b'{"a":[],"b":{},"c":null}')
        self.assertEqual(deps[b"kind"](value[b"a"]), b"array")
        self.assertEqual(deps[b"kind"](value[b"b"]), b"object")
        self.assertEqual(deps[b"kind"](value[b"c"]), b"null")
        self.assertEqual(deps[b"kind"](deps[b"object"](lua.table())), b"object")
        self.assertEqual(deps[b"kind"](deps[b"array"](lua.table())), b"array")
