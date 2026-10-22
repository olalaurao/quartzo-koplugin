-- A short-lived diagnostic snapshot. Statistics remains the sole database owner.
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

function M.probe(path, sqlite)
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
    -- SQ3 closes all of its remaining prepared statements, including on error.
    if conn then
        local closed = pcall(conn.close, conn)
        if not closed then return nil, "statistics_read_failed" end
    end
    if ok then return result end
    if result == "unsupported_statistics_schema" or result == "invalid_statistics_data" then
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

return M
