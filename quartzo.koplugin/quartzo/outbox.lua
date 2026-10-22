-- Plugin-owned delivery state, never canonical Reading Activity or Statistics.
-- No startup/lifecycle/network caller. Missing/corrupt state never re-enrolls.
local M = {}
local FILE = "quartzo_sync_state.sqlite3"
local CAP = 1000
local function check(value, code)
    if not value then error(code or "invalid_outbox_state", 0) end
end
local function scope(value)
    return type(value) == "string" and #value > 0 and #value <= 128
        and not value:find("[^A-Za-z0-9_-]")
end
local function integer(value)
    return type(value) == "number" and value == value and value % 1 == 0
        and math.abs(value) <= 9007199254740991
end
local function path(root)
    check(type(root) == "string" and #root > 0 and not root:find("%z")
        and not root:lower():match("^file:"))
    return root .. "/" .. FILE
end
local function backup_path(root, leaf)
    path(root)
    local suffix=type(leaf)=="string" and leaf:match("^quartzo_sync_recovery_([a-f0-9]+)%.sqlite3$")
    check(suffix and #suffix==32)
    return root.."/"..leaf
end
local function regular(name, runtime)
    local attributes = runtime.attributes
    if not attributes then attributes = require("libs/libkoreader-lfs").symlinkattributes end
    local info = attributes(name)
    check(info == nil or info.mode == "file", "unsupported_outbox_file")
    return info ~= nil
end
local function entropy()
    local file = assert(io.open("/dev/urandom", "rb"))
    local ok, bytes = pcall(file.read, file, 16)
    local closed = file:close()
    check(ok and closed and type(bytes) == "string" and #bytes == 16, "outbox_entropy_unavailable")
    return bytes
end
local function generated_device(runtime)
    local bytes = (runtime.entropy or entropy)()
    check(type(bytes) == "string" and #bytes == 16, "outbox_entropy_unavailable")
    return "qrd_" .. bytes:gsub(".", function(c) return string.format("%02x", c:byte()) end)
end
local function count(conn, name)
    -- Fixed owner table names only. Corrupt over-cap state cannot load history.
    local n = tonumber(conn:rowexec("SELECT COUNT(*) FROM (SELECT 1 FROM " .. name .. " LIMIT 1001)"))
    check(integer(n) and n >= 0 and n <= CAP, "outbox_capacity")
    return n
end
local function execute(conn, sql, ...)
    local stmt = conn:prepare(sql)
    stmt:bind(...)
    stmt:step()
    stmt:close()
end
local function query(conn, sql, ...)
    local stmt = conn:prepare(sql)
    stmt:bind(...)
    local row = stmt:step()
    stmt:close()
    return row
end
local function bounded(name, maximum)
    -- Fixed owner column names only; do not load oversized corrupt fields.
    return "CASE WHEN typeof("..name..")='text' AND length(CAST("..name
        .." AS BLOB))<="..maximum.." THEN "..name.." ELSE NULL END"
end
-- One owner declaration serves creation AND validation. table_info alone hides
-- generated columns, collations, CHECK/UNIQUE/FK constraints and table options.
-- Cloning an unfamiliar declaration would silently drop those semantics.
local definitions = {
    identity="(id INTEGER PRIMARY KEY CHECK(id=1), device_id TEXT NOT NULL,source_epoch TEXT NOT NULL)",
    pending="(event_id TEXT PRIMARY KEY,line TEXT NOT NULL,native_digest TEXT NOT NULL)",
    review="(started_at INTEGER NOT NULL,book_id TEXT NOT NULL,page TEXT NOT NULL,"
        .."duration TEXT NOT NULL,pages TEXT NOT NULL,types TEXT NOT NULL,"
        .."PRIMARY KEY(started_at,book_id,page,duration,pages,types))",
}
local function create_schema(conn, prefix)
    check(prefix=="" or prefix=="recovery.")
    for _,name in ipairs({"identity","pending","review"}) do
        conn:exec("CREATE TABLE "..prefix..name..definitions[name])
    end
end
local function check_schema(conn)
    local indexes={sqlite_autoindex_pending_1="pending",sqlite_autoindex_review_1="review"}
    local objects=conn:prepare("SELECT name,type,tbl_name,"
        .."CASE WHEN typeof(sql)='text' AND length(CAST(sql AS BLOB))<=1024 THEN sql ELSE NULL END "
        .."FROM sqlite_master LIMIT 6")
    local seen={}
    for _=1,6 do
        local row=objects:step()
        if not row then break end
        local name=row[1]
        check(not seen[name])
        if definitions[name] then
            check(row[2]=="table" and row[3]==name and row[4]=="CREATE TABLE "..name..definitions[name])
        else
            check(indexes[name] and row[2]=="index" and row[3]==indexes[name] and row[4]==nil)
        end
        seen[row[1]]=true
    end
    objects:close()
    for _,name in ipairs({"identity","pending","review","sqlite_autoindex_pending_1","sqlite_autoindex_review_1"}) do
        check(seen[name])
    end
end
local function configured(conn)
    conn:set_busy_timeout(1000)
    -- Existing KOReader SQLite owns recovery/rollback; no second JSON journal.
    check(conn:rowexec("PRAGMA journal_mode=DELETE") == "delete")
    conn:exec("PRAGMA synchronous=EXTRA")
    check(tonumber(conn:rowexec("PRAGMA synchronous")) == 3)
    conn:exec("PRAGMA temp_store=MEMORY")
end
local function own_schema(conn)
    check(tonumber(conn:rowexec("PRAGMA user_version")) == 1, "unsupported_outbox_schema")
    check(conn:rowexec("PRAGMA quick_check(1)") == "ok", "invalid_outbox_state")
    check_schema(conn)
    check(tonumber(conn:rowexec("SELECT COUNT(*) FROM (SELECT 1 FROM identity LIMIT 2)"))==1)
    local row = query(conn, "SELECT "..bounded("device_id",128)..","..bounded("source_epoch",128).." FROM identity WHERE id=1")
    check(row and scope(row[1]) and scope(row[2]))
    check(count(conn, "pending") + count(conn, "review") <= CAP, "outbox_capacity")
    return {device_id=row[1], source_epoch=row[2]}
end
local errors = {invalid_outbox_state=true,unsupported_outbox_schema=true,unsupported_outbox_file=true,
    outbox_capacity=true,outbox_exists=true,outbox_missing=true,outbox_scope_mismatch=true,
    outbox_native_conflict=true,outbox_entropy_unavailable=true,unverified_reading_receipt=true,
    outbox_backup_missing=true}
local function operation(name, runtime, mode, callback)
    local conn
    local ok, value = pcall(function()
        conn = (runtime.sqlite or require("lua-ljsqlite3/init")).open(name, mode)
        return callback(conn)
    end)
    if conn then
        local closed = pcall(conn.close, conn)
        if not closed then return nil, "outbox_unavailable" end
    end
    if ok then return value end
    return nil, errors[value] and value or "outbox_unavailable"
end
local function transaction(conn, callback)
    conn:exec("BEGIN IMMEDIATE")
    local value = callback()
    conn:exec("COMMIT")
    return value -- Any failure closes the connection and rolls back its journal.
end
local function context_equal(a, b)
    check(a.device_id == b.device_id and a.source_epoch == b.source_epoch, "outbox_scope_mismatch")
end
local function inspect(codec, line, context)
    check(type(line) == "string" and #line <= 8192)
    local entry = codec.inspect_event(line)
    check(type(entry) == "table" and entry.canonical_ack == false)
    context_equal(entry, context)
    return entry
end
local function verify_contents(conn, codec, context)
    check(type(codec)=="table" and type(codec.inspect_event)=="function")
    local stmt=conn:prepare("SELECT "..bounded("event_id",68)..","..bounded("line",8192)
        ..","..bounded("native_digest",64).." FROM pending LIMIT 1001")
    for i=1,CAP+1 do
        local row=stmt:step()
        if not row then break end
        check(i<=CAP,"outbox_capacity")
        local entry=inspect(codec,row[2],context)
        check(entry.event_id==row[1] and entry.native_digest==row[3])
    end
    stmt:close()
    stmt=conn:prepare("SELECT CASE WHEN typeof(started_at)='integer' THEN started_at ELSE NULL END,"
        ..bounded("book_id",20)..","..bounded("page",20)..","..bounded("duration",20)..","
        ..bounded("pages",20)..","..bounded("types",39).." FROM review LIMIT 1001")
    local valid_types={integer=true,real=true,text=true,blob=true,["null"]=true}
    for i=1,CAP+1 do
        local row=stmt:step()
        if not row then break end
        check(i<=CAP,"outbox_capacity")
        check(integer(tonumber(row[1])) and type(row[6])=="string")
        local types={}
        for value in row[6]:gmatch("[^,]+") do check(valid_types[value]);types[#types+1]=value end
        check(#types==5 and types[3]=="integer" and table.concat(types,",")==row[6])
        for j,source in ipairs({1,2,4,5}) do
            local value=row[j+1]
            check(type(value)=="string")
            if types[source]=="integer" then check(value:match("^%-?%d+$"))
            else check(value=="") end
        end
    end
    stmt:close()
end
local function clone(conn, destination, runtime, context)
    check(not regular(destination,runtime),"outbox_exists")
    -- Both databases are plugin-owned, in the same directory. SQLite's attached
    -- DELETE-journal transaction is the copy/recovery mechanism; no raw file copy.
    check(conn:rowexec("PRAGMA journal_mode")=="delete")
    conn:exec("PRAGMA synchronous=EXTRA")
    check(tonumber(conn:rowexec("PRAGMA synchronous"))==3)
    -- Native sqlite3_open_v2(...,rw) does not let ATTACH create its target.
    -- Create only this fresh owned destination explicitly; never weaken the
    -- existing source's non-creating open mode to rwc.
    local created,reason=operation(destination,runtime,"rwc",function(target)
        check(tonumber(target:rowexec("PRAGMA user_version"))==0,"outbox_exists")
        check(tonumber(target:rowexec("SELECT COUNT(*) FROM sqlite_master"))==0,"outbox_exists")
        configured(target)
        return true
    end)
    if not created then error(reason,0) end
    execute(conn,"ATTACH DATABASE ? AS recovery",destination)
    local function fresh()
        check(tonumber(conn:rowexec("PRAGMA recovery.user_version"))==0,"outbox_exists")
        check(tonumber(conn:rowexec("SELECT COUNT(*) FROM recovery.sqlite_master"))==0,"outbox_exists")
    end
    fresh()
    check(conn:rowexec("PRAGMA recovery.journal_mode=DELETE")=="delete")
    conn:exec("PRAGMA recovery.synchronous=EXTRA")
    check(tonumber(conn:rowexec("PRAGMA recovery.synchronous"))==3)
    return transaction(conn,function()
        fresh()
        context_equal(own_schema(conn),context)
        verify_contents(conn,runtime.codec,context)
        create_schema(conn,"recovery.")
        for _,name in ipairs({"identity","pending","review"}) do
            conn:exec("INSERT INTO recovery."..name.." SELECT * FROM main."..name)
        end
        conn:exec("PRAGMA recovery.user_version=1")
        return {device_id=context.device_id,source_epoch=context.source_epoch,
            pending=count(conn,"pending"),review=count(conn,"review"),canonical_ack=false}
    end)
end
local function handle(name, runtime, context)
    local codec = runtime.codec
    check(type(codec) == "table" and type(codec.inspect_event) == "function")
    local function access(write, callback)
        local checked,exists=pcall(regular,name,runtime)
        if not checked then return nil,"unsupported_outbox_file" end
        if not exists then return nil,"outbox_missing" end
        -- Existing owned state may need SQLite hot-journal recovery even on read.
        -- rw never creates a missing file; Statistics is a separate ro owner.
        return operation(name, runtime, "rw", function(conn)
            context_equal(own_schema(conn), context)
            if write then configured(conn) end
            return callback(conn)
        end)
    end
    local api = {}
    function api.context()
        return {device_id=context.device_id, source_epoch=context.source_epoch}
    end
    function api.status()
        return access(false, function(conn)
            return {pending=count(conn,"pending"), review=count(conn,"review"), capacity=CAP,
                source_watermark=nil, canonical_ack=false}
        end)
    end
    function api.backup()
        return access(true,function(conn)
            local leaf="quartzo_sync_recovery_"..generated_device(runtime):sub(5)..".sqlite3"
            local destination=name:sub(1,-#FILE-1)..leaf
            local result=clone(conn,destination,runtime,context)
            local preview=M.inspect_backup(name:sub(1,-#FILE-2),leaf,runtime)
            check(preview and preview.pending==result.pending and preview.review==result.review)
            context_equal(preview,context)
            result.backup_leaf=leaf
            return result
        end)
    end
    function api.stage(batch)
        return access(true, function(conn)
            check(type(batch) == "table" and type(batch.event_lines) == "table"
                and type(batch.rejections) == "table" and integer(batch.scanned_count)
                and batch.scanned_count >= 0 and batch.scanned_count <= 100
                and #batch.event_lines + #batch.rejections == batch.scanned_count)
            -- Snapshot validated bounded caller data before the writer transaction.
            local incoming, reviews = {}, {}
            for i,line in ipairs(batch.event_lines) do
                local entry = inspect(codec,line,context)
                incoming[i] = {line=line, event_id=entry.event_id, native_digest=entry.native_digest}
            end
            for i,item in ipairs(batch.rejections) do
                check(type(item)=="table" and item.reason=="invalid_statistics_event"
                    and integer(item.started_at) and integer(item.row_id)
                    and type(item.integer_fields)=="table" and type(item.field_types)=="table")
                local values = {item.started_at}
                for _,key in ipairs({"book_row_id","page","duration_seconds","total_pages"}) do
                    local value = item.integer_fields[key]
                    check(value == nil or (type(value)=="string" and #value<=20
                        and value:match("^%-?%d+$")))
                    values[#values+1] = value or ""
                end
                local types={}
                check(#item.field_types==5)
                for j=1,5 do
                    local value=item.field_types[j]
                    check(value=="integer" or value=="real" or value=="text" or value=="blob" or value=="null")
                    types[j]=value
                end
                values[#values+1] = table.concat(types,",")
                reviews[i]=values
            end
            return transaction(conn,function()
                for _,entry in ipairs(incoming) do
                    local saved=query(conn,"SELECT native_digest FROM pending WHERE event_id=?",entry.event_id)
                    check(not saved or saved[1]==entry.native_digest,"outbox_native_conflict")
                    -- Preserve the first immutable selected bytes/observation.
                    if not saved then execute(conn,"INSERT INTO pending(event_id,line,native_digest) VALUES(?,?,?)",
                        entry.event_id,entry.line,entry.native_digest) end
                end
                for _,values in ipairs(reviews) do
                    execute(conn,"INSERT OR IGNORE INTO review(started_at,book_id,page,duration,pages,types) VALUES(?,?,?,?,?,?)",
                        unpack(values))
                end
                local pending, review=count(conn,"pending"),count(conn,"review")
                check(pending+review<=CAP,"outbox_capacity")
                return {pending=pending,review=review,canonical_ack=false}
            end)
        end)
    end
    function api.pending(limit)
        limit=limit or 50
        if not integer(limit) or limit<1 or limit>100 then return nil,"invalid_outbox_state" end
        return access(false,function(conn)
            local stmt=conn:prepare("SELECT CASE WHEN length(CAST(line AS BLOB))<=8192 THEN line ELSE NULL END,"
                .. "event_id,native_digest FROM pending ORDER BY event_id LIMIT ?")
            stmt:bind(limit)
            local lines,bytes={},0
            for _=1,limit do
                local row=stmt:step()
                if not row then break end
                local entry=inspect(codec,row[1],context)
                check(entry.event_id==row[2] and entry.native_digest==row[3])
                if bytes+#row[1]+1>524288 then break end
                bytes=bytes+#row[1]+1
                lines[#lines+1]=row[1]
            end
            stmt:close()
            return {event_lines=lines,canonical_ack=false}
        end)
    end
    function api.consume_receipt(session,receipt,request_bytes)
        return access(true,function(conn)
            -- Only the existing approved-pairing owner's opaque receipt can prune.
            -- No accepted-ID/boolean/parser entry point is exposed here. Production
            -- module composition remains gated until its owner is installed.
            local paired=require("quartzo/paired_exchange")
            local accepted=paired.acknowledged(session,receipt,request_bytes)
            check(type(accepted)=="table" and #accepted<=1000,"unverified_reading_receipt")
            return transaction(conn,function()
                local removed=0
                for _,claim in ipairs(accepted) do
                    check(type(claim)=="table","unverified_reading_receipt")
                    local saved=query(conn,"SELECT line,native_digest FROM pending WHERE event_id=?",claim.event_id)
                    if saved then
                        local entry=inspect(codec,saved[1],context)
                        check(entry.native_digest==claim.native_digest and entry.line_digest==claim.line_digest,
                            "unverified_reading_receipt")
                        execute(conn,"DELETE FROM pending WHERE event_id=? AND line=?",claim.event_id,saved[1])
                        removed=removed+1
                    end
                end
                return {removed=removed,review_retained=count(conn,"review"),source_watermark=nil,canonical_ack=false}
            end)
        end)
    end
    return api
end

function M.create(root, source_epoch, runtime)
    runtime=runtime or {}
    local ok,name=pcall(path,root)
    if not ok or not scope(source_epoch) then return nil,"invalid_outbox_state" end
    local checked,exists=pcall(regular,name,runtime)
    if not checked then return nil,"unsupported_outbox_file" end
    if exists then return nil,"outbox_exists" end
    return operation(name,runtime,"rwc",function(conn)
        -- The file can appear between the filesystem check and SQLite open.
        -- Reject unknown/existing state before any journal configuration writes.
        local function fresh()
            check(tonumber(conn:rowexec("PRAGMA user_version"))==0,"outbox_exists")
            check(tonumber(conn:rowexec("SELECT COUNT(*) FROM sqlite_master"))==0,"outbox_exists")
        end
        fresh()
        configured(conn)
        return transaction(conn,function()
            fresh()
            local context={device_id=generated_device(runtime),source_epoch=source_epoch}
            create_schema(conn,"")
            execute(conn,"INSERT INTO identity VALUES(1,?,?)",context.device_id,context.source_epoch)
            conn:exec("PRAGMA user_version=1")
            return handle(name,runtime,context)
        end)
    end)
end
function M.open(root, runtime)
    runtime=runtime or {}
    local ok,name=pcall(path,root)
    if not ok then return nil,"invalid_outbox_state" end
    local checked,exists=pcall(regular,name,runtime)
    if not checked then return nil,"unsupported_outbox_file" end
    if not exists then return nil,"outbox_missing" end
    return operation(name,runtime,"rw",function(conn)
        return handle(name,runtime,own_schema(conn))
    end)
end
function M.inspect_backup(root, backup_leaf, runtime)
    runtime=runtime or {}
    local ok,name=pcall(backup_path,root,backup_leaf)
    if not ok then return nil,"invalid_outbox_state" end
    local checked,exists=pcall(regular,name,runtime)
    if not checked then return nil,"unsupported_outbox_file" end
    if not exists then return nil,"outbox_backup_missing" end
    return operation(name,runtime,"rw",function(conn)
        conn:exec("BEGIN DEFERRED")
        local context=own_schema(conn)
        verify_contents(conn,runtime.codec,context)
        return {device_id=context.device_id,source_epoch=context.source_epoch,
            pending=count(conn,"pending"),review=count(conn,"review"),canonical_ack=false}
    end)
end
function M.restore(root, backup_leaf, runtime)
    runtime=runtime or {}
    local ok,name=pcall(path,root)
    local valid,backup=pcall(backup_path,root,backup_leaf)
    if not ok or not valid then return nil,"invalid_outbox_state" end
    local checked,exists=pcall(regular,name,runtime)
    if not checked then return nil,"unsupported_outbox_file" end
    if exists then return nil,"outbox_exists" end
    checked,exists=pcall(regular,backup,runtime)
    if not checked then return nil,"unsupported_outbox_file" end
    if not exists then return nil,"outbox_backup_missing" end
    local restored,reason=operation(backup,runtime,"rw",function(conn)
        local context=own_schema(conn)
        -- Validate before creating/attaching the destination; a malformed backup
        -- remains available for review and cannot silently become empty state.
        verify_contents(conn,runtime.codec,context)
        return clone(conn,name,runtime,context)
    end)
    if not restored then return nil,reason end
    local reopened,failure=M.open(root,runtime)
    if not reopened then return nil,failure end
    local context=reopened.context()
    if context.device_id~=restored.device_id or context.source_epoch~=restored.source_epoch then
        return nil,"outbox_scope_mismatch"
    end
    return reopened
end
return M
