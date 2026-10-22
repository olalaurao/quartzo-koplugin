-- Isolated device harness. All filesystem/native dependencies are injected.
local M = {}
M.PAYLOAD = '{"probe_version":1,"source_data":"synthetic","event_count":1,"diagnostic_only":true}'
local allowed = { endpoint=true, token=true, expired_token=true, run_id=true,
    expires_at=true, ca_file=true, bad_ca_file=true }

function M.run(directory, deps)
    local report = {probe_version=1, phase="failed", proof="device_transport_diagnostic",
        source_data="synthetic", canonical_ack_claimed=false,
        canonical_persistence_proven=false, statistics_accessed=false, wifi_changed=false}
    local function fail(code) report.error_code=code; return report end
    if type(directory) ~= "string" or not directory:match("^/mnt/us/extensions/quartzo%-transport%-probe$") then
        return fail("invalid_owned_directory")
    end
    local ok, config = pcall(function()
        return deps.decode(deps.read(directory .. "/private-session.json", 2048))
    end)
    if not ok or type(config) ~= "table" then return fail("invalid_session_file") end
    for key in pairs(config) do
        if not allowed[key] then return fail("unexpected_session_field") end
    end
    if config.ca_file ~= "server.pem" or config.bad_ca_file ~= "untrusted.pem" then
        return fail("invalid_trust_path")
    end
    -- Do not propagate arbitrary decoder, native TLS, path or credential errors.
    if type(config.run_id) ~= "string" or #config.run_id ~= 32
        or config.run_id:find("[^a-f0-9]") then return fail("invalid_run_id") end
    report.run_id = config.run_id
    ok = pcall(function()
        assert(deps.read(directory .. "/synthetic-payload.json", 8192) == M.PAYLOAD)
        for _, name in ipairs({"server.pem", "untrusted.pem"}) do
            local certificate = deps.read(directory .. "/" .. name, 16384)
            assert(certificate:find("-----BEGIN CERTIFICATE-----", 1, true))
            assert(not certificate:find("PRIVATE KEY", 1, true))
        end
    end)
    if not ok then return fail("invalid_synthetic_fixture_or_certificate") end
    config.ca_file = directory .. "/server.pem"
    config.bad_ca_file = directory .. "/untrusted.pem"
    local started = deps.now()
    local result, error_code
    ok = pcall(function()
        local request = deps.client.transport(config, deps.https, deps.ltn12, M.PAYLOAD)
        result, error_code = deps.client.run(config, {
            request=request, now=deps.now, sleep=deps.sleep})
    end)
    if not ok then return fail("native_diagnostic_exception") end
    if not result then
        -- Only the client's fixed public error vocabulary is exposed here.
        local errors = {invalid_diagnostic_config=true, expired_or_untrusted_clock=true,
            bad_ca_not_rejected_by_certificate_validation=true, unauthorized_not_rejected=true,
            expired_token_not_rejected=true, noncanonical_receipt_required=true,
            retryable_fault_not_observed=true, retry_delay_rejected=true,
            bounded_retry_failed=true, replay_receipt_rejected=true}
        return fail(errors[error_code] and error_code or "diagnostic_failed")
    end
    for _, field in ipairs({"request_attempts", "bad_ca_rejected", "unauthorized_rejected",
        "expired_token_rejected", "rate_limit_retried", "server_error_retried",
        "replay_receipt_received"}) do report[field] = result[field] end
    report.phase = "passed"
    report.elapsed_seconds = math.max(0, deps.now() - started)
    return report
end

return M
