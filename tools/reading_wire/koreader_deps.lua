-- Explicit KOReader dependency adapter for the gated pure consumer only.
-- Loading modules does not select a transport, access credentials or grant ACK.
local M = {}
function M.load(require_module)
    local ok, value = pcall(function()
        assert(type(require_module) == "function")
        local json, sha = require_module("dkjson"), require_module("ffi/sha2")
        assert(type(json) == "table" and type(json.decode) == "function" and json.null ~= nil)
        assert(type(sha) == "table" and type(sha.sha256) == "function")
        local object_meta, array_meta = {wire_kind="object"}, {wire_kind="array"}
        local deps = {null=json.null}
        function deps.kind(item)
            if item == json.null then return "null" end
            if type(item) ~= "table" then return type(item) end
            local meta = getmetatable(item)
            return type(meta) == "table" and meta.wire_kind or nil
        end
        function deps.decode_json(bytes)
            local decoded, position, failure = json.decode(bytes, 1, json.null, object_meta, array_meta)
            if failure or position ~= #bytes+1 then error("invalid_json_provider_result",0) end
            return decoded
        end
        function deps.sha256(bytes) return sha.sha256(bytes) end
        function deps.object(item) return setmetatable(item, object_meta) end
        function deps.array(item) return setmetatable(item, array_meta) end
        -- Probe the exact API instead of silently losing null/empty containers.
        local sample = deps.decode_json('{"object":{},"array":[],"null":null,"integer":9007199254740991}')
        assert(deps.kind(sample) == "object" and deps.kind(sample.object) == "object"
            and deps.kind(sample.array) == "array" and sample.null == json.null and sample.integer == 9007199254740991)
        assert(deps.sha256("abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad")
        return deps
    end)
    if ok then return value end
    return nil, "unsupported_reading_wire_dependencies"
end
return M
