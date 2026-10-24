-- Finite synthetic physical-test sequence through the approved paired owner.
-- No Statistics, file, outbox/cursor, retry scheduler or Wi-Fi action.
local M={}
local labels={"seed","mixed","within_request_conflict"}
local expected={{"committed"},{"fatal_corruption","unsupported_version","review","conflict","committed"},
    {"conflict","conflict","committed"}}
local function check(value) if not value then error("paired_sequence_failed",0) end end
local function hex(value,size)
    return type(value)=="string" and #value==size and not value:find("[^a-f0-9]")
end
function M.run(deps,codec_module,paired,fixture,runtime)
    local report={probe_revision="canonical-paired-sequence-v1",phase="failed",source_data="synthetic",
        canonical_ack=false,canonical_persistence_proven=false,physical_execution_attested=false,
        source_cursor_changed=false,statistics_accessed=false,wifi_changed=false,
        attempts=0,checked_receipts=0,deliberately_discarded_responses=0,steps={}}
    local session
    local ok=pcall(function()
        check(type(runtime)=="table" and type(runtime.now)=="function"
            and type(runtime.window)=="function" and type(runtime.nonce)=="function")
        check(fixture.schema_version==1 and fixture.fixture_revision=="canonical-wire-synthetic-v1"
            and hex(fixture.run_id,32) and fixture.canonical_ack==false
            and fixture.physical_execution_attested==false and fixture.expected_unique_events==3
            and fixture.expected_native_seconds==120 and deps.kind(fixture.batches)=="array"
            and #fixture.batches==3 and deps.kind(fixture.expected_shards)=="array" and #fixture.expected_shards==3)
        report.run_id=fixture.run_id
        local binding=deps.object({})
        for _,key in ipairs({"binding_id","vault_scope","device_id","source_epoch"}) do
            binding[key]=fixture.binding[key]
        end
        local native_context=type(binding.device_id)=="string" and #binding.device_id==36
            and binding.device_id:match("^qrd_[a-f0-9]+$")
            and type(binding.source_epoch)=="string" and #binding.source_epoch==38
            and binding.source_epoch:match("^probe_[a-f0-9]+$")
        check((binding.device_id=="synthetic-wire-device" and binding.source_epoch=="synthetic-wire-"..fixture.run_id)
            or native_context)
        check((native_context and type(runtime.outbox)=="table")
            or (not native_context and runtime.outbox==nil and not runtime.seed_only))
        local batches={}
        for i=1,3 do
            local input=fixture.batches[i]
            check(input.label==labels[i] and deps.kind(input.event_lines)=="array"
                and #input.event_lines==#expected[i] and #input.expected_outcomes==#expected[i]
                and hex(fixture.expected_shards[i].sha256,64))
            local batch={lines=deps.array({}),revision="qrc_"..fixture.expected_shards[i].sha256}
            for index,outcome in ipairs(expected[i]) do
                check(type(input.event_lines[index])=="string" and input.expected_outcomes[index]==outcome)
                batch.lines[index]=input.event_lines[index]
            end
            batches[i]=batch
        end
        local codec=assert(codec_module.new(deps))
        local queue
        if native_context then
            queue=assert(runtime.outbox.open(runtime.queue_root,{codec=codec,sqlite=runtime.sqlite,
                attributes=runtime.attributes}))
            local context=queue.context()
            check(context.device_id==binding.device_id and context.source_epoch==binding.source_epoch)
            local before=assert(queue.status())
            check(before.canonical_ack==false)
            if runtime.seed_only then
                check(before.pending==0 and before.review==0)
            else
                check(runtime.expected_seed_pending==true and before.pending==3 and before.review==1)
            end
            local staged=assert(queue.stage({
                event_lines={batches[1].lines[1],batches[2].lines[5],batches[3].lines[3]},
                scanned_count=4,rejections={{reason="invalid_statistics_event",started_at=1791946202,row_id=3,
                    integer_fields={book_row_id="17",page="0",duration_seconds="10",total_pages="120"},
                    field_types={"integer","integer","integer","integer","integer"}}},
            }))
            check(staged.pending==3 and staged.review==1 and staged.canonical_ack==false)
            report.outbox_initial_pending,report.outbox_review_retained,report.outbox_pruned=3,1,0
            local selected=assert(queue.pending(10))
            check(#selected.event_lines==3 and selected.canonical_ack==false)
            local expected_lines={[batches[1].lines[1]]=true,[batches[2].lines[5]]=true,[batches[3].lines[3]]=true}
            report.outbox_selected_sha256=deps.array({})
            for _,line in ipairs(selected.event_lines) do
                check(expected_lines[line]);expected_lines[line]=nil
                report.outbox_selected_sha256[#report.outbox_selected_sha256+1]=deps.sha256(line)
            end
            check(next(expected_lines)==nil)
            report.outbox_raw_receipt_rejections=0
        end
        local now,window,nonce=runtime.now,runtime.window,runtime.nonce
        session=assert(paired.open(runtime.document_bytes,runtime.approved_sha256,{
            deps=deps,codec=codec,carrier=runtime.carrier,ca_file=runtime.ca_file,
            now=now,https=runtime.https,ltn12=runtime.ltn12,http=runtime.http,
        }))
        local seen,batch_ids={},{}
        for i,batch in ipairs(batches) do
            for attempt=1,2 do
                local issued,expires=window()
                local id=nonce()
                check(type(id)=="string" and not seen[id]);seen[id]=true
                local fields=deps.object({protocol_version=1,request_id=id,
                    issued_at_utc=issued,expires_at_utc=expires,event_lines=batch.lines})
                for key,value in pairs(binding) do fields[key]=value end
                local bytes=assert(codec.encode_request(fields,binding,now()))
                local inspected=assert(codec.inspect_request(bytes,binding,now()))
                if batch_ids[i] then check(batch_ids[i]==inspected.batch_id) end
                batch_ids[i]=inspected.batch_id
                report.attempts=report.attempts+1;check(report.attempts<=6)
                local receipt,reason=paired.attempt(session,bytes)
                if not receipt then
                    local allowed={reading_transport_failed=true,reading_peer_unverified=true,
                        reading_peer_pin_mismatch=true,reading_proxy_unsupported=true,response_bound=true,
                        reading_certificate_rejected=true,reading_http_unauthorized=true,
                        reading_http_retryable=true,unverified_reading_receipt=true}
                    report.error_code=allowed[reason] and reason or "paired_sequence_failed"
                    check(false)
                end
                local event=deps.null
                if i==1 and attempt==1 then
                    -- Deliberately lose this source receipt; the exact same
                    -- native lines are retried with a fresh request nonce.
                    report.deliberately_discarded_responses=1
                    if runtime.seed_only then
                        local accepted=assert(paired.acknowledged(session,receipt,bytes))
                        check(#accepted==1 and accepted[1].canonical_commit==batch.revision
                            and accepted[1].event_id==inspected.entries[1].event_id)
                        check(queue.status().pending==3 and queue.status().review==1)
                        report.checked_receipts=1
                        report.outbox_final_pending=3
                        report.outbox_identity_preserved=true
                        report.steps[1]={step="seed_discard_before_ack",request_id=id,
                            batch_id=inspected.batch_id,request_sha256=deps.sha256(bytes),
                            issued_at_utc=issued,expires_at_utc=expires,receipt_event=deps.null}
                        report.phase="outbox_seed_receipt_discarded"
                        return
                    end
                else
                    local accepted=assert(paired.acknowledged(session,receipt,bytes))
                    local entry=inspected.entries[#batch.lines]
                    check(#accepted==1 and accepted[1].index==#batch.lines-1
                        and accepted[1].event_id==entry.event_id
                        and accepted[1].line_digest==entry.line_digest
                        and accepted[1].native_digest==entry.native_digest
                        and accepted[1].canonical_commit==batch.revision)
                    check(not paired.acknowledged(session,{},bytes))
                    event=accepted[1]
                    report.checked_receipts=report.checked_receipts+1
                    if queue then
                        check(not queue.consume_receipt(session,{},bytes))
                        report.outbox_raw_receipt_rejections=report.outbox_raw_receipt_rejections+1
                        local result=assert(queue.consume_receipt(session,receipt,bytes))
                        check(result.canonical_ack==false and result.source_watermark==nil
                            and result.review_retained==1)
                        check(result.removed==((i==1 or attempt==1) and 1 or 0))
                        report.outbox_pruned=report.outbox_pruned+result.removed
                    end
                end
                report.steps[#report.steps+1]={step=labels[i].."_"..attempt,
                    request_id=id,batch_id=inspected.batch_id,request_sha256=deps.sha256(bytes),
                    issued_at_utc=issued,expires_at_utc=expires,receipt_event=event}
                if queue then
                    local status=assert(queue.status())
                    check(status.review==1 and status.pending==3-report.outbox_pruned)
                    report.steps[#report.steps].outbox_pending=status.pending
                end
            end
        end
        check(report.checked_receipts==5 and report.deliberately_discarded_responses==1)
        if queue then
            local context=queue.context()
            check(report.outbox_pruned==3 and queue.status().pending==0 and queue.status().review==1
                and context.device_id==binding.device_id and context.source_epoch==binding.source_epoch)
            report.outbox_final_pending=0
            report.outbox_identity_preserved=true
        end
        report.phase="paired_receipts_checked"
    end)
    if session then pcall(paired.close,session) end
    if not ok then report.phase="failed";report.error_code=report.error_code or "paired_sequence_failed" end
    return report
end
return M
