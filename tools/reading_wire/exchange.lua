-- One explicit diagnostic attempt. No retry loop, file/queue/credential owner,
-- listener, Statistics access, Wi-Fi action, accepted-event list or cursor grant.
local M = {}

function M.attempt(codec, binding, now, requestBytes, transport, token)
    if type(codec) ~= "table" or type(codec.inspect_request) ~= "function"
        or type(codec.decode_response) ~= "function" or type(now) ~= "function"
        or type(transport) ~= "function" then return nil, "invalid_reading_exchange" end
    local ok, value, failure = pcall(function()
        local inspected = codec.inspect_request(requestBytes, binding, now())
        if not inspected or inspected.canonical_ack ~= false then return nil, "invalid_reading_wire" end
        local status, body = transport(requestBytes, token, "good")
        if status == 401 then return nil, "reading_http_unauthorized" end
        if status == 429 or (type(status) == "number" and status >= 500 and status <= 599) then
            return nil, "reading_http_retryable"
        end
        if status ~= 200 then return nil, "reading_transport_failed" end
        local response = codec.decode_response(body, requestBytes, binding, now())
        if not response or response.canonical_ack ~= false or response.accepted_events ~= nil then
            return nil, "invalid_reading_wire"
        end
        return response
    end)
    if not ok then return nil, "invalid_reading_exchange" end
    return value, failure
end

return M
