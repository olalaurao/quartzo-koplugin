-- Opt-in finite G04 composition. No file, credential store, Statistics, retry,
-- outbox/cursor or Wi-Fi owner. Approval must come from explicit trusted
-- out-of-band delivery, never a hash/role advertised by the network peer.
local M = {}
local sessions=setmetatable({}, {__mode="k"})
local scope_keys = {"binding_id","vault_scope","device_id","source_epoch"}
local document_keys = {"pairing_version","receiver_role","endpoint","certificate_pem",
    "peer_certificate_sha256","binding","token","not_before_utc","expires_at_utc"}
local transport_errors={reading_transport_failed=true,reading_peer_unverified=true,
    reading_peer_pin_mismatch=true,reading_proxy_unsupported=true,response_bound=true}
local function check(value) if not value then error("invalid_approved_reading_pairing",0) end end
local function hex(value)
    return type(value)=="string" and #value==64 and not value:find("[^a-f0-9]")
end
local function keys(deps,value,expected)
    check(deps.kind(value)=="object")
    local allowed={}
    for _,key in ipairs(expected) do allowed[key]=true;check(value[key]~=nil) end
    for key in pairs(value) do check(allowed[key]) end
end

-- Local composition root supplies trusted SDK/provider modules and the
-- independently approved exact document hash. This is deliberately not an
-- HTTP discovery/importer or a public boolean promoting decoded claims.
function M.open(document_bytes,approved_sha256,runtime)
    local ok,value=pcall(function()
        check(type(runtime)=="table" and type(runtime.now)=="function")
        local deps,codec,carrier=runtime.deps,runtime.codec,runtime.carrier
        check(type(document_bytes)=="string" and #document_bytes>0 and #document_bytes<=8192
            and hex(approved_sha256) and deps.sha256(document_bytes)==approved_sha256)
        local document=deps.decode_json(document_bytes)
        keys(deps,document,document_keys)
        check(document.pairing_version==1 and document.receiver_role=="canonical_reading_activity_v1"
            and type(document.certificate_pem)=="string" and #document.certificate_pem<=4096
            and document.certificate_pem:match("^%-%-%-%-%-BEGIN CERTIFICATE%-%-%-%-%-\n")
            and hex(document.peer_certificate_sha256)
            and type(document.token)=="string" and #document.token==43
            and not document.token:find("[^A-Za-z0-9_-]"))
        keys(deps,document.binding,scope_keys)
        local binding=deps.object({})
        for _,key in ipairs(scope_keys) do
            local item=document.binding[key]
            check(type(item)=="string" and #item>0 and #item<=128 and not item:find("[^A-Za-z0-9_-]"))
            binding[key]=item
        end
        local now=runtime.now -- Capture once; changing caller table cannot retarget this session.
        local first,last,invalidated=document.not_before_utc,nil,false
        local expires,token=document.expires_at_utc,document.token
        local context={endpoint=document.endpoint,binding_id=binding.binding_id,
            peer_certificate_sha256=document.peer_certificate_sha256,ca_file=runtime.ca_file}
        local function current()
            check(not invalidated)
            local succeeded,instant=pcall(now)
            if not succeeded or not codec.check_pairing_window(first,expires,instant,last) then
                invalidated=true;check(false)
            end
            last=instant
            return instant
        end
        current()
        -- Existing shared carrier owns HTTPS, CA validation, pre-send leaf pin,
        -- byte bounds and opaque request/token/context-bound delivery.
        local send=carrier.pinned_wire_transport(context,runtime.https,runtime.ltn12,runtime.http)
        local read_delivery=carrier.read_pinned_delivery
        local receipts=setmetatable({}, {__mode="k"})
        local session={}
        function session.prepare(event_lines,request_id,issued_at_utc,expires_at_utc)
            local succeeded,bytes=pcall(function()
                check(type(event_lines)=="table" and #event_lines>=1 and #event_lines<=100)
                local count=#event_lines
                local selected=deps.array({})
                for key in pairs(event_lines) do
                    check(type(key)=="number" and key%1==0 and key>=1 and key<=count)
                end
                for i=1,count do check(type(event_lines[i])=="string");selected[i]=event_lines[i] end
                for _,line in ipairs(selected) do
                    local entry=codec.inspect_event(line)
                    check(entry and entry.canonical_ack==false and entry.device_id==binding.device_id
                        and entry.source_epoch==binding.source_epoch)
                end
                local fields=deps.object({protocol_version=1,request_id=request_id,
                    issued_at_utc=issued_at_utc,expires_at_utc=expires_at_utc,event_lines=selected})
                for key,value in pairs(binding) do fields[key]=value end
                local result=codec.encode_request(fields,binding,current())
                check(type(result)=="string")
                return result -- Request preparation grants no receipt/ACK.
            end)
            if not succeeded then return nil,"invalid_reading_delivery_request" end
            return bytes
        end
        function session.attempt(request_bytes)
            local succeeded,receipt,reason=pcall(function()
                check(codec.inspect_request(request_bytes,binding,current()))
                local status,body,_,delivery=send(request_bytes,token,"good")
                if status==nil then
                    -- The pinned carrier emits fixed codes only. Do not expose
                    -- arbitrary SDK messages, certificate contents or paths.
                    if body=="certificate verify failed" then return nil,"reading_certificate_rejected" end
                    return nil,transport_errors[body] and body or "unverified_reading_receipt"
                end
                if status==401 or status==403 then return nil,"reading_http_unauthorized" end
                if status==429 or (type(status)=="number" and status>=500 and status<=599) then
                    return nil,"reading_http_retryable"
                end
                check(status==200 and delivery~=nil)
                local verified,original=read_delivery(delivery,request_bytes,token,context)
                check(verified==200 and original==body)
                local response=codec.decode_response(body,request_bytes,binding,current())
                check(response and response.canonical_ack==false and response.accepted_events==nil)
                local accepted={}
                for _,claim in ipairs(response.untrusted_claims) do
                    if claim.outcome=="committed" or claim.outcome=="duplicate" then
                        accepted[#accepted+1]={index=claim.index,line_digest=claim.line_digest,
                            event_id=claim.event_id,native_digest=claim.native_digest,
                            canonical_commit=claim.canonical_commit}
                    end
                end
                local result=setmetatable({}, {__metatable="approved_reading_receipt"})
                receipts[result]={request=request_bytes,accepted=accepted}
                return result
            end)
            if not succeeded then return nil,"unverified_reading_receipt" end
            return receipt,reason
        end
        -- Outbox composition must consume this session-bound capability,
        -- not a caller-constructed table or a parsed committed claim. Copy all
        -- returned rows; mutating observations cannot change a later lookup.
        function session.acknowledged(receipt,request_bytes)
            local succeeded,events=pcall(function()
                current()
                local saved=receipts[receipt]
                check(saved and saved.request==request_bytes)
                local result={}
                for i,row in ipairs(saved.accepted) do
                    local copy={}
                    for key,item in pairs(row) do copy[key]=item end
                    result[i]=copy
                end
                return result
            end)
            if not succeeded then return nil,"unverified_reading_receipt" end
            return events
        end
        function session.close() invalidated=true end
        local handle=setmetatable({}, {__metatable="approved_reading_pairing",
            __tostring=function() return "ReadingPairedExchange(redacted)" end})
        sessions[handle]=session
        return handle
    end)
    if not ok then return nil,"invalid_approved_reading_pairing" end
    return value
end
function M.prepare(handle,event_lines,request_id,issued_at_utc,expires_at_utc)
    local session=sessions[handle]
    if not session then return nil,"invalid_approved_reading_pairing" end
    return session.prepare(event_lines,request_id,issued_at_utc,expires_at_utc)
end
function M.attempt(handle,request_bytes)
    local session=sessions[handle]
    if not session then return nil,"invalid_approved_reading_pairing" end
    return session.attempt(request_bytes)
end
function M.acknowledged(handle,receipt,request_bytes)
    local session=sessions[handle]
    if not session then return nil,"unverified_reading_receipt" end
    return session.acknowledged(receipt,request_bytes)
end
function M.close(handle)
    local session=sessions[handle]
    if session then session.close();sessions[handle]=nil end
end
return M
