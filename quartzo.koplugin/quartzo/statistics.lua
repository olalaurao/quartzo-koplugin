-- Short-lived read-only snapshots. Statistics remains the sole database owner.
local M = {}
local LIMIT = 100000
local schemas = {
    book = {
        {"id", "INTEGER", 0, nil, 1}, {"title", "TEXT", 0},
        {"authors", "TEXT", 0}, {"notes", "INTEGER", 0},
        {"last_open", "INTEGER", 0}, {"highlights", "INTEGER", 0},
        {"pages", "INTEGER", 0}, {"series", "TEXT", 0},
        {"language", "TEXT", 0}, {"md5", "TEXT", 0},
        {"total_read_time", "INTEGER", 0}, {"total_read_pages", "INTEGER", 0},
    },
    page_stat_data = {
        {"id_book", "INTEGER", 0}, {"page", "INTEGER", 1, "0"},
        {"start_time", "INTEGER", 1, "0"}, {"duration", "INTEGER", 1, "0"},
        {"total_pages", "INTEGER", 1, "0"},
    },
}

local function unsupported()
    error("unsupported_statistics_schema", 0)
end

local function check_columns(conn, name, expected)
    if conn:rowexec("SELECT type FROM sqlite_master WHERE name = '" .. name .. "'") ~= "table" then
        unsupported()
    end
    local stmt = conn:prepare("PRAGMA table_info(" .. name .. ")")
    for i, column in ipairs(expected) do
        local row = stmt:step()
        if not row or row[1] ~= i - 1 or row[2] ~= column[1]
            or row[3] ~= column[2] or row[4] ~= column[3]
            or row[5] ~= column[4] or row[6] ~= (column[5] or 0) then
            unsupported()
        end
    end
    if stmt:step() then unsupported() end
    stmt:close()
end

local function check_index(conn, table_name, name, unique, columns)
    -- All names are fixed constants, never user data or names returned by SQL.
    local indexes = conn:prepare("PRAGMA index_list(" .. table_name .. ")")
    local found = false
    for i = 1, 17 do
        local row = indexes:step()
        if not row then break end
        if i == 17 then unsupported() end
        if row[2] == name then
            if row[3] ~= unique or row[5] ~= 0 then unsupported() end
            found = true
        end
    end
    indexes:close()
    if not found then unsupported() end
    local stmt = conn:prepare("PRAGMA index_info(" .. name .. ")")
    for i, column in ipairs(columns) do
        local row = stmt:step()
        if not row or row[1] ~= i - 1 or row[3] ~= column then unsupported() end
    end
    if stmt:step() then unsupported() end
    stmt:close()
end

local function integer(value, maximum)
    value = tonumber(value)
    if not value or value < 0 or value > maximum or value % 1 ~= 0 then
        error("invalid_statistics_data", 0)
    end
    return value
end

function M.with_snapshot(path, sqlite, read)
    local conn
    local ok, result = pcall(function()
        sqlite = sqlite or require("lua-ljsqlite3/init")
        conn = sqlite.open(path, "ro") -- Never rely on SQ3's default (rwc).
        conn:set_busy_timeout(1000)
        conn:exec("BEGIN DEFERRED") -- One bounded, read-only snapshot until close.
        if tonumber(conn:rowexec("PRAGMA user_version")) ~= 20221111 then unsupported() end
        for _, name in ipairs({"book", "page_stat_data"}) do
            check_columns(conn, name, schemas[name])
        end
        check_index(conn, "book", "book_title_authors_md5", 1, {"title", "authors", "md5"})
        check_index(conn, "page_stat_data", "sqlite_autoindex_page_stat_data_1", 1,
            {"id_book", "page", "start_time"})
        check_index(conn, "page_stat_data", "page_stat_data_start_time", 0, {"start_time"})
        local fk = conn:prepare("PRAGMA foreign_key_list(page_stat_data)")
        local relation = fk:step()
        if not relation or relation[3] ~= "book" or relation[4] ~= "id_book"
            or relation[5] ~= "id" or fk:step() then unsupported() end
        fk:close()
        return read(conn)
    end)
    -- SQ3 closes all of its remaining prepared statements, including on error.
    if conn then
        local closed = pcall(conn.close, conn)
        if not closed then return nil, "statistics_read_failed" end
    end
    if ok then return result end
    if result == "unsupported_statistics_schema" or result == "invalid_statistics_data"
        or result == "invalid_statistics_event" or result == "invalid_statistics_collection"
        or result == "statistics_source_changed" or result == "statistics_source_unverifiable" then
        return nil, result
    end
    -- SDK errors may contain private paths/SQL. Expose only fixed categories.
    local message = tostring(result)
    if message:find("ljsqlite3%[busy%]") or message:find("ljsqlite3%[locked%]")
        or message:find("database is locked", 1, true) then
        return nil, "statistics_busy"
    end
    return nil, "statistics_unavailable"
end

function M.probe(path, sqlite)
    return M.with_snapshot(path, sqlite, function(conn)
        local books = integer(conn:rowexec(
            "SELECT COUNT(*) FROM (SELECT 1 FROM book LIMIT 100001)"), LIMIT + 1)
        local events = integer(conn:rowexec(
            "SELECT COUNT(*) FROM (SELECT 1 FROM page_stat_data LIMIT 100001)"), LIMIT + 1)
        local first = conn:rowexec("SELECT start_time FROM page_stat_data "
            .. "INDEXED BY page_stat_data_start_time ORDER BY start_time ASC LIMIT 1")
        local last = conn:rowexec("SELECT start_time FROM page_stat_data "
            .. "INDEXED BY page_stat_data_start_time ORDER BY start_time DESC LIMIT 1")
        if events > 0 then
            first = integer(first, 253402300799)
            last = integer(last, 253402300799)
            if first > last then error("invalid_statistics_data", 0) end
        elseif first ~= nil or last ~= nil then
            error("invalid_statistics_data", 0)
        end
        return {
            schema_version = 20221111, count_limit = LIMIT,
            book_count = math.min(books, LIMIT), book_count_limited = books > LIMIT,
            event_count = math.min(events, LIMIT), event_count_limited = events > LIMIT,
            first_started_at = first, last_started_at = last,
        }
    end)
end

-- Statistics has no intrinsic database-generation UUID. These are conservative
-- continuity guards for an EXPLICITLY reviewed enrollment, never an inferred
-- generation, event watermark, backfill permission or canonical receipt.
local source_fields={"volume","inode","book_sequence","first_event","last_event","history_boundary"}
local source_reviews=setmetatable({}, {__mode="k"})
local function source_check(ok, code)
    if not ok then error(code or "statistics_source_unverifiable",0) end
end
local function native_number(value)
    -- The actual SQ3 SDK returns INTEGER as int64_t cdata. Reject values outside
    -- the exact-double range before serializing; test bridge numbers are not its ABI.
    if type(value)=="cdata" then value=tonumber(value) end
    source_check(type(value)=="number" and value==value and value%1==0
        and math.abs(value)<=9007199254740991)
    return string.format("%.0f",value)
end
local function native_file(path,runtime)
    local attributes=runtime.attributes or require("libs/libkoreader-lfs").symlinkattributes
    local info=attributes(path)
    source_check(info and info.mode=="file")
    local volume,inode=native_number(info.dev),native_number(info.ino)
    source_check(info.dev>=0 and info.ino>0)
    return volume,inode
end
local function sequence(conn)
    local stmt=conn:prepare("SELECT CASE WHEN typeof(seq)='integer' THEN seq ELSE NULL END "
        .."FROM sqlite_sequence WHERE name='book' LIMIT 2")
    local row=stmt:step()
    source_check(not row or not stmt:step())
    stmt:close()
    if not row then return "0" end
    local value=row[1]
    local result=native_number(value)
    source_check(tonumber(value)>=0)
    return result
end
local projection="CASE WHEN typeof(id_book)='integer' THEN id_book ELSE NULL END,"
    .."CASE WHEN typeof(page)='integer' THEN page ELSE NULL END,"
    .."CASE WHEN typeof(start_time)='integer' THEN start_time ELSE NULL END,"
    .."CASE WHEN typeof(duration)='integer' THEN duration ELSE NULL END,"
    .."CASE WHEN typeof(total_pages)='integer' THEN total_pages ELSE NULL END"
local function anchor(row)
    if not row then return "" end
    local values={}
    for i=1,5 do values[i]=native_number(row[i]) end
    return table.concat(values,",")
end
local function parse_anchor(value)
    source_check(type(value)=="string" and #value<=104)
    if value=="" then return nil end
    local values={}
    for part in value:gmatch("[^,]+") do
        source_check(part:match("^%-?%d+$"))
        local n=tonumber(part)
        source_check(native_number(n)==part)
        values[#values+1]=n
    end
    source_check(#values==5 and anchor(values)==value)
    return values
end
function M.validate_source_checkpoint(value)
    local ok,result=pcall(function()
        source_check(type(value)=="table")
        local copied,allowed={},{}
        for _,key in ipairs(source_fields) do
            source_check(type(value[key])=="string")
            copied[key],allowed[key]=value[key],true
        end
        for key in pairs(value) do source_check(allowed[key]) end
        for _,key in ipairs({"volume","inode","book_sequence"}) do
            local field=copied[key]
            source_check(#field<=16 and field:match("^%d+$") and native_number(tonumber(field))==field)
        end
        source_check(tonumber(copied.inode)>0)
        local first,last=parse_anchor(copied.first_event),parse_anchor(copied.last_event)
        source_check((first==nil)==(last==nil))
        if first then
            local field=copied.history_boundary
            source_check(#field<=17 and field:match("^%-?%d+$") and native_number(tonumber(field))==field
                and tonumber(field)>=first[3] and tonumber(field)>=last[3])
        else source_check(copied.history_boundary=="") end
        return copied
    end)
    if ok then return result end
    return nil,"statistics_source_unverifiable"
end
local function checkpoint_key(value)
    local parts={}
    for _,key in ipairs(source_fields) do parts[#parts+1]=value[key] end
    return table.concat(parts,"|")
end
local function source_snapshot(path,runtime,read)
    local ok,volume,inode=pcall(native_file,path,runtime)
    if not ok then return nil,"statistics_source_unverifiable" end
    local result,code=M.with_snapshot(path,runtime.sqlite,function(conn)
        return read(conn,volume,inode)
    end)
    if not result then return nil,code end
    local checked,after_volume,after_inode=pcall(native_file,path,runtime)
    if not checked then return nil,"statistics_source_unverifiable" end
    if after_volume~=volume or after_inode~=inode then return nil,"statistics_source_changed" end
    return result
end
local function check_anchors(conn,checkpoint)
    source_check(tonumber(sequence(conn))>=tonumber(checkpoint.book_sequence),"statistics_source_changed")
    for _,saved in ipairs({checkpoint.first_event,checkpoint.last_event}) do
        local values=parse_anchor(saved)
        if values then
            local stmt=conn:prepare("SELECT "..projection.." FROM page_stat_data "
                .."WHERE id_book=? AND page=? AND start_time=?")
            stmt:bind(values[1],values[2],values[3])
            local actual=anchor(stmt:step())
            stmt:close()
            source_check(actual==saved,"statistics_source_changed")
        end
    end
end
local function capture_source(path,runtime,previous)
    return source_snapshot(path,runtime,function(conn,volume,inode)
        if previous then
            check_anchors(conn,previous)
            local refreshed={}
            for _,field in ipairs(source_fields) do refreshed[field]=previous[field] end
            refreshed.volume,refreshed.inode=volume,inode
            return refreshed -- Keep the original history boundary and anchors.
        end
        local function edge(order)
            local stmt=conn:prepare("SELECT "..projection.." FROM page_stat_data "
                .."INDEXED BY sqlite_autoindex_page_stat_data_1 ORDER BY id_book "..order
                ..",page "..order..",start_time "..order.." LIMIT 1")
            local value=anchor(stmt:step())
            stmt:close()
            return value
        end
        local boundary=conn:rowexec("SELECT start_time FROM page_stat_data "
            .."INDEXED BY page_stat_data_start_time ORDER BY start_time DESC LIMIT 1")
        local value={volume=volume,inode=inode,book_sequence=sequence(conn),
            first_event=edge("ASC"),last_event=edge("DESC"),
            history_boundary=boundary~=nil and native_number(boundary) or ""}
        local checked=M.validate_source_checkpoint(value)
        source_check(checked~=nil)
        return checked
    end)
end
function M.review_source(path,runtime,previous)
    runtime=runtime or {}
    if previous then
        local checked,code=M.validate_source_checkpoint(previous)
        if not checked then return nil,code end
        -- An enrollment made against empty history has no retained native
        -- witness for a moved/replaced file. Do not guess continuity later.
        if checked.first_event=="" then return nil,"statistics_source_unverifiable" end
        previous=checked
    end
    local captured,code=capture_source(path,runtime,previous)
    if not captured then return nil,code end
    local token={}
    source_reviews[token]={path=path,runtime=runtime,checkpoint=captured,previous=previous}
    return {review=token,has_history=captured.history_boundary~="",
        history_boundary=tonumber(captured.history_boundary),canonical_ack=false}
end
function M.accept_source_review(token,accept)
    local reviewed=source_reviews[token]
    if not reviewed or type(accept)~="function" then return nil,"statistics_source_review_required" end
    source_reviews[token]=nil -- A failed/changed review must be repeated explicitly.
    local current,code=capture_source(reviewed.path,reviewed.runtime,reviewed.previous)
    if not current then return nil,code end
    if checkpoint_key(current)~=checkpoint_key(reviewed.checkpoint) then
        return nil,"statistics_source_changed"
    end
    return accept(current)
end
function M.with_source_snapshot(path,expected,runtime,read)
    runtime=runtime or {}
    local checkpoint,code=M.validate_source_checkpoint(expected)
    if not checkpoint then return nil,code end
    return source_snapshot(path,runtime,function(conn,volume,inode)
        source_check(volume==checkpoint.volume and inode==checkpoint.inode,"statistics_source_changed")
        check_anchors(conn,checkpoint)
        return read(conn)
    end)
end

return M
