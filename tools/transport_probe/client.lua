-- Isolated Gate 0B diagnostic only. No plugin, Statistics, outbox or ACK owner.
local M = {}
M.RECEIPT = '{"probe_version":1,"transport_only":true,"canonical_ack":false,"persisted_canonical":false}'

local function hex(value, size)
    return type(value) == "string" and #value == size and not value:find("[^a-f0-9]")
end

local function privateEndpoint(value)
    if type(value) ~= "string" then return false end
    local a, b, c, d, port = value:match("^https://(%d+)%.(%d+)%.(%d+)%.(%d+):(%d+)$")
    if not a then return false end
    local parts = {a, b, c, d}
    for i, part in ipairs(parts) do
        if (#part > 1 and part:sub(1, 1) == "0") or tonumber(part) > 255 then return false end
        parts[i] = tonumber(part)
    end
    port = tonumber(port)
    if port < 1024 or port > 65535 then return false end
    return parts[1] == 10 or (parts[1] == 192 and parts[2] == 168)
        or (parts[1] == 172 and parts[2] >= 16 and parts[2] <= 31)
        or (parts[1] == 127 and parts[2] == 0 and parts[3] == 0 and parts[4] == 1)
end

local function errorText(value)
    if type(value) == "table" then value = value[1] end
    return type(value) == "string" and value:lower() or "unclassified"
end

-- Uses the installed KOReader LuaSec API with explicit peer trust. Its default
-- verify setting is not sufficient. This binds only the isolated test cert;
-- it is not a production/public-CA hostname-verification implementation.
function M.transport(config, https, ltn12, payload)
    assert(privateEndpoint(config.endpoint), "explicit private HTTPS endpoint required")
    assert(type(payload) == "string" and #payload > 0 and #payload <= 8192, "invalid diagnostic payload")
    assert(type(config.ca_file) == "string" and #config.ca_file > 0
        and type(config.bad_ca_file) == "string" and #config.bad_ca_file > 0
        and config.ca_file ~= config.bad_ca_file, "explicit diagnostic trust files required")
    https.TIMEOUT = 5
    return function(path, token, trust)
        if (path ~= "ok" and path ~= "rate" and path ~= "server")
            or not hex(token, 64) or (trust ~= "good" and trust ~= "bad") then
            return nil, "invalid_diagnostic_request"
        end
        local chunks, received, exceeded = {}, 0, false
        local request = {
            url = config.endpoint .. "/probe/" .. path,
            method = "POST", redirect = false,
            protocol = "tlsv1_2", verify = "peer",
            cafile = trust == "bad" and config.bad_ca_file or config.ca_file,
            headers = {
                ["content-type"] = "application/json",
                ["content-length"] = tostring(#payload),
                ["authorization"] = "Bearer " .. token,
                ["x-quartzo-probe-run"] = config.run_id,
            },
            source = ltn12.source.string(payload),
            sink = function(chunk)
                if chunk then
                    received = received + #chunk
                    if received > 2048 then exceeded = true; return nil, "response_bound" end
                    chunks[#chunks + 1] = chunk
                end
                return 1
            end,
        }
        local ok, first, code, headers = pcall(https.request, request)
        if exceeded then return nil, "response_bound" end
        if not ok then return nil, errorText(first) end
        if not first then return nil, errorText(code) end
        return tonumber(code), table.concat(chunks), headers
    end
end

function M.run(config, deps)
    if type(config) ~= "table" or type(deps) ~= "table"
        or type(deps.request) ~= "function" or type(deps.now) ~= "function"
        or type(deps.sleep) ~= "function" or not privateEndpoint(config.endpoint)
        or not hex(config.token, 64) or not hex(config.expired_token, 64)
        or config.token == config.expired_token or not hex(config.run_id, 32)
        or type(config.expires_at) ~= "number"
        or type(config.ca_file) ~= "string" or #config.ca_file == 0
        or type(config.bad_ca_file) ~= "string" or #config.bad_ca_file == 0
        or config.ca_file == config.bad_ca_file then
        return nil, "invalid_diagnostic_config"
    end
    local function validClock()
        local remaining = config.expires_at - deps.now()
        return remaining > 0 and remaining <= 1800
    end
    if not validClock() then return nil, "expired_or_untrusted_clock" end
    local attempts = 0
    local function request(path, token, trust)
        if not validClock() then return nil, "expired_or_untrusted_clock" end
        attempts = attempts + 1
        return deps.request(path, token, trust)
    end
    -- Never send the valid credential during the untrusted-certificate test.
    local code, detail = request("ok", string.rep("0", 64), "bad")
    if code ~= nil or not (errorText(detail):find("certificate", 1, true)
        or errorText(detail):find("unknown ca", 1, true)) then
        return nil, "bad_ca_not_rejected_by_certificate_validation"
    end
    code = request("ok", string.rep("0", 64), "good")
    if code ~= 401 then return nil, "unauthorized_not_rejected" end
    code = request("ok", config.expired_token, "good")
    if code ~= 401 then return nil, "expired_token_not_rejected" end
    local body
    code, body = request("ok", config.token, "good")
    if code ~= 200 or body ~= M.RECEIPT then return nil, "noncanonical_receipt_required" end
    for _, scenario in ipairs({"rate", "server"}) do
        local headers
        code, body, headers = request(scenario, config.token, "good")
        if (scenario == "rate" and code ~= 429) or (scenario == "server"
            and (not code or code < 500 or code > 599)) then
            return nil, "retryable_fault_not_observed"
        end
        local delay = 1
        if scenario == "rate" then delay = headers and tonumber(headers["retry-after"]) end
        if not delay or delay < 1 or delay > 3 or delay ~= math.floor(delay) then
            return nil, "retry_delay_rejected"
        end
        deps.sleep(delay)
        code, body = request(scenario, config.token, "good")
        if code ~= 200 or body ~= M.RECEIPT then return nil, "bounded_retry_failed" end
    end
    code, body = request("ok", config.token, "good")
    if code ~= 200 or body ~= M.RECEIPT then return nil, "replay_receipt_rejected" end
    return {
        phase = "passed", probe_version = 1, request_attempts = attempts,
        source_data = "synthetic", bad_ca_rejected = true,
        unauthorized_rejected = true, expired_token_rejected = true,
        rate_limit_retried = true, server_error_retried = true,
        replay_receipt_received = true, canonical_ack_claimed = false,
        statistics_accessed = false, wifi_changed = false,
    }
end

return M
