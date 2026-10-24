-- Standalone official Linux LuaJIT fixture; never fork an embedded Python VM.
local root,sqlite_ref,wire_ref,repo,kind=unpack(arg)
assert(root and sqlite_ref and wire_ref and repo)
assert(kind==nil or kind=="source_lifecycle")
package.path=sqlite_ref.."/?.lua;"..repo.."/quartzo.koplugin/?.lua;"..package.path
bit=require("bit")
local ffi=require("ffi")
ffi.loadlib=function(name,version)
    assert(name=="sqlite3" and version=="0")
    return ffi.load(sqlite_ref.."/libs/libsqlite3.so.0")
end
package.preload["libs/libkoreader-lfs"]=function()
    return assert(package.loadlib(sqlite_ref.."/libs/libkoreader-lfs.so","luaopen_lfs"))()
end
package.preload.dkjson=function() return dofile(wire_ref.."/dkjson.lua") end
package.preload["ffi/sha2"]=function() return dofile(wire_ref.."/sha2.lua") end
local deps=assert(dofile(repo.."/quartzo.koplugin/quartzo/koreader_deps.lua").load(require))
local codec=dofile(repo.."/quartzo.koplugin/quartzo/codec.lua").new(deps)
package.loaded["quartzo/paired_exchange"]=dofile(repo.."/quartzo.koplugin/quartzo/paired_exchange.lua")
local process=dofile(repo.."/tools/plugin/outbox_probe.lua")
local probe=kind and dofile(repo.."/tools/plugin/source_probe.lua") or process
local report=probe.run(root.."/state",string.rep("a",32),
    dofile(repo.."/quartzo.koplugin/quartzo/outbox.lua"),codec,
    require("common/lua-ljsqlite3/init"),require("libs/libkoreader-lfs"),process)
print(assert(require("dkjson").encode(report)))
os.exit(report.phase=="passed" and 0 or 1)
