-- Synthetic offline compatibility checks only. Filesystem/runtime setup belongs
-- to the separate disposable launcher; no network, native facts or ACK owner.
local M = {}
local order = {"protocol_version","binding_id","vault_scope","device_id","source_epoch","request_id",
    "issued_at_utc","expires_at_utc","batch_id","event_lines","results","index","line_digest",
    "event_id","native_digest","outcome","canonical_commit"}
local function check(value) if not value then error("wire_probe_check_failed",0) end end
function M.run(deps, codec_module, wire, reference, encode)
    local result = {probe_version=1, phase="failed", source_data="synthetic", uses_synthetic_clock=true,
        canonical_ack=false, canonical_persistence_proven=false, statistics_accessed=false,
        source_cursor_changed=false, network_accessed=false, wifi_changed=false}
    local ok = pcall(function()
        check(type(encode) == "function" and #wire.negative_cases == 12 and #reference.cases == 5)
        local codec = codec_module.new(deps)
        check(codec ~= nil)
        local binding = deps.object({})
        for _, key in ipairs({"binding_id","vault_scope","device_id","source_epoch"}) do binding[key] = wire.request[key] end
        local now = "2026-10-17T12:00:01.000Z"
        local function clone(value)
            if value == deps.null then return deps.null end
            if type(value) ~= "table" then return value end
            local copy = deps.kind(value) == "array" and deps.array({}) or deps.object({})
            for key, item in pairs(value) do copy[key] = clone(item) end
            return copy
        end
        local function request(lines)
            local input = clone(wire.request)
            input.batch_id = nil
            if lines then input.event_lines = deps.array(lines) end
            local encoded = codec.encode_request(input,binding,now)
            check(type(encoded) == "string")
            return encoded
        end
        check(request() == wire.request_json)
        local inspected = codec.inspect_request(wire.request_json,binding,now)
        check(inspected and inspected.canonical_ack == false and inspected.batch_id == wire.batch_id
            and inspected.entries[1].native_digest == wire.response.results[1].native_digest)
        local decoded = codec.decode_response(wire.response_json,wire.request_json,binding,now)
        check(decoded and decoded.canonical_ack == false and decoded.accepted_events == nil
            and #decoded.untrusted_claims == 1 and decoded.untrusted_claims[1].outcome == "committed")
        check(encode(wire.request,{keyorder=order}) == wire.request_json)
        check(encode(wire.response,{keyorder=order}) == wire.response_json)
        result.golden_checks = 3
        result.negative_cases = 0
        for _, case in ipairs(wire.negative_cases) do
            local changed = clone(wire[case.side])
            local target = changed
            for i = 1, #case.path-1 do
                local key = case.path[i]
                if type(key) == "number" then key = key+1 end
                target = target[key]
            end
            local key = case.path[#case.path]
            if type(key) == "number" then key = key+1 end
            target[key] = clone(case.value)
            local bytes = encode(changed,{keyorder=order})
            local value, failure
            if case.side == "request" then value, failure = codec.inspect_request(bytes,binding,now)
            else value, failure = codec.decode_response(bytes,wire.request_json,binding,now) end
            check(value == nil and failure == "invalid_reading_wire")
            result.negative_cases = result.negative_cases+1
        end
        result.native_reference_cases = 0
        for _, case in ipairs(reference.cases) do
            local value = codec.inspect_request(request({case.line}),binding,now)
            check(value and value.canonical_ack == false and value.entries[1].rejection == nil
                and value.entries[1].native_digest == deps.sha256(case.native_payload))
            result.native_reference_cases = result.native_reference_cases+1
        end
        local original = wire.request.event_lines[1]
        local changed, substitutions = original:gsub('"duration_seconds":1800','"duration_seconds":1801',1)
        check(substitutions == 1)
        local conflicts = codec.inspect_request(request({original,changed,original}),binding,now)
        check(conflicts and #conflicts.entries == 3)
        for _, entry in ipairs(conflicts.entries) do
            check(entry.rejection == "conflict" and entry.event_id == deps.null and entry.native_digest == deps.null)
        end
        result.conflicting_positions = 3
        local mixed = codec.inspect_request(request({original,"not JSON",'{"schema_version":999}'}),binding,now)
        check(mixed and #mixed.entries == 3 and mixed.entries[1].rejection == nil
            and mixed.entries[2].rejection == "fatal_corruption" and mixed.entries[3].rejection == "unsupported_version")
        result.isolated_entries = 3
        local expired, failure = codec.inspect_request(wire.request_json,binding,wire.request.expires_at_utc)
        check(expired == nil and failure == "invalid_reading_wire")
        result.expired_request_rejected = true
        result.phase = "passed"
    end)
    if not ok then result.error_code = "wire_probe_check_failed" end
    return result
end
return M
