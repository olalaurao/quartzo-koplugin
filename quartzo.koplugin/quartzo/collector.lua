-- Phase C only: bounded native snapshots, no storage, ACK, networking or hooks.
local Statistics = require("quartzo/statistics")
local M = {}
local MAX = 9007199254740991
local function integer(value, low, high)
    return type(value) == "number" and value == value and value % 1 == 0
        and value >= low and value <= high
end
local function check(ok, code)
    if not ok then error(code or "invalid_statistics_collection", 0) end
end
local function scope(value)
    return type(value) == "string" and #value >= 1 and #value <= 128
        and not value:find("[^A-Za-z0-9_-]")
end
local function bound(limit)
    limit = limit or 50
    check(integer(limit, 1, 100))
    return limit
end
-- Only a bounded native digest is projected. Titles, authors, paths, annotations
-- and Reader identifiers never enter event bytes or this metadata projection.
local BOOK = "SELECT id, CASE WHEN typeof(md5) = 'text' "
    .. "AND length(CAST(md5 AS BLOB)) = 32 THEN md5 ELSE NULL END FROM book "
local function metadata(row, id)
    local item = {book_row_id=id, missing_book=row == nil}
    if row then
        local md5 = row[2]
        if type(md5) == "string" and #md5 == 32 and not md5:find("[^a-fA-F0-9]") then
            item.md5 = md5:lower()
        end
    end
    return item
end
local function group(result, item)
    result.books[#result.books+1] = item
    if item.md5 then
        local ids = result.md5_groups[item.md5] or {}
        result.md5_groups[item.md5] = ids
        ids[#ids+1] = item.book_row_id
    end
end

function M.books(path, options, sqlite)
    return Statistics.with_snapshot(path, sqlite, function(conn)
        check(type(options) == "table")
        local limit, after = bound(options.limit), options.after_book_row_id or 0
        check(integer(after, 0, MAX))
        local stmt = conn:prepare(BOOK .. "WHERE id > ? ORDER BY id LIMIT ?")
        stmt:bind(after, limit+1)
        local result = {books={}, md5_groups={}, complete=false, canonical_ack=false}
        for i = 1, limit do
            local row = stmt:step()
            if not row then result.complete=true; break end
            local id = tonumber(row[1])
            check(integer(id, 1, MAX), "invalid_statistics_event")
            group(result, metadata(row, id))
            result.next_book_row_id = id
        end
        if not result.complete then result.complete = stmt:step() == nil end
        stmt:close()
        return result
    end)
end

function M.collect(path, options, codec, sqlite)
    return Statistics.with_snapshot(path, sqlite, function(conn)
        check(type(options) == "table" and type(codec) == "table"
            and type(codec.encode_event) == "function")
        local limit = bound(options.limit)
        local device, epoch, observed = options.device_id, options.source_epoch, options.observed_at_utc
        check(scope(device) and scope(epoch) and type(observed) == "string" and #observed <= 32)
        local lower, after = options.from_started_at, options.after
        if lower ~= nil then check(integer(lower, -62135596800, 253402300799)) end
        if after ~= nil then
            check(type(after) == "table" and after.device_id == device and after.source_epoch == epoch
                and after.from_started_at == lower
                and integer(after.started_at, -62135596800, 253402300799)
                and integer(after.row_id, -MAX, MAX)
                and (lower == nil or after.started_at >= lower))
            -- rowid is a transient index tie-breaker, NEVER native event identity
            -- or an acknowledged/persisted watermark. Reopen overlap passes from
            -- their time boundary; rowids may change after database maintenance.
            after = {started_at=after.started_at, row_id=after.row_id}
        end
        local sql = "SELECT rowid, id_book, page, start_time, duration, total_pages, "
            .. "strftime('%Y-%m-%dT%H:%M:%S.000Z', start_time, 'unixepoch'), "
            .. "typeof(id_book), typeof(page), typeof(start_time), typeof(duration), typeof(total_pages) "
            .. "FROM page_stat_data INDEXED BY page_stat_data_start_time"
        local stmt, remaining, following = nil, limit+1, after ~= nil
        if after then
            -- SQLite's row-value (time,rowid)> predicate can rescan an entire
            -- equal-time group. Two index seeks bound work without a new index.
            stmt = conn:prepare(sql .. " WHERE start_time = ? AND rowid > ? ORDER BY rowid LIMIT ?")
            stmt:bind(after.started_at, after.row_id, remaining)
        elseif lower ~= nil then
            stmt = conn:prepare(sql .. " WHERE start_time >= ? ORDER BY start_time, rowid LIMIT ?")
            stmt:bind(lower, remaining)
        else
            stmt = conn:prepare(sql .. " ORDER BY start_time, rowid LIMIT ?")
            stmt:bind(remaining)
        end
        local function next_row()
            if remaining == 0 then return nil end
            local row = stmt:step()
            if not row and following then
                following = false
                stmt:close()
                stmt = conn:prepare(sql .. " WHERE start_time > ? ORDER BY start_time, rowid LIMIT ?")
                stmt:bind(after.started_at, remaining)
                row = stmt:step()
            end
            if row then remaining = remaining-1 end
            return row
        end
        local result = {event_lines={}, books={}, md5_groups={}, complete=false, canonical_ack=false}
        local seen, bytes = {}, 0
        for i = 1, limit do
            local row = next_row()
            if not row then result.complete=true; break end
            for j = 8, 12 do check(row[j] == "integer", "invalid_statistics_event") end
            local id, page, started = tonumber(row[2]), tonumber(row[3]), tonumber(row[4])
            local duration, pages, row_id = tonumber(row[5]), tonumber(row[6]), tonumber(row[1])
            check(integer(id, 1, MAX) and integer(page, 1, MAX) and integer(pages, 1, MAX)
                and integer(started, -62135596800, 253402300799) and integer(duration, 1, 86400)
                and integer(row_id, -MAX, MAX), "invalid_statistics_event")
            local line = codec.encode_event({schema_version=1, source="koreader_statistics",
                device_id=device, source_epoch=epoch, book_row_id=id, page=page,
                started_at_utc=row[7], duration_seconds=duration, total_pages=pages,
                observed_at_utc=observed, source_schema_version="20221111"})
            check(type(line) == "string", "invalid_statistics_event")
            bytes = bytes + #line + 1
            check(bytes <= 524288, "invalid_statistics_event")
            result.event_lines[#result.event_lines+1] = line
            result.next_scan = {device_id=device, source_epoch=epoch, from_started_at=lower,
                started_at=started, row_id=row_id}
            if not seen[id] then
                local book = conn:prepare(BOOK .. "WHERE id = ? LIMIT 1")
                book:bind(id)
                seen[id] = metadata(book:step(), id)
                book:close()
            end
        end
        if not result.complete then result.complete = next_row() == nil end
        stmt:close()
        local ids = {}
        for id in pairs(seen) do ids[#ids+1] = id end
        table.sort(ids)
        for _, id in ipairs(ids) do group(result, seen[id]) end
        result.byte_count = bytes
        -- This is a source observation only, including when complete=true.
        -- Invalid rows fail the entire batch, leaving no candidate scan to skip.
        return result
    end)
end

return M
