-- Explicit finite synthetic diagnostic. No file, outbox, cursor or ACK owner.
local M = {}
local labels = {"seed", "mixed", "within_request_conflict"}
local outcomes = {{"committed"},
    {"fatal_corruption", "unsupported_version", "review", "conflict", "committed"},
    {"conflict", "conflict", "committed"}}
local function check(value) if not value then error("wire_sequence_failed", 0) end end
local function hex(value, count)
    return type(value) == "string" and #value == count and not value:find("[^a-f0-9]")
end

function M.run(deps, codec_module, exchange, fixture, runtime)
    local result = {probe_revision="canonical-wire-sequence-v1", phase="failed", source_data="synthetic",
        canonical_ack=false, canonical_persistence_proven=false, physical_execution_attested=false,
        source_cursor_changed=false, statistics_accessed=false, wifi_changed=false,
        attempts=0, checked_responses=0, deliberately_discarded_responses=0, steps={}}
    local ok = pcall(function()
        check(type(runtime) == "table" and type(runtime.transport) == "function"
            and type(runtime.now) == "function" and type(runtime.window) == "function"
            and type(runtime.nonce) == "function" and type(runtime.pause) == "function"
            and type(runtime.token) == "string" and #runtime.token == 43
            and not runtime.token:find("[^A-Za-z0-9_-]"))
        check(fixture.schema_version == 1 and fixture.fixture_revision == "canonical-wire-synthetic-v1"
            and hex(fixture.run_id,32) and fixture.canonical_ack == false
            and fixture.physical_execution_attested == false and fixture.expected_unique_events == 3
            and fixture.expected_native_seconds == 120 and deps.kind(fixture.batches) == "array"
            and #fixture.batches == 3 and deps.kind(fixture.expected_shards) == "array"
            and #fixture.expected_shards == 3)
        local binding = deps.object({})
        local scope = "synthetic-wire-" .. fixture.run_id
        for _, key in ipairs({"binding_id", "vault_scope", "source_epoch"}) do
            check(fixture.binding[key] == scope)
            binding[key] = scope
        end
        check(fixture.binding.device_id == "synthetic-wire-device")
        binding.device_id = fixture.binding.device_id
        result.run_id = fixture.run_id
        local codec = codec_module.new(deps)
        check(codec and type(exchange.attempt) == "function")
        -- Snapshot every exact line/expectation before invoking external callbacks.
        local batches = {}
        for i=1,3 do
            local input, expected = fixture.batches[i], outcomes[i]
            check(input.label == labels[i] and deps.kind(input.event_lines) == "array"
                and #input.event_lines == #expected and deps.kind(input.expected_outcomes) == "array"
                and #input.expected_outcomes == #expected and deps.kind(input.expected_revisions) == "array"
                and #input.expected_revisions == #expected and hex(fixture.expected_shards[i].sha256,64))
            local batch = {lines=deps.array({}), revisions={}}
            for index, outcome in ipairs(expected) do
                check(type(input.event_lines[index]) == "string" and input.expected_outcomes[index] == outcome)
                batch.lines[index] = input.event_lines[index]
                batch.revisions[index] = outcome == "committed"
                    and "qrc_" .. fixture.expected_shards[i].sha256 or deps.null
                check(input.expected_revisions[index] == batch.revisions[index])
            end
            batches[i] = batch
        end
        local token, transport = runtime.token, runtime.transport
        local seen, batch_ids = {}, {}
        local function request(batch)
            local issued, expires = runtime.window()
            local nonce = runtime.nonce()
            check(type(nonce) == "string" and not seen[nonce])
            seen[nonce] = true
            local fields = deps.object({protocol_version=1, request_id=nonce,
                issued_at_utc=issued, expires_at_utc=expires, event_lines=batch.lines})
            for key, value in pairs(binding) do fields[key] = value end
            local bytes = codec.encode_request(fields,binding,runtime.now())
            check(type(bytes) == "string")
            local inspected = codec.inspect_request(bytes,binding,runtime.now())
            check(inspected and inspected.canonical_ack == false)
            if batch_ids[batch] then check(batch_ids[batch] == inspected.batch_id) end
            batch_ids[batch] = inspected.batch_id
            result.attempts = result.attempts+1
            check(result.attempts <= 10)
            return bytes, nonce, inspected.batch_id
        end
        local function record(step, bytes, nonce, batch)
            result.steps[#result.steps+1] = {step=step, request_id=nonce, batch_id=batch,
                request_sha256=deps.sha256(bytes)}
        end
        local function expected_error(step, code, bearer, status)
            local bytes, nonce, batch = request(batches[1])
            local observed
            local value, failure = exchange.attempt(codec,binding,runtime.now,bytes,function(payload,provided,trust)
                local http, body = transport(payload,provided,trust)
                observed = http
                return http, body
            end,bearer)
            check(value == nil and failure == code and observed == status)
            record(step,bytes,nonce,batch)
        end
        local bytes, nonce, batch = request(batches[1])
        local bad_status = transport(bytes,token,"bad")
        check(bad_status == nil)
        record("untrusted_certificate_rejected",bytes,nonce,batch)
        local wrong_token = (token:sub(1,1) == "x" and "y" or "x") .. token:sub(2)
        expected_error("unauthorized", "reading_http_unauthorized", wrong_token,401)
        expected_error("rate_limited", "reading_http_retryable", token,429)
        check(runtime.pause(1) == true)
        expected_error("server_retryable", "reading_http_retryable", token,503)

        bytes, nonce, batch = request(batches[1])
        local discarded_status, discarded_size
        local value, failure = exchange.attempt(codec,binding,runtime.now,bytes,function(payload,provided,trust)
            local http, body = transport(payload,provided,trust)
            discarded_status = http
            discarded_size = type(body) == "string" and #body or 0
            -- Deliberate application-level discard after I/O, not a claimed
            -- random connection failure or proof of physical network loss.
            return nil
        end,token)
        check(value == nil and failure == "reading_transport_failed"
            and discarded_status == 200 and discarded_size > 0 and discarded_size <= 524288)
        result.deliberately_discarded_responses = 1
        record("deliberately_discarded_response",bytes,nonce,batch)
        for i=1,3 do
            for attempt=1,(i == 1 and 1 or 2) do
                bytes, nonce, batch = request(batches[i])
                local response = exchange.attempt(codec,binding,runtime.now,bytes,transport,token)
                check(response and response.canonical_ack == false and response.accepted_events == nil
                    and #response.untrusted_claims == #outcomes[i])
                for index, claim in ipairs(response.untrusted_claims) do
                    check(claim.outcome == outcomes[i][index]
                        and claim.canonical_commit == batches[i].revisions[index])
                end
                result.checked_responses = result.checked_responses+1
                record(labels[i] .. "_" .. attempt,bytes,nonce,batch)
            end
        end
        check(result.attempts == 10 and result.checked_responses == 5)
        result.phase = "wire_claims_checked"
    end)
    if not ok then result.error_code = "wire_sequence_failed" end
    return result
end
return M
