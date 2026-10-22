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
    check(type(root) == "string" and #root > 0 and not root:find("%z"))
    return root .. "/" .. FILE
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
    local row = query(conn, "SELECT device_id,source_epoch FROM identity WHERE id=1")
    check(row and scope(row[1]) and scope(row[2]))
    check(count(conn, "pending") + count(conn, "review") <= CAP, "outbox_capacity")
    return {device_id=row[1], source_epoch=row[2]}
end
local errors = {invalid_outbox_state=true,unsupported_outbox_schema=true,unsupported_outbox_file=true,
    outbox_capacity=true,outbox_exists=true,outbox_missing=true,outbox_scope_mismatch=true,
    outbox_native_conflict=true,outbox_entropy_unavailable=true,unverified_reading_receipt=true}
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
        configured(conn)
        return transaction(conn,function()
            check(tonumber(conn:rowexec("PRAGMA user_version"))==0,"outbox_exists")
            check(tonumber(conn:rowexec("SELECT COUNT(*) FROM sqlite_master"))==0,"outbox_exists")
            local context={device_id=generated_device(runtime),source_epoch=source_epoch}
            conn:exec("CREATE TABLE identity(id INTEGER PRIMARY KEY CHECK(id=1), device_id TEXT NOT NULL,source_epoch TEXT NOT NULL)")
            conn:exec("CREATE TABLE pending(event_id TEXT PRIMARY KEY,line TEXT NOT NULL,native_digest TEXT NOT NULL)")
            conn:exec("CREATE TABLE review(started_at INTEGER NOT NULL,book_id TEXT NOT NULL,page TEXT NOT NULL,"
                .. "duration TEXT NOT NULL,pages TEXT NOT NULL,types TEXT NOT NULL,"
                .. "PRIMARY KEY(started_at,book_id,page,duration,pages,types))")
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
return M
