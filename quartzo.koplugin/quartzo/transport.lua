-- Isolated Gate 0B diagnostic only. No plugin, Statistics, outbox or ACK owner.
local M = {}
local pinnedDeliveries = setmetatable({}, {__mode="k"})
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

-- Diagnostic trust rejection must come from verification, not generic TLS,
-- offline or certificate-file configuration failure. Never expose raw detail.
function M.certificate_rejected(status, detail)
    local text = errorText(detail)
    return status == nil and (text:find("certificate verify failed", 1, true) ~= nil
        or text:find("unknown ca", 1, true) ~= nil)
end

-- LuaSec 1.3.2 exports tcp(), but https.request rejects a caller create hook.
-- Reuse that native TLS factory and LuaSocket's existing HTTP implementation.
-- The wrapper gates every HTTP write on the actual peer's DER SHA-256 pin.
local function pinnedRequester(endpoint, ca, pin, https, http)
    assert(https._VERSION == "1.3.2" and type(https.tcp) == "function"
        and type(http) == "table" and type(http.request) == "function", "pinned_TLS_API_required")
    local expectedHost, expectedPort = endpoint:match('^https://([^:]+):(%d+)$')
    local httpRequest, tlsFactory = http.request, https.tcp
    return function(request)
        if http.PROXY then return nil, "reading_proxy_unsupported" end
        local closes, created, authenticated, invalid, failure = {}, 0, false, false, nil
        local ok, first, code, headers = pcall(function()
            local create = tlsFactory({protocol="tlsv1_2",verify="peer",cafile=ca,
                options={"all","no_sslv2","no_sslv3","no_tlsv1"}})
            assert(type(create) == "function", "native_TLS_factory_required")
            request.create = function()
                created = created + 1
                if created ~= 1 then invalid = true; error("reading_transport_failed",0) end
                local native = create()
                assert(type(native) == "table" and type(native.connect) == "function", "native_TLS_socket_required")
                local connected, closed = false, false
                local function close()
                    if closed then return 1 end
                    closed, connected = true, false
                    if type(native.close) == "function" then pcall(native.close,native)
                    elseif native.sock and type(native.sock.close) == "function" then pcall(native.sock.close,native.sock) end
                    return 1
                end
                closes[#closes+1] = close
                local function reject(reason)
                    invalid, failure = true, reason
                    close()
                    return nil, reason
                end
                local conn = {}
                function conn:close() return close() end
                function conn:settimeout()
                    if closed or type(native.settimeout) ~= "function" then return reject("reading_transport_failed") end
                    return native:settimeout(5)
                end
                function conn:connect(host,port)
                    if closed or connected or host ~= expectedHost or tonumber(port) ~= tonumber(expectedPort) then
                        return reject("reading_transport_failed")
                    end
                    local established, result, detail = pcall(native.connect,native,host,port)
                    if not established or result ~= 1 then
                        local reason = M.certificate_rejected(nil, established and detail or result)
                            and "certificate verify failed" or "reading_transport_failed"
                        return reject(reason)
                    end
                    local inspected, digest = pcall(function()
                        local certificate = native:getpeercertificate()
                        return certificate and certificate:digest("sha256")
                    end)
                    if not inspected or not hex(digest,64) then return reject("reading_peer_unverified") end
                    if digest ~= pin then return reject("reading_peer_pin_mismatch") end
                    connected, authenticated = true, true
                    return 1
                end
                function conn:send(...)
                    if not connected or closed then return reject("reading_peer_unverified") end
                    return native:send(...)
                end
                function conn:receive(...)
                    if not connected or closed then return reject("reading_peer_unverified") end
                    return native:receive(...)
                end
                function conn:getfd() return native:getfd() end
                function conn:dirty() return native:dirty() end
                return conn
            end
            return httpRequest(request)
        end)
        for _, close in ipairs(closes) do close() end
        if not ok or not first or invalid or not authenticated or created ~= 1 then
            return nil, failure or "reading_transport_failed"
        end
        return first, code, headers
    end
end

-- Uses the installed KOReader LuaSec API with explicit peer trust. Its default
-- verify setting is not sufficient. This binds only the isolated test cert;
-- it is not a production/public-CA hostname-verification implementation.
local function postTransport(config, https, ltn12, responseBound, pin, http)
    assert(privateEndpoint(config.endpoint), "explicit private HTTPS endpoint required")
    assert(type(config.ca_file) == "string" and #config.ca_file > 0, "explicit peer trust file required")
    if not pin then
        assert(type(config.bad_ca_file) == "string" and #config.bad_ca_file > 0
            and config.ca_file ~= config.bad_ca_file, "explicit diagnostic trust files required")
    end
    local endpoint, ca, badCa = config.endpoint, config.ca_file, config.bad_ca_file
    local requestPeer = pin and pinnedRequester(endpoint,ca,pin,https,http) or nil
    https.TIMEOUT = 5
    return function(path, payload, headers, trust)
        local chunks, received, exceeded = {}, 0, false
        headers["content-type"], headers["content-length"] = "application/json", tostring(#payload)
        local request = {
            url = endpoint .. path,
            method = "POST", redirect = false,
            protocol = "tlsv1_2", verify = "peer",
            cafile = trust == "bad" and badCa or ca, headers = headers,
            source = ltn12.source.string(payload),
            sink = function(chunk)
                if chunk then
                    if type(chunk) ~= "string" then exceeded = true; return nil, "response_bound" end
                    received = received + #chunk
                    if received > responseBound then exceeded = true; return nil, "response_bound" end
                    chunks[#chunks + 1] = chunk
                end
                return 1
            end,
        }
        local ok, first, code, headers = pcall(requestPeer or https.request, request)
        if exceeded then return nil, "response_bound" end
        if not ok then return nil, pin and "reading_transport_failed" or errorText(first) end
        if not first then return nil, pin and code or errorText(code) end
        return tonumber(code), table.concat(chunks), headers
    end
end

function M.transport(config, https, ltn12, payload)
    assert(type(payload) == "string" and #payload > 0 and #payload <= 8192, "invalid diagnostic payload")
    local post, runId = postTransport(config, https, ltn12, 2048), config.run_id
    return function(path, token, trust)
        if (path ~= "ok" and path ~= "rate" and path ~= "server")
            or not hex(token, 64) or (trust ~= "good" and trust ~= "bad") then
            return nil, "invalid_diagnostic_request"
        end
        return post("/probe/" .. path, payload, {
            authorization = "Bearer " .. token, ["x-quartzo-probe-run"] = runId,
        }, trust)
    end
end

-- Opt-in canonical-wire diagnostic carrier, still no receipt/cursor authority.
-- The caller supplies fresh canonical bytes and the current short-lived bearer.
-- Shared TLS policy above remains the only network implementation.
local function wireTransport(config, https, ltn12, pin, http)
    assert(type(config.binding_id) == "string" and #config.binding_id >= 1
        and #config.binding_id <= 128 and not config.binding_id:find("[^A-Za-z0-9_-]"),
        "explicit diagnostic binding required")
    local post, bindingId = postTransport(config, https, ltn12, 524288,pin,http), config.binding_id
    local endpoint = config.endpoint
    return function(payload, token, trust)
        if type(payload) ~= "string" or #payload == 0 or #payload > 1048576
            or type(token) ~= "string" or #token ~= 43 or token:find("[^A-Za-z0-9_-]")
            or (trust ~= "good" and trust ~= "bad") or (pin and trust ~= "good") then
            return nil, "invalid_diagnostic_request"
        end
        local headers = {
            authorization = "Bearer " .. token, ["x-quartzo-reading-binding"] = bindingId,
        }
        if not pin then return post("/reading/activity/v1",payload,headers,trust) end
        local status, body, responseHeaders = post("/reading/activity/v1",payload,headers,trust)
        if status == nil then return nil,body end
        if status ~= 200 then return status,body,responseHeaders end
        local delivery = setmetatable({}, {__metatable="pinned_reading_delivery",
            __newindex=function() error("immutable_reading_delivery",0) end})
        pinnedDeliveries[delivery] = {endpoint=endpoint,bindingId=bindingId,pin=pin,
            token=token,request=payload,status=status,body=body}
        return status,body,responseHeaders,delivery
    end
end

function M.wire_transport(config, https, ltn12)
    return wireTransport(config,https,ltn12)
end

-- Opt-in isolated trust preparation. No canonical-receiver role, accepted
-- events, durable receipt, outbox or source cursor follows from a TLS delivery.
function M.pinned_wire_transport(config, https, ltn12, http)
    assert(type(config) == "table" and hex(config.peer_certificate_sha256,64), "peer_fingerprint_required")
    return wireTransport(config,https,ltn12,config.peer_certificate_sha256,http)
end

function M.read_pinned_delivery(delivery, request, token, context)
    local value = pinnedDeliveries[delivery]
    if not value or type(context) ~= "table" or value.request ~= request or value.token ~= token
        or value.endpoint ~= context.endpoint or value.bindingId ~= context.binding_id
        or value.pin ~= context.peer_certificate_sha256 then return nil,"untrusted_reading_delivery" end
    return value.status,value.body
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
    if not M.certificate_rejected(code, detail) then
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
