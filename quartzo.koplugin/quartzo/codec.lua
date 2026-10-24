-- Gate 0C pure consumer of the pinned upstream wire contract. No I/O, secrets,
-- Statistics access, receipt issuer, accepted-event list or cursor authority.
local M = {}
local scope_keys = {"binding_id", "vault_scope", "device_id", "source_epoch"}
local request_keys = {"protocol_version", "binding_id", "vault_scope", "device_id", "source_epoch",
    "request_id", "issued_at_utc", "expires_at_utc", "batch_id", "event_lines"}
local response_keys = {"protocol_version", "binding_id", "vault_scope", "device_id", "source_epoch",
    "request_id", "batch_id", "results"}
local event_keys = {"schema_version", "event_id", "source", "device_id", "source_epoch", "book_row_id",
    "page", "started_at_utc", "duration_seconds", "total_pages", "observed_at_utc", "source_schema_version"}
local result_keys = {"index", "line_digest", "event_id", "native_digest", "outcome", "canonical_commit"}
local outcomes = {committed=true, duplicate=true, staged=true, retryable=true, auth_required=true,
    unsupported_version=true, conflict=true, review=true, fatal_corruption=true}
local function check(ok, code) if not ok then error(code, 0) end end
local function integer(n, low, high)
    return type(n) == "number" and n == n and n >= low and n <= high and n % 1 == 0
end
local function scope(s)
    return type(s) == "string" and #s >= 1 and #s <= 128 and not s:find("[^A-Za-z0-9_-]")
end
local function hex(s, count)
    return type(s) == "string" and #s == count and not s:find("[^a-f0-9]")
end
local function utf8(s)
    if type(s) ~= "string" then return false end
    local i = 1
    while i <= #s do
        local a, b = s:byte(i), s:byte(i+1)
        local length = 1
        if a <= 127 then length = 1
        elseif a >= 194 and a <= 223 then length = 2
        elseif a >= 224 and a <= 239 then
            length = 3
            if not b or (a == 224 and b < 160) or (a == 237 and b > 159) then return false end
        elseif a >= 240 and a <= 244 then
            length = 4
            if not b or (a == 240 and b < 144) or (a == 244 and b > 143) then return false end
        else return false end
        for j = 1, length-1 do
            local c = s:byte(i+j)
            if not c or c < 128 or c > 191 then return false end
        end
        i = i + length
    end
    return true
end
local escaped = {['"']='\\"', ['\\']='\\\\', ['\b']='\\b', ['\f']='\\f', ['\n']='\\n', ['\r']='\\r', ['\t']='\\t'}
local function quote(s)
    check(utf8(s), "invalid_unicode")
    return '"' .. s:gsub('[%z\1-\31\\"]', function(c)
        return escaped[c] or string.format('\\u%04x', c:byte())
    end) .. '"'
end
local function nonblank(s)
    if not utf8(s) then return false end
    local i = 1
    while i <= #s do
        local first = s:byte(i)
        local length = first >= 240 and 4 or first >= 224 and 3 or first >= 192 and 2 or 1
        local code = first - (length == 4 and 240 or length == 3 and 224 or length == 2 and 192 or 0)
        for j = 1, length-1 do code = code*64 + s:byte(i+j)-128 end
        local whitespace = (code >= 9 and code <= 13) or code == 32 or code == 133 or code == 160
            or code == 5760 or (code >= 8192 and code <= 8202) or code == 8232 or code == 8233
            or code == 8239 or code == 8287 or code == 12288 or code == 65279
        if not whitespace then return true end
        i = i + length
    end
    return false
end
local function timestamp(s)
    check(type(s) == "string", "invalid_timestamp")
    local y, m, d, h, n, sec, fraction = s:match('^(%d%d%d%d)%-(%d%d)%-(%d%d)T(%d%d):(%d%d):(%d%d)%.(%d+)Z$')
    check(y and (#fraction == 3 or (#fraction == 6 and fraction:sub(4) ~= "000")), "noncanonical_timestamp")
    y, m, d, h, n, sec = tonumber(y), tonumber(m), tonumber(d), tonumber(h), tonumber(n), tonumber(sec)
    local leap = y % 4 == 0 and (y % 100 ~= 0 or y % 400 == 0)
    local months = {31, leap and 29 or 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31}
    check(y >= 1 and y <= 9999 and m >= 1 and m <= 12 and d >= 1 and d <= months[m]
        and h <= 23 and n <= 59 and sec <= 59, "invalid_calendar")
    local previous = y-1
    local days = previous*365 + math.floor(previous/4) - math.floor(previous/100) + math.floor(previous/400) + d-1
    for month = 1, m-1 do days = days + months[month] end
    return {seconds=(days-719162)*86400 + h*3600+n*60+sec,
        micros=tonumber(fraction) * (#fraction == 3 and 1000 or 1)}
end
local function compare(a, b)
    if a.seconds ~= b.seconds then return a.seconds < b.seconds end
    return a.micros < b.micros
end
-- Reuse the same canonical UTC parser for request and finite pairing windows.
-- This pure predicate authenticates neither a peer nor an acknowledgement.
local function window(issued_text, expiry_text, now_text, maximum, previous_text)
    local issued, expiry, current = timestamp(issued_text), timestamp(expiry_text), timestamp(now_text)
    local lifetime = expiry.seconds-issued.seconds + (expiry.micros-issued.micros)/1000000
    check(lifetime > 0 and lifetime <= maximum and not compare(current, issued)
        and compare(current, expiry), "invalid_window")
    if previous_text then check(not compare(current,timestamp(previous_text)), "backward_clock") end
    return true
end
local function guarded(fn, ...)
    local ok, value = pcall(fn, ...)
    if ok then return value end
    -- Never propagate decoder/provider exceptions or private input excerpts.
    return nil, "invalid_reading_wire"
end

local function create(deps)
    check(type(deps) == "table" and type(deps.sha256) == "function" and type(deps.decode_json) == "function"
        and type(deps.kind) == "function" and deps.null ~= nil, "explicit_codec_dependencies_required")
    local hash, decode, kind, null = deps.sha256, deps.decode_json, deps.kind, deps.null
    local function digest(bytes)
        local value = hash(bytes)
        check(hex(value, 64), "invalid_digest_provider")
        return value
    end
    check(digest("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", "invalid_digest_provider")
    local function keys(value, expected)
        check(kind(value) == "object", "object_required")
        local allowed = {}
        for _, key in ipairs(expected) do allowed[key] = true; check(value[key] ~= nil, "missing_field") end
        for key in pairs(value) do check(allowed[key], "unknown_field") end
    end
    local function array(value, low, high)
        check(kind(value) == "array", "array_required")
        local count = 0
        for key in pairs(value) do
            check(integer(key, 1, high), "invalid_array_index")
            count = count + 1
        end
        check(count >= low and count <= high, "array_bound")
        for i = 1, count do check(value[i] ~= nil, "sparse_array") end
        return count
    end
    local function primitive(value)
        if value == null then return "null" end
        if type(value) == "string" then return quote(value) end
        check(integer(value, 0, 9007199254740991), "integer_required")
        return string.format("%.0f", value)
    end
    local function object(value, order, skip)
        local parts = {}
        for _, key in ipairs(order) do
            if key ~= skip then parts[#parts+1] = quote(key) .. ":" .. primitive(value[key]) end
        end
        return "{" .. table.concat(parts, ",") .. "}"
    end
    local function strings(lines)
        local parts = {}
        for i = 1, #lines do parts[i] = quote(lines[i]) end
        return "[" .. table.concat(parts, ",") .. "]"
    end
    local function parse(bytes, limit)
        check(type(bytes) == "string" and #bytes > 0 and #bytes <= limit and utf8(bytes), "wire_bound_or_unicode")
        return decode(bytes)
    end
    local function context(request, expected, now)
        keys(expected, scope_keys)
        for _, key in ipairs(scope_keys) do
            check(scope(request[key]) and scope(expected[key]) and request[key] == expected[key], "binding_mismatch")
        end
        window(request.issued_at_utc,request.expires_at_utc,now,300)
    end
    local function build_request(input, expected, now, decoding)
        local expected_keys = {}
        for _, key in ipairs(request_keys) do if decoding or key ~= "batch_id" then expected_keys[#expected_keys+1] = key end end
        keys(input, expected_keys)
        check(input.protocol_version == 1 and type(input.request_id) == "string" and #input.request_id == 37
            and input.request_id:sub(1,5) == "qrtr_" and hex(input.request_id:sub(6),32), "request_version_or_nonce")
        context(input, expected, now)
        local count = array(input.event_lines, 1, 1000)
        local lines, size = {}, 0
        for i = 1, count do
            local line = input.event_lines[i]
            check(type(line) == "string" and #line > 0 and #line <= 8192 and utf8(line)
                and not line:find('[\r\n]'), "line_bound_or_unicode")
            size = size + #line + 1
            check(size <= 524288, "payload_bound")
            lines[i] = line
        end
        local preimage = {quote("quartzo-reading-transport-batch-v1")}
        for _, key in ipairs(scope_keys) do preimage[#preimage+1] = quote(input[key]) end
        preimage[#preimage+1] = strings(lines)
        local batch = "qrtb_" .. digest("[" .. table.concat(preimage, ",") .. "]")
        if decoding then check(input.batch_id == batch, "batch_mismatch") end
        local fields = {protocol_version=1, batch_id=batch}
        for _, key in ipairs(scope_keys) do fields[key] = input[key] end
        fields.request_id, fields.issued_at_utc, fields.expires_at_utc = input.request_id, input.issued_at_utc, input.expires_at_utc
        local prefix = object(fields, request_keys, "event_lines")
        local encoded = prefix:sub(1,-2) .. ',"event_lines":' .. strings(lines) .. "}"
        check(#encoded <= 1048576, "request_bound")
        return {fields=fields, lines=lines, bytes=encoded}
    end
    local function request(bytes, expected, now)
        local value = build_request(parse(bytes, 1048576), expected, now, true)
        check(value.bytes == bytes, "noncanonical_request")
        return value
    end
    local function event_identity(raw)
        local started = timestamp(raw.started_at_utc)
        check(started.micros == 0, "native_start_precision")
        local preimage = '[' .. quote("quartzo-reading-event-v1") .. ',' .. quote(raw.device_id) .. ',' .. quote(raw.source_epoch)
            .. ',' .. primitive(raw.book_row_id) .. ',' .. primitive(raw.page) .. ',' .. string.format('%.0f', started.seconds) .. ']'
        return "qre_" .. digest(preimage)
    end
    local function inspect_event(line)
        local raw = parse(line, 8192)
        if kind(raw) ~= "object" then return {rejection="fatal_corruption"} end
        if raw.schema_version ~= 1 then return {rejection="unsupported_version"} end
        keys(raw, event_keys)
        check(raw.source == "koreader_statistics" and nonblank(raw.device_id)
            and nonblank(raw.source_epoch) and nonblank(raw.source_schema_version), "invalid_native_fields")
        for _, key in ipairs({"book_row_id", "page", "total_pages"}) do check(integer(raw[key],1,9007199254740991), "native_integer") end
        check(integer(raw.duration_seconds,1,86400), "native_duration")
        timestamp(raw.observed_at_utc)
        check(raw.event_id == event_identity(raw) and object(raw,event_keys) == line, "native_identity_or_encoding")
        return {event_id=raw.event_id, device_id=raw.device_id, source_epoch=raw.source_epoch,
            started_at_seconds=timestamp(raw.started_at_utc).seconds,
            native=object(raw,event_keys,"observed_at_utc")}
    end
    local function entries(value)
        local result, by_id, conflicts = {}, {}, {}
        for i, line in ipairs(value.lines) do
            local ok, entry = pcall(inspect_event, line)
            if not ok then entry = {rejection="fatal_corruption"} end
            entry.index, entry.line_digest = i-1, digest(line)
            if not entry.rejection then
                if entry.device_id ~= value.fields.device_id or entry.source_epoch ~= value.fields.source_epoch then entry.rejection = "review"
                elseif by_id[entry.event_id] and by_id[entry.event_id] ~= entry.native then conflicts[entry.event_id] = true end
                if not entry.rejection then by_id[entry.event_id] = entry.native end
            end
            result[i] = entry
        end
        for _, entry in ipairs(result) do
            if entry.event_id and conflicts[entry.event_id] then entry.rejection = "conflict" end
            if entry.rejection then entry.event_id, entry.native_digest = null, null
            else entry.native_digest = digest(entry.native) end
            entry.native, entry.device_id, entry.source_epoch, entry.started_at_seconds = nil, nil, nil, nil
        end
        return result
    end
    local api = {}
    function api.utc_seconds(value)
        return guarded(function() return timestamp(value).seconds end)
    end
    function api.inspect_event(line)
        return guarded(function()
            local entry = inspect_event(line)
            check(not entry.rejection, "invalid_event")
            return {event_id=entry.event_id, device_id=entry.device_id, source_epoch=entry.source_epoch,
                native_digest=digest(entry.native), line_digest=digest(line),
                started_at_seconds=entry.started_at_seconds,canonical_ack=false}
        end)
    end
    -- Construction and inspection share the same serializer, identity and validator.
    -- Plain caller fields are copied; no receipt or cursor capability is created.
    function api.encode_event(input)
        return guarded(function()
            check(type(input) == "table", "event_fields_required")
            local raw, allowed = {}, {}
            for _, key in ipairs(event_keys) do
                if key ~= "event_id" then
                    check(input[key] ~= nil, "missing_field")
                    raw[key], allowed[key] = input[key], true
                end
            end
            for key in pairs(input) do check(allowed[key], "unknown_field") end
            raw.event_id = event_identity(raw)
            local line = object(raw, event_keys)
            check(not inspect_event(line).rejection, "invalid_event")
            return line
        end)
    end
    function api.check_pairing_window(issued, expiry, now, previous)
        return guarded(window,issued,expiry,now,1800,previous)
    end
    function api.encode_request(input, expected, now)
        return guarded(function() return build_request(input, expected, now, false).bytes end)
    end
    function api.inspect_request(bytes, expected, now)
        return guarded(function()
            local value = request(bytes, expected, now)
            return {batch_id=value.fields.batch_id, entries=entries(value), canonical_ack=false}
        end)
    end
    function api.decode_response(bytes, request_bytes, expected, now)
        return guarded(function()
            local sent = request(request_bytes, expected, now)
            local raw = parse(bytes, 524288)
            keys(raw, response_keys)
            check(raw.protocol_version == 1 and raw.request_id == sent.fields.request_id and raw.batch_id == sent.fields.batch_id, "response_identity")
            for _, key in ipairs(scope_keys) do check(raw[key] == sent.fields[key], "response_binding") end
            check(array(raw.results,1,1000) == #sent.lines, "response_count")
            local inspected, claims, encoded_claims = entries(sent), {}, {}
            for i, claim in ipairs(raw.results) do
                keys(claim, result_keys)
                local entry = inspected[i]
                check(integer(claim.index,0,999) and claim.index == i-1 and claim.line_digest == entry.line_digest
                    and claim.event_id == entry.event_id and claim.native_digest == entry.native_digest
                    and type(claim.outcome) == "string" and outcomes[claim.outcome], "response_claim")
                local committed = claim.outcome == "committed" or claim.outcome == "duplicate"
                check((committed and not entry.rejection and scope(claim.canonical_commit))
                    or (not committed and claim.canonical_commit == null), "untrusted_commit_claim")
                local copy = {}
                for _, key in ipairs(result_keys) do copy[key] = claim[key] end
                claims[i], encoded_claims[i] = copy, object(copy,result_keys)
            end
            local prefix = object(sent.fields,response_keys,"results")
            local encoded = prefix:sub(1,-2) .. ',"results":[' .. table.concat(encoded_claims,",") .. "]}"
            check(encoded == bytes, "noncanonical_response")
            return {untrusted_claims=claims, canonical_ack=false}
        end)
    end
    return api
end
function M.new(deps) return guarded(create, deps) end
return M
