-- Test-owned Linux fixtures only. Actual official SDK, LFS and OS entropy.
local mode,root,source,sqlite_ref,wire_ref,repo=unpack(arg)
package.path=sqlite_ref.."/?.lua;"..package.path
package.path=repo.."/quartzo.koplugin/?.lua;"..package.path
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
package.loaded["quartzo/statistics"]=dofile(repo.."/quartzo.koplugin/quartzo/statistics.lua")
local deps=assert(dofile(repo.."/quartzo.koplugin/quartzo/koreader_deps.lua").load(require))
local codec=assert(dofile(repo.."/quartzo.koplugin/quartzo/codec.lua").new(deps))
local owner=dofile(repo.."/quartzo.koplugin/quartzo/outbox.lua")
local sdk=require("common/lua-ljsqlite3/init")
local fs=require("libs/libkoreader-lfs")
local runtime={codec=codec,sqlite=sdk,filesystem=fs}
local queue
if mode=="enroll" then
    local reviewed=assert(owner.review_source(root,source,runtime))
    assert(not fs.attributes(root.."/quartzo_sync_state.sqlite3"))
    queue=assert(owner.enroll(root,reviewed.review,runtime))
    local selected=assert(queue.review_collection(source,"2026-10-24T00:00:00.000Z"))
    assert(assert(queue.status()).pending==0 and selected.canonical_ack==false)
    assert(assert(queue.stage_collection(selected.pass)).pending==2)
    assert(assert(queue.status()).source_watermark==nil)
    local saved=assert(queue.backup())
    local reviewed_copy=assert(owner.inspect_backup(root,saved.backup_leaf,runtime))
    assert(os.rename(root.."/quartzo_sync_state.sqlite3",root.."/retired-test-state.sqlite3"))
    local native_sdk=runtime.sqlite
    runtime.sqlite={open=function() error("orphan destination must be refused before SQLite opens",0) end}
    for _,suffix in ipairs({"-journal","-wal","-shm"}) do
        local orphan=root.."/quartzo_sync_state.sqlite3"..suffix
        local original=suffix=="-shm" and "" or "synthetic interrupted-state artifact"
        local output=assert(io.open(orphan,"wb"))
        assert(output:write(original) and output:close())
        local rejected,reason=owner.restore(root,saved.backup_leaf,runtime,reviewed_copy)
        assert(not rejected and reason=="outbox_recovery_review_required")
        assert(not fs.symlinkattributes(root.."/quartzo_sync_state.sqlite3"))
        local input=assert(io.open(orphan,"rb"))
        assert(input:read("*a")==original and input:close())
        assert(os.remove(orphan)) -- Only this fresh test-owned synthetic file.
    end
    runtime.sqlite=native_sdk
    queue=assert(owner.restore(root,saved.backup_leaf,runtime,reviewed_copy))
elseif mode=="reopen" then
    queue=assert(owner.open(root,runtime))
else error("unsupported fixture mode") end
assert(assert(queue.check_source(source)).source_state=="matches_enrollment")
assert(assert(queue.status()).pending==2)
local context=queue.context()
assert(context.device_id:match("^qrd_[a-f0-9]+$") and #context.device_id==36)
assert(context.source_epoch:match("^qse_[a-f0-9]+$") and #context.source_epoch==36)
assert(context.device_id:sub(5)~=context.source_epoch:sub(5))
local copied=source..".test-copy"
if mode=="enroll" then
    local input=assert(io.open(source,"rb"))
    local bytes=input:read("*a")
    input:close()
    local output=assert(io.open(copied,"wb"))
    assert(output:write(bytes));output:close()
end
local invalid,reason=queue.check_source(copied)
assert(not invalid and reason=="statistics_source_changed")
assert(assert(queue.status()).pending==2)
print(assert(require("dkjson").encode(context)))
