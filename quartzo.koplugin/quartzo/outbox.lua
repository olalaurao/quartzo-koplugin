-- Plugin-owned delivery state, never canonical Reading Activity or Statistics.
-- No startup/lifecycle/network caller. Missing/corrupt state never re-enrolls.
local M = {}
local FILE = "quartzo_sync_state.sqlite3"
local CAP = 1000
local source_reviews=setmetatable({}, {__mode="k"})
local collection_passes=setmetatable({}, {__mode="k"})
local rejection_reviews=setmetatable({}, {__mode="k"})
local generation_reviews=setmetatable({}, {__mode="k"})
local schema_reviews=setmetatable({}, {__mode="k"})
local EARLIEST,LATEST=-62135596800,253402300799
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
    source="(id INTEGER PRIMARY KEY CHECK(id=1),volume TEXT NOT NULL,inode TEXT NOT NULL,"
        .."book_sequence TEXT NOT NULL,first_event TEXT NOT NULL,last_event TEXT NOT NULL,history_boundary TEXT NOT NULL)",
    progress="(id INTEGER PRIMARY KEY CHECK(id=1),ack_watermark TEXT,scan_before TEXT)",
}
local function definition(name,version)
    if name=="review" and version==3 then
        return definitions.review:gsub("PRIMARY KEY", "resolved INTEGER NOT NULL DEFAULT 0 CHECK(resolved IN(0,1)),PRIMARY KEY",1)
    end
    return definitions[name]
end
local source_fields={"volume","inode","book_sequence","first_event","last_event","history_boundary"}
local function update_source(conn,checkpoint)
    execute(conn,"UPDATE source SET volume=?,inode=?,book_sequence=?,first_event=?,last_event=?,history_boundary=? WHERE id=1",
        checkpoint.volume,checkpoint.inode,checkpoint.book_sequence,
        checkpoint.first_event,checkpoint.last_event,checkpoint.history_boundary)
end
local function tables(version)
    if version==3 then return {"identity","pending","review","source","progress"} end
    return version==2 and {"identity","pending","review","source"} or {"identity","pending","review"}
end
local function create_schema(conn, prefix, version)
    check(prefix=="" or prefix=="recovery.")
    for _,name in ipairs(tables(version)) do
        conn:exec("CREATE TABLE "..prefix..name..definition(name,version))
    end
end
local function check_schema(conn,version)
    local indexes={sqlite_autoindex_pending_1="pending",sqlite_autoindex_review_1="review"}
    local objects=conn:prepare("SELECT name,type,tbl_name,"
        .."CASE WHEN typeof(sql)='text' AND length(CAST(sql AS BLOB))<=1024 THEN sql ELSE NULL END "
        .."FROM sqlite_master LIMIT 8")
    local seen={}
    for _=1,8 do
        local row=objects:step()
        if not row then break end
        local name=row[1]
        check(not seen[name])
        if definitions[name] and (name~="source" or version>=2) and (name~="progress" or version==3) then
            check(row[2]=="table" and row[3]==name and row[4]=="CREATE TABLE "..name..definition(name,version))
        else
            check(indexes[name] and row[2]=="index" and row[3]==indexes[name] and row[4]==nil)
        end
        seen[row[1]]=true
    end
    objects:close()
    for _,name in ipairs({"identity","pending","review","sqlite_autoindex_pending_1","sqlite_autoindex_review_1"}) do
        check(seen[name])
    end
    if version>=2 then check(seen.source) end
    if version==3 then check(seen.progress) end
end
local function watermark(value)
    if value==nil then return nil end
    check(type(value)=="string" and #value<=13 and value:match("^%-?%d+$"))
    local n=tonumber(value)
    check(integer(n) and n>=EARLIEST and n<=LATEST and string.format("%.0f",n)==value)
    return n
end
local function progress(conn,version)
    if version~=3 then return {} end
    check(tonumber(conn:rowexec("SELECT COUNT(*) FROM (SELECT 1 FROM progress LIMIT 2)"))==1)
    local row=query(conn,"SELECT "..bounded("ack_watermark",13)..","..bounded("scan_before",13)
        ..",typeof(ack_watermark),typeof(scan_before) FROM progress WHERE id=1")
    check(row~=nil)
    for index=1,2 do check(row[index+2]=="null" or (row[index+2]=="text" and row[index]~=nil)) end
    local result={ack=watermark(row[1]),scanned=watermark(row[2])}
    check(not result.ack or (result.scanned and result.ack<=result.scanned))
    return result
end
local function set_progress(conn,ack,scanned)
    execute(conn,"UPDATE progress SET ack_watermark=?,scan_before=? WHERE id=1",
        ack and string.format("%.0f",ack) or nil,scanned and string.format("%.0f",scanned) or nil)
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
    local version=tonumber(conn:rowexec("PRAGMA user_version"))
    check(version==1 or version==2 or version==3, "unsupported_outbox_schema")
    check(conn:rowexec("PRAGMA quick_check(1)") == "ok", "invalid_outbox_state")
    check_schema(conn,version)
    check(tonumber(conn:rowexec("SELECT COUNT(*) FROM (SELECT 1 FROM identity LIMIT 2)"))==1)
    local row = query(conn, "SELECT "..bounded("device_id",128)..","..bounded("source_epoch",128).." FROM identity WHERE id=1")
    check(row and scope(row[1]) and scope(row[2]))
    check(count(conn, "pending") + count(conn, "review") <= CAP, "outbox_capacity")
    local checkpoint
    if version>=2 then
        check(tonumber(conn:rowexec("SELECT COUNT(*) FROM (SELECT 1 FROM source LIMIT 2)"))==1)
        local columns={}
        for _,field in ipairs(source_fields) do columns[#columns+1]=bounded(field,104) end
        local saved=query(conn,"SELECT "..table.concat(columns,",").." FROM source WHERE id=1")
        check(saved~=nil)
        local value={}
        for index,field in ipairs(source_fields) do value[field]=saved[index] end
        checkpoint=require("quartzo/statistics").validate_source_checkpoint(value,version==3)
        check(checkpoint~=nil)
    end
    progress(conn,version)
    return {device_id=row[1], source_epoch=row[2],schema_version=version,source_checkpoint=checkpoint}
end
local errors = {invalid_outbox_state=true,unsupported_outbox_schema=true,unsupported_outbox_file=true,
    outbox_capacity=true,outbox_exists=true,outbox_missing=true,outbox_scope_mismatch=true,
    outbox_native_conflict=true,outbox_entropy_unavailable=true,unverified_reading_receipt=true,
    outbox_backup_missing=true,outbox_backup_changed=true,statistics_source_changed=true,
    statistics_source_unverifiable=true,statistics_source_review_required=true,statistics_busy=true,statistics_unavailable=true,
    statistics_read_failed=true,unsupported_statistics_schema=true,invalid_statistics_collection=true,
    invalid_statistics_event=true,invalid_statistics_data=true,outbox_collection_review_required=true,
    outbox_collection_changed=true,outbox_review_changed=true,outbox_source_not_settled=true,
    statistics_source_unchanged=true,statistics_source_reconciliation_required=true}
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
local function source_equal(a,b)
    check(a.schema_version==b.schema_version,"outbox_scope_mismatch")
    if a.source_checkpoint then
        check(b.source_checkpoint~=nil,"outbox_scope_mismatch")
        for _,field in ipairs(source_fields) do
            check(a.source_checkpoint[field]==b.source_checkpoint[field],"outbox_scope_mismatch")
        end
    end
end
local function inspect(codec, line, context)
    check(type(line) == "string" and #line <= 8192)
    local entry = codec.inspect_event(line)
    check(type(entry) == "table" and entry.canonical_ack == false)
    context_equal(entry, context)
    return entry
end
local function frontier(conn,context,codec)
    local saved=progress(conn,context.schema_version)
    local candidate=saved.scanned
    if not candidate then return nil end
    local stmt=conn:prepare("SELECT "..bounded("line",8192)..","..bounded("event_id",68)
        ..","..bounded("native_digest",64).." FROM pending LIMIT 1001")
    for i=1,CAP+1 do
        local row=stmt:step()
        if not row then break end
        check(i<=CAP,"outbox_capacity")
        local entry=inspect(codec,row[1],context)
        check(entry.event_id==row[2] and entry.native_digest==row[3])
        check(integer(entry.started_at_seconds))
        candidate=math.min(candidate,entry.started_at_seconds-1)
    end
    stmt:close()
    check(tonumber(conn:rowexec("SELECT COUNT(*) FROM review WHERE typeof(started_at)<>'integer' "
        .."OR typeof(resolved)<>'integer' OR resolved NOT IN(0,1)"))==0)
    local unresolved=conn:rowexec("SELECT MIN(started_at) FROM review WHERE resolved=0")
    if unresolved~=nil then candidate=math.min(candidate,tonumber(unresolved)-1) end
    return candidate>=EARLIEST and candidate or nil
end
local function unresolved_count(conn,version)
    if version~=3 then return count(conn,"review") end
    return tonumber(conn:rowexec("SELECT COUNT(*) FROM review WHERE resolved=0"))
end
local function same_batch(a,b)
    check(a.scanned_count==b.scanned_count and a.complete==b.complete
        and a.snapshot_schema_cookie==b.snapshot_schema_cookie
        and #a.event_lines==#b.event_lines and #a.rejections==#b.rejections,"outbox_collection_changed")
    for i,line in ipairs(a.event_lines) do check(line==b.event_lines[i],"outbox_collection_changed") end
    for i,row in ipairs(a.rejections) do
        local other=b.rejections[i]
        check(row.started_at==other.started_at and row.row_id==other.row_id,"outbox_collection_changed")
        for _,field in ipairs({"book_row_id","page","duration_seconds","total_pages"}) do
            check(row.integer_fields[field]==other.integer_fields[field],"outbox_collection_changed")
        end
        for j=1,5 do check(row.field_types[j]==other.field_types[j],"outbox_collection_changed") end
    end
    if a.next_scan or b.next_scan then
        check(a.next_scan and b.next_scan and a.next_scan.started_at==b.next_scan.started_at
            and a.next_scan.row_id==b.next_scan.row_id,"outbox_collection_changed")
    end
end
local valid_review_types={integer=true,real=true,text=true,blob=true,["null"]=true}
local function verify_review(row)
    check(integer(tonumber(row[1])) and type(row[6])=="string" and #row[6]<=39)
    local types={}
    for value in row[6]:gmatch("[^,]+") do check(valid_review_types[value]);types[#types+1]=value end
    check(#types==5 and types[3]=="integer" and table.concat(types,",")==row[6])
    for j,source in ipairs({1,2,4,5}) do
        local value=row[j+1]
        check(type(value)=="string" and #value<=20)
        if types[source]=="integer" then check(value:match("^%-?%d+$"))
        else check(value=="") end
    end
end
local function verify_contents(conn, codec, context)
    check(type(codec)=="table" and type(codec.inspect_event)=="function")
    -- Bind a manual review to the selected bytes, not just its row counts.
    -- Entries are bounded and sorted; hashes come from the existing wire codec.
    -- Review descriptors contain only integers and fixed type names, so these
    -- separators are unambiguous. No private event bodies enter this key.
    local selection={"quartzo-outbox-review-v1"}
    if context.source_checkpoint then
        selection[#selection+1]="source-v2"
        for _,field in ipairs(source_fields) do selection[#selection+1]=context.source_checkpoint[field] end
    end
    if context.schema_version==3 then
        local saved=progress(conn,3)
        selection[#selection+1]="progress-v3:"..(saved.ack and string.format("%.0f",saved.ack) or "")
            ..":"..(saved.scanned and string.format("%.0f",saved.scanned) or "")
    end
    local stmt=conn:prepare("SELECT "..bounded("event_id",68)..","..bounded("line",8192)
        ..","..bounded("native_digest",64).." FROM pending ORDER BY event_id LIMIT 1001")
    for i=1,CAP+1 do
        local row=stmt:step()
        if not row then break end
        check(i<=CAP,"outbox_capacity")
        local entry=inspect(codec,row[2],context)
        check(entry.event_id==row[1] and entry.native_digest==row[3])
        selection[#selection+1]="p:"..entry.event_id..":"..entry.line_digest
    end
    stmt:close()
    stmt=conn:prepare("SELECT CASE WHEN typeof(started_at)='integer' THEN started_at ELSE NULL END,"
        ..bounded("book_id",20)..","..bounded("page",20)..","..bounded("duration",20)..","
        ..bounded("pages",20)..","..bounded("types",39)..(context.schema_version==3
            and ",CASE WHEN typeof(resolved)='integer' THEN resolved ELSE NULL END" or "").." FROM review "
        .."ORDER BY started_at,book_id,page,duration,pages,types LIMIT 1001")
    for i=1,CAP+1 do
        local row=stmt:step()
        if not row then break end
        check(i<=CAP,"outbox_capacity")
        verify_review(row)
        row[1]=string.format("%.0f",tonumber(row[1]))
        if context.schema_version==3 then
            local resolved=tonumber(row[7])
            check(resolved==0 or resolved==1)
            row[7]=tostring(resolved)
        end
        selection[#selection+1]="r:"..table.concat(row,":")
    end
    stmt:close()
    return table.concat(selection,"\n")
end
local function check_review(conn, context, expected, selection)
    if expected == nil then return end
    check(type(expected)=="table" and scope(expected.device_id) and scope(expected.source_epoch)
        and integer(expected.pending) and expected.pending>=0
        and integer(expected.review) and expected.review>=0
        and expected.pending+expected.review<=CAP and expected.canonical_ack==false
        and type(expected.selection_key)=="string" and #expected.selection_key<=200000)
    check(expected.device_id==context.device_id and expected.source_epoch==context.source_epoch
        and expected.pending==count(conn,"pending") and expected.review==count(conn,"review")
        and expected.selection_key==selection,
        "outbox_backup_changed")
end
local function clone(conn, destination, runtime, context, expected)
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
        local current=own_schema(conn)
        context_equal(current,context)
        source_equal(current,context)
        local selection=verify_contents(conn,runtime.codec,context)
        check_review(conn,context,expected,selection)
        create_schema(conn,"recovery.",context.schema_version)
        for _,name in ipairs(tables(context.schema_version)) do
            conn:exec("INSERT INTO recovery."..name.." SELECT * FROM main."..name)
        end
        conn:exec("PRAGMA recovery.user_version="..context.schema_version)
        return {device_id=context.device_id,source_epoch=context.source_epoch,
            pending=count(conn,"pending"),review=count(conn,"review"),
            unresolved_review=unresolved_count(conn,context.schema_version),canonical_ack=false}
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
            local current=own_schema(conn)
            context_equal(current, context)
            source_equal(current,context)
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
                unresolved_review=unresolved_count(conn,context.schema_version),
                collection_supported=context.schema_version==3,
                upgrade_supported=context.schema_version==2,
                source_state=context.source_checkpoint and "enrolled" or "review_required",
                source_watermark=progress(conn,context.schema_version).ack, canonical_ack=false}
        end)
    end
    function api.check_source(statistics_path)
        return access(false,function()
            if not context.source_checkpoint then return {source_state="review_required",canonical_ack=false} end
            local result,code=require("quartzo/statistics").with_source_snapshot(statistics_path,context.source_checkpoint,runtime,
                function() return {source_state="matches_enrollment",canonical_ack=false} end)
            if not result then error(code,0) end
            return result
        end)
    end
    function api.review_source_change(statistics_path)
        return access(false,function()
            check(context.source_checkpoint~=nil,"statistics_source_review_required")
            local preview,code=require("quartzo/statistics").review_source(statistics_path,runtime,context.source_checkpoint)
            if not preview then error(code,0) end
            source_reviews[preview.review]={name=name,context=context}
            return preview
        end)
    end
    function api.preview_source(statistics_path,observed_at_utc,after,limit)
        return access(false,function()
            check(context.source_checkpoint~=nil,"statistics_source_review_required")
            -- Reuse the sole collector inside the SAME guarded native snapshot.
            -- Scope comes only from this existing queue, never caller fields.
            -- This bounded dry run stages nothing and advances no checkpoint.
            local batch,code=require("quartzo/collector").collect_reviewed(statistics_path,
                {device_id=context.device_id,source_epoch=context.source_epoch,
                    observed_at_utc=observed_at_utc,after=after,limit=limit},
                codec,context.source_checkpoint,runtime)
            if not batch then error(code,0) end
            return batch
        end)
    end
    function api.renew_source(review)
        return access(true,function(conn)
            check(context.source_checkpoint~=nil,"statistics_source_review_required")
            local reviewed=source_reviews[review]
            check(reviewed and reviewed.name==name,"statistics_source_review_required")
            context_equal(reviewed.context,context)
            source_equal(reviewed.context,context)
            source_reviews[review]=nil
            local renewed,code=require("quartzo/statistics").accept_source_review(review,function(checkpoint)
                -- Refresh only native file continuity after explicit review.
                -- A reset/different history cannot silently mint an epoch or
                -- move the original import boundary through this operation.
                for _,field in ipairs(source_fields) do
                    if field~="volume" and field~="inode" then
                        check(checkpoint[field]==context.source_checkpoint[field],"statistics_source_changed")
                    end
                end
                return transaction(conn,function()
                    local current=own_schema(conn)
                    context_equal(current,context)
                    source_equal(current,context)
                    execute(conn,"UPDATE source SET volume=?,inode=? WHERE id=1",checkpoint.volume,checkpoint.inode)
                    return handle(name,runtime,own_schema(conn))
                end)
            end)
            if not renewed then error(code,0) end
            return renewed
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
    local function stage_batch(conn,batch,coverage,before_stage,strengthened)
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
                    check(valid_review_types[value])
                    types[j]=value
                end
                values[#values+1] = table.concat(types,",")
                -- Accept only descriptors that the same recovery owner can read.
                -- A malformed review must not poison already selected neighbors.
                verify_review(values)
                reviews[i]=values
            end
            return transaction(conn,function()
                local current=own_schema(conn)
                context_equal(current,context)
                source_equal(current,context)
                if before_stage then before_stage() end
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
                if context.schema_version==3 then
                    local saved=progress(conn,3)
                    if coverage then saved.scanned=math.max(saved.scanned or EARLIEST,coverage) end
                    set_progress(conn,saved.ack,saved.scanned)
                    if strengthened then
                        update_source(conn,strengthened)
                    end
                end
                return {pending=pending,review=review,source_reopen_required=strengthened~=nil,canonical_ack=false}
            end)
    end
    function api.stage(batch)
        return access(true,function(conn)
            check(context.schema_version~=3,"outbox_collection_review_required")
            return stage_batch(conn,batch)
        end)
    end
    local function read_collection(saved,observed_at)
        local observed=codec.utc_seconds(observed_at)
        check(integer(observed),"invalid_statistics_collection")
        check(not saved.observed_seconds or observed>=saved.observed_seconds,"outbox_collection_changed")
        local batch,code=require("quartzo/collector").collect_reviewed(saved.path,
            {device_id=context.device_id,source_epoch=context.source_epoch,observed_at_utc=observed_at,
                from_started_at=saved.lower,after=saved.after,limit=saved.limit},
            codec,context.source_checkpoint,runtime)
        if not batch then error(code,0) end
        if saved.cookie then check(saved.cookie==batch.snapshot_schema_cookie,"outbox_collection_changed") end
        return batch
    end
    local function pass_preview(pass,saved,batch,observed)
        saved.batch,saved.observed,saved.cookie=batch,observed,batch.snapshot_schema_cookie
        saved.observed_seconds=codec.utc_seconds(observed)
        saved.ready=true
        return {pass=pass,scanned_count=batch.scanned_count,event_count=#batch.event_lines,
            review_count=#batch.rejections,complete=batch.complete,clock_reset=saved.clock_reset or false,canonical_ack=false}
    end
    function api.review_collection(statistics_path,observed_at_utc,limit,mode)
        return access(false,function(conn)
            check(context.schema_version==3,"outbox_collection_review_required")
            check(mode==nil or mode=="all_history","invalid_statistics_collection")
            local pass={}
            local saved={name=name,context=context,path=statistics_path,
                lower=progress(conn,3).ack,limit=limit,restart=mode=="all_history"}
            local observed=codec.utc_seconds(observed_at_utc)
            check(integer(observed),"invalid_statistics_collection")
            if saved.lower and observed<saved.lower then saved.restart,saved.clock_reset=true,true end
            if saved.restart then saved.lower=nil end
            local batch=read_collection(saved,observed_at_utc)
            collection_passes[pass]=saved
            return pass_preview(pass,saved,batch,observed_at_utc)
        end)
    end
    local function checked_pass(pass,conn)
        local saved=collection_passes[pass]
        check(saved and saved.name==name and context.schema_version==3,"outbox_collection_review_required")
        context_equal(saved.context,context)
        source_equal(saved.context,context)
        local ack=progress(conn,3).ack
        check(saved.lower==nil or (ack~=nil and saved.lower<=ack),"outbox_collection_changed")
        return saved
    end
    function api.stage_collection(pass)
        return access(true,function(conn)
            local saved=checked_pass(pass,conn)
            check(saved.ready,"outbox_collection_review_required")
            local current=read_collection(saved,saved.observed)
            same_batch(saved.batch,current)
            local last=current.next_scan and current.next_scan.started_at
            local coverage=last and last-1
            if coverage and (coverage<EARLIEST or coverage>LATEST) then coverage=nil end
            local strengthened
            if context.source_checkpoint.first_event=="" and current.scanned_count>0 then
                local code
                strengthened,code=require("quartzo/statistics").strengthen_empty_source(saved.path,context.source_checkpoint,runtime)
                if not strengthened then error(code,0) end
            end
            local result=stage_batch(conn,current,coverage,function()
                checked_pass(pass,conn)
                if saved.restart then set_progress(conn,nil,nil) end -- Explicit rescan revokes progress, never grants ACK.
            end,strengthened)
            saved.after,saved.complete,saved.ready=current.next_scan,current.complete,false
            saved.restart=false
            if strengthened then collection_passes[pass]=nil end
            result.complete=current.complete
            return result
        end)
    end
    function api.next_collection(pass,observed_at_utc)
        return access(false,function(conn)
            local saved=checked_pass(pass,conn)
            check(not saved.ready and not saved.complete,"outbox_collection_review_required")
            return pass_preview(pass,saved,read_collection(saved,observed_at_utc),observed_at_utc)
        end)
    end
    local review_where="started_at=? AND book_id=? AND page=? AND duration=? AND pages=? AND types=?"
    function api.review_rejections(limit)
        limit=limit or 100
        if not integer(limit) or limit<1 or limit>100 then return nil,"invalid_outbox_state" end
        return access(false,function(conn)
            check(context.schema_version==3,"outbox_collection_review_required")
            local stmt=conn:prepare("SELECT started_at,"..bounded("book_id",20)..","..bounded("page",20)
                ..","..bounded("duration",20)..","..bounded("pages",20)..","..bounded("types",39)
                .." FROM review WHERE resolved=0 ORDER BY started_at,book_id,page,duration,pages,types LIMIT ?")
            stmt:bind(limit)
            local cases={}
            for _=1,limit do
                local row=stmt:step()
                if not row then break end
                verify_review(row)
                row[1]=tonumber(row[1])
                cases[#cases+1]=row
            end
            stmt:close()
            local token={}
            rejection_reviews[token]={name=name,context=context,cases=cases}
            return {review=token,count=#cases,remaining=unresolved_count(conn,3)-#cases,canonical_ack=false}
        end)
    end
    function api.resolve_rejections(token)
        return access(true,function(conn)
            local reviewed=rejection_reviews[token]
            check(reviewed and reviewed.name==name and context.schema_version==3,"outbox_review_changed")
            context_equal(reviewed.context,context)
            source_equal(reviewed.context,context)
            rejection_reviews[token]=nil
            return transaction(conn,function()
                local current=own_schema(conn)
                context_equal(current,context)
                source_equal(current,context)
                for _,row in ipairs(reviewed.cases) do
                    local saved=query(conn,"SELECT resolved FROM review WHERE "..review_where,unpack(row))
                    check(saved and tonumber(saved[1])==0,"outbox_review_changed")
                    execute(conn,"UPDATE review SET resolved=1 WHERE "..review_where.." AND resolved=0",unpack(row))
                    check(tonumber(conn:rowexec("SELECT changes()"))==1,"outbox_review_changed")
                end
                -- Keep descriptors for audit/replay. Resolution is neither ACK
                -- nor permission to delete Statistics or advance its watermark.
                return {resolved=#reviewed.cases,unresolved=unresolved_count(conn,3),
                    retained=count(conn,"review"),canonical_ack=false}
            end)
        end)
    end
    local function settled(conn)
        check(context.schema_version==3,"outbox_collection_review_required")
        check(count(conn,"pending")==0 and unresolved_count(conn,3)==0,"outbox_source_not_settled")
    end
    function api.review_new_generation(statistics_path)
        return access(false,function(conn)
            settled(conn)
            local statistics=require("quartzo/statistics")
            local same=statistics.with_source_snapshot(statistics_path,context.source_checkpoint,runtime,
                function() return true end)
            check(not same,"statistics_source_unchanged")
            local reviewed,code=statistics.review_source(statistics_path,runtime)
            if not reviewed then error(code,0) end
            -- A nonempty replacement might contain already imported history.
            -- Do not manufacture deduplication across a new epoch; reconcile it.
            check(not reviewed.has_history,"statistics_source_reconciliation_required")
            generation_reviews[reviewed.review]={name=name,context=context}
            return {review=reviewed.review,canonical_ack=false}
        end)
    end
    function api.begin_new_generation(token)
        return access(true,function(conn)
            settled(conn)
            local reviewed=generation_reviews[token]
            check(reviewed and reviewed.name==name,"statistics_source_review_required")
            context_equal(reviewed.context,context)
            source_equal(reviewed.context,context)
            generation_reviews[token]=nil
            local backup,code=api.backup()
            if not backup then error(code,0) end
            local changed,reason=require("quartzo/statistics").accept_source_review(token,function(checkpoint)
                check(checkpoint.first_event=="" and checkpoint.history_boundary=="",
                    "statistics_source_reconciliation_required")
                return transaction(conn,function()
                    local current=own_schema(conn)
                    context_equal(current,context)
                    source_equal(current,context)
                    settled(conn)
                    local epoch="qse_"..generated_device(runtime):sub(5)
                    execute(conn,"UPDATE identity SET source_epoch=? WHERE id=1",epoch)
                    update_source(conn,checkpoint)
                    conn:exec("DELETE FROM review") -- Settled records survive in the mandatory recovery copy.
                    set_progress(conn,nil,nil)
                    return {queue=handle(name,runtime,own_schema(conn)),backup_leaf=backup.backup_leaf,canonical_ack=false}
                end)
            end)
            if not changed then error(reason,0) end
            return changed
        end)
    end
    function api.review_upgrade(statistics_path)
        return access(false,function(conn)
            check(context.schema_version==2,"outbox_collection_review_required")
            verify_contents(conn,codec,context)
            local matches,code=require("quartzo/statistics").with_source_snapshot(statistics_path,
                context.source_checkpoint,runtime,function() return true end)
            if not matches then error(code,0) end
            local token={}
            schema_reviews[token]={name=name,context=context,path=statistics_path}
            return {review=token,canonical_ack=false}
        end)
    end
    function api.upgrade_queue(token)
        return access(true,function(conn)
            local reviewed=schema_reviews[token]
            check(reviewed and reviewed.name==name and context.schema_version==2,"outbox_collection_review_required")
            context_equal(reviewed.context,context)
            source_equal(reviewed.context,context)
            schema_reviews[token]=nil
            local matches,reason=require("quartzo/statistics").with_source_snapshot(reviewed.path,
                context.source_checkpoint,runtime,function() return true end)
            if not matches then error(reason,0) end
            local backup,code=api.backup()
            if not backup then error(code,0) end
            return transaction(conn,function()
                local current=own_schema(conn)
                context_equal(current,context)
                source_equal(current,context)
                verify_contents(conn,codec,context)
                conn:exec("ALTER TABLE review RENAME TO review_schema2")
                conn:exec("CREATE TABLE review"..definition("review",3))
                conn:exec("INSERT INTO review(started_at,book_id,page,duration,pages,types) "
                    .."SELECT started_at,book_id,page,duration,pages,types FROM review_schema2")
                conn:exec("DROP TABLE review_schema2")
                conn:exec("CREATE TABLE progress"..definition("progress",3))
                conn:exec("INSERT INTO progress VALUES(1,NULL,NULL)")
                conn:exec("PRAGMA user_version=3")
                return {queue=handle(name,runtime,own_schema(conn)),backup_leaf=backup.backup_leaf,canonical_ack=false}
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
                local current=own_schema(conn)
                context_equal(current,context)
                source_equal(current,context)
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
                local saved=progress(conn,context.schema_version)
                if context.schema_version==3 and removed>0 then
                    local next_ack=frontier(conn,context,codec)
                    if next_ack then saved.ack=math.max(saved.ack or EARLIEST,next_ack) end
                    set_progress(conn,saved.ack,saved.scanned)
                end
                return {removed=removed,review_retained=count(conn,"review"),source_watermark=saved.ack,canonical_ack=false}
            end)
        end)
    end
    return api
end

local function create(root, source_epoch, runtime, checkpoint)
    runtime=runtime or {}
    local ok,name=pcall(path,root)
    if not ok or (not checkpoint and not scope(source_epoch)) then return nil,"invalid_outbox_state" end
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
            local context={device_id=generated_device(runtime),source_epoch=source_epoch
                or ("qse_"..generated_device(runtime):sub(5)),schema_version=checkpoint and 3 or 1,
                source_checkpoint=checkpoint}
            create_schema(conn,"",context.schema_version)
            execute(conn,"INSERT INTO identity VALUES(1,?,?)",context.device_id,context.source_epoch)
            if checkpoint then
                execute(conn,"INSERT INTO source VALUES(1,?,?,?,?,?,?)",checkpoint.volume,checkpoint.inode,
                    checkpoint.book_sequence,checkpoint.first_event,checkpoint.last_event,checkpoint.history_boundary)
                conn:exec("INSERT INTO progress VALUES(1,NULL,NULL)")
            end
            conn:exec("PRAGMA user_version="..context.schema_version)
            return handle(name,runtime,context)
        end)
    end)
end
function M.create(root,source_epoch,runtime)
    -- Retained for existing explicit synthetic diagnostics, not production setup.
    return create(root,source_epoch,runtime)
end
local function enrollment_available(root,runtime)
    local ok,name=pcall(path,root)
    if not ok then return nil,"invalid_outbox_state" end
    local checked,exists=pcall(regular,name,runtime)
    if not checked then return nil,"unsupported_outbox_file" end
    if exists then return nil,"outbox_exists" end
    local listing,code=M.list_backups(root,runtime)
    if not listing then return nil,code end
    if #listing.backups>0 or listing.unsupported>0 then return nil,"outbox_recovery_review_required" end
    return true
end
function M.review_source(root,statistics_path,runtime)
    runtime=runtime or {}
    local ready,code=enrollment_available(root,runtime)
    if not ready then return nil,code end
    return require("quartzo/statistics").review_source(statistics_path,runtime)
end
function M.enroll(root,review,runtime)
    runtime=runtime or {}
    local ready,code=enrollment_available(root,runtime)
    if not ready then return nil,code end
    return require("quartzo/statistics").accept_source_review(review,function(checkpoint)
        return create(root,nil,runtime,checkpoint)
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
        local selection=verify_contents(conn,runtime.codec,context)
        return {device_id=context.device_id,source_epoch=context.source_epoch,
            pending=count(conn,"pending"),review=count(conn,"review"),
            unresolved_review=unresolved_count(conn,context.schema_version),selection_key=selection,canonical_ack=false}
    end)
end
function M.list_backups(root, runtime)
    runtime=runtime or {}
    local directory
    local ok,result=pcall(function()
        path(root)
        local fs=runtime.filesystem or require("libs/libkoreader-lfs")
        local iterator
        iterator,directory=fs.dir(root)
        check(type(iterator)=="function")
        local entries,visited,unsupported={},0,0
        for leaf in iterator,directory do
            visited=visited+1
            check(visited<=512,"outbox_recovery_list_limit")
            local own_leaf=type(leaf)=="string" and leaf:lower() or ""
            if own_leaf:match("^quartzo_sync_recovery_") then
                local valid,name=pcall(backup_path,root,leaf)
                if valid then
                    local info=(runtime.attributes or fs.symlinkattributes)(name)
                    if info and info.mode=="file" then
                        check(#entries<32,"outbox_recovery_list_limit")
                        local modified=info.modification
                        if type(modified)~="number" or modified~=modified or modified<0
                            or modified>9007199254740991 then modified=nil end
                        entries[#entries+1]={leaf=leaf,modified=modified}
                    else unsupported=unsupported+1 end
                else unsupported=unsupported+1 end
            elseif own_leaf~=FILE and own_leaf:match("^quartzo_sync_state[._-]") then
                -- Legacy state, orphan journals and preserved/partial primaries
                -- are evidence to review, never permission for a new identity.
                -- Discovery stays metadata-only and does not repair/open them.
                unsupported=unsupported+1
            end
        end
        table.sort(entries,function(a,b)
            if (a.modified or 0)~=(b.modified or 0) then return (a.modified or 0)>(b.modified or 0) end
            return a.leaf<b.leaf
        end)
        return {backups=entries,unsupported=unsupported,canonical_ack=false}
    end)
    if directory then pcall(function() directory:close() end) end
    if ok then return result end
    return nil,result=="outbox_recovery_list_limit" and result or "outbox_recovery_list_unavailable"
end
function M.restore(root, backup_leaf, runtime, expected)
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
        -- UI review is a precondition, not authority to mint an identity or ACK.
        -- Recheck under the copy transaction as well as before target creation.
        -- Validate before creating/attaching the destination; a malformed backup
        -- remains available for review and cannot silently become empty state.
        local selection=verify_contents(conn,runtime.codec,context)
        check_review(conn,context,expected,selection)
        return clone(conn,name,runtime,context,expected)
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
