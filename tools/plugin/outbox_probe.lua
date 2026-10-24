-- Isolated synthetic offline acceptance of the SAME delivery-state owner.
-- No Statistics, user settings, network, canonical receipt or source cursor.
local M = {}
M.cases = {"stage_before_commit","stage_after_commit","backup_before_commit",
    "backup_after_commit","restore_before_commit","restore_after_commit"}
local function check(value)
    if not value then error("outbox_probe_check_failed",0) end
end
local function must(value)
    check(type(value)=="table")
    return value
end
local function same_context(a,b)
    check(a.device_id==b.device_id and a.source_epoch==b.source_epoch)
end
local function file_bytes(path, maximum)
    local file=assert(io.open(path,"rb"))
    local bytes=file:read(maximum+1)
    check(file:close())
    check(type(bytes)=="string" and #bytes<=maximum)
    return bytes
end
local function fixture(codec, context)
    local lines={}
    for i=1,2 do
        lines[i]=codec.encode_event({schema_version=1,source="koreader_statistics",
            device_id=context.device_id,source_epoch=context.source_epoch,book_row_id=17,page=3+i,
            started_at_utc=i==1 and "2026-10-14T02:50:00.000Z" or "2026-10-14T02:50:01.000Z",
            duration_seconds=i==1 and 20 or 30,total_pages=120,
            observed_at_utc="2026-10-16T12:00:00.000Z",source_schema_version="fixture_only"})
        check(type(lines[i])=="string")
    end
    return {event_lines=lines,scanned_count=3,rejections={{reason="invalid_statistics_event",
        started_at=1791946202,row_id=3,
        integer_fields={book_row_id="17",page="0",duration_seconds="10",total_pages="120"},
        field_types={"integer","integer","integer","integer","integer"}}}}
end
local function pending_equal(queue, expected, count)
    local result=must(queue.pending(10))
    check(result.canonical_ack==false and #result.event_lines==count)
    local seen={}
    for _,line in ipairs(result.event_lines) do
        check(not seen[line] and (line==expected[1] or line==expected[2]))
        seen[line]=true
    end
end
local function recovery_leaf(fs, root)
    local selected
    for name in fs.dir(root) do
        local hex=name:match("^quartzo_sync_recovery_([a-f0-9]+)%.sqlite3$")
        if hex then check(#hex==32 and selected==nil);selected=name end
    end
    check(selected~=nil)
    return selected
end
local function verify_copy(sdk, codec, path, context, expected)
    local conn=sdk.open(path,"ro")
    local ok=pcall(function()
        local device,epoch=conn:rowexec("SELECT device_id,source_epoch FROM identity WHERE id=1")
        same_context({device_id=device,source_epoch=epoch},context)
        check(tonumber(conn:rowexec("SELECT COUNT(*) FROM review"))==1)
        local stmt=conn:prepare("SELECT line,event_id,native_digest FROM pending LIMIT 3")
        local seen={}
        for _=1,2 do
            local row=stmt:step()
            check(row and (row[1]==expected[1] or row[1]==expected[2]) and not seen[row[1]])
            local entry=must(codec.inspect_event(row[1]))
            check(entry.canonical_ack==false and entry.event_id==row[2] and entry.native_digest==row[3])
            seen[row[1]]=true
        end
        check(stmt:step()==nil)
        stmt:close()
    end)
    local closed=pcall(conn.close,conn)
    check(ok and closed)
end
local function process_system()
    check(jit and jit.os=="Linux" and (jit.arch=="arm" or jit.arch=="x64"))
    local ffi=require("ffi")
    require("ffi/posix_h")
    ffi.cdef[[
        typedef void (*quartzo_probe_signal_handler)(int);
        quartzo_probe_signal_handler signal(int, quartzo_probe_signal_handler);
        int prctl(int, ...);
    ]]
    local C=ffi.C
    -- Resolve every callable before fork; a child must never return to the driver.
    local system={ffi=ffi,fork=C.fork,kill=C.kill,waitpid=C.waitpid,exit=C._exit,
        usleep=C.usleep,getpid=C.getpid,getppid=C.getppid,prctl=C.prctl,signal=C.signal}
    -- These diagnostics support the pinned Linux ARM32 target and x64 fixture.
    -- Default SIGCHLD keeps an exited owned child unreused until our waitpid.
    local default=ffi.cast("quartzo_probe_signal_handler",0)
    local failure=ffi.cast("quartzo_probe_signal_handler",-1)
    local previous=C.signal(17,default)
    check(previous~=failure)
    system.restore=function() check(C.signal(17,previous)~=failure) end
    return system
end
-- The paired diagnostic reuses this same bounded native process setup. Merely
-- loading this module has no process or filesystem effect.
M.native_process_system = process_system
local function stop_child(system, fs, sdk, root, name, body)
    local ffi=system.ffi
    local marker=root.."/gate.ready"
    check(fs.symlinkattributes(marker)==nil)
    local parent=system.getpid()
    local pid=system.fork()
    check(pid>=0)
    if pid==0 then
        local zero=ffi.cast("unsigned long",0)
        -- Only this new child: kernel termination on diagnostic-parent death.
        -- Check PPID too, covering death between fork and prctl.
        if system.prctl(1,ffi.cast("unsigned long",9),zero,zero,zero)~=0
            or system.getppid()~=parent then system.exit(111) end
        local function point()
            if system.getppid()~=parent then system.exit(111) end
            local file=assert(io.open(marker,"wb"))
            check(file:write("ready") and file:close())
            -- Bounded even if the parent fails; this is not a persistent worker.
            for _=1,50 do
                if system.getppid()~=parent then system.exit(111) end
                system.usleep(100000)
            end
            system.exit(112)
        end
        local wrapped={open=function(path,mode)
            local conn=sdk.open(path,mode)
            conn:exec("PRAGMA cache_size=1")
            conn:exec("PRAGMA cache_spill=ON")
            return setmetatable({exec=function(_,sql)
                if sql=="PRAGMA recovery.synchronous=EXTRA" then
                    conn:exec("PRAGMA recovery.cache_size=1")
                    conn:exec("PRAGMA recovery.cache_spill=ON")
                end
                if sql=="COMMIT" and name:match("_before_commit$") then point() end
                local first,second=conn:exec(sql)
                if sql=="COMMIT" and name:match("_after_commit$") then point() end
                return first,second
            end},{__index=function(_,method)
                return function(_,...) return conn[method](conn,...) end
            end})
        end}
        pcall(body,wrapped)
        system.exit(113)
    end
    local status=ffi.new("int[1]")
    local reaped=false
    local ok=pcall(function()
        local ready=false
        for _=1,50 do
            if fs.symlinkattributes(marker) then ready=true;break end
            local state=system.waitpid(pid,status,1) -- WNOHANG on supported Linux ABIs.
            if state~=0 then reaped=true;check(false) end
            system.usleep(100000)
        end
        check(ready and file_bytes(marker,16)=="ready")
        if name:match("_before_commit$") then
            local journal
            for leaf in fs.dir(root) do
                if leaf:match("%.sqlite3%-journal$") then
                    check(journal==nil);journal=root.."/"..leaf
                end
            end
            check(journal~=nil)
            local file=assert(io.open(journal,"rb"))
            local header=file:read(8)
            check(file:close() and header and #header==8 and header~=string.rep("\0",8))
        end
        local state=system.waitpid(pid,status,1)
        if state~=0 then reaped=true;check(false) end
        check(system.kill(pid,9)==0)
        check(system.waitpid(pid,status,0)==pid)
        reaped=true
        check(bit.band(status[0],127)==9) -- A real SIGKILL, not a returned error.
    end)
    if not reaped then
        system.kill(pid,9)
        system.waitpid(pid,status,0)
    end
    check(ok)
end
-- Shared only by the isolated source-lifecycle diagnostic; loading is inert.
M.stop_owned_child = stop_child
function M.run(root, run_id, outbox, codec, sdk, fs)
    local report={probe_version=1,phase="failed",source_data="synthetic",uses_synthetic_clock=true,
        statistics_accessed=false,network_accessed=false,wifi_changed=false,source_cursor_changed=false,
        canonical_ack=false,canonical_persistence_proven=false,paired_receipt_proven=false,
        source_epoch_verified=false,gate4_passed=false,case_checks={}}
    local system
    local ok=pcall(function()
        check(type(run_id)=="string" and #run_id==32 and not run_id:find("[^a-f0-9]"))
        check(type(root)=="string" and root:sub(1,1)=="/" and fs.symlinkattributes(root)==nil)
        check(fs.mkdir(root))
        system=process_system()
        local ids={}
        for _,name in ipairs(M.cases) do
            local directory=root.."/"..name
            check(fs.mkdir(directory))
            local runtime={codec=codec,sqlite=sdk}
            local queue=must(outbox.create(directory,"probe_"..run_id,runtime))
            local context=queue.context()
            check(context.device_id:match("^qrd_[a-f0-9]+$") and #context.device_id==36 and not ids[context.device_id])
            ids[context.device_id]=true
            local batch=fixture(codec,context)
            local leaf,preserved_hash
            if not name:match("^stage_") then must(queue.stage(batch)) end
            if name:match("^restore_") then
                local snapshot=must(queue.backup())
                leaf=snapshot.backup_leaf
                local original=directory.."/quartzo_sync_state.sqlite3"
                local preserved=directory.."/quartzo_sync_state_preserved.sqlite3"
                check(fs.symlinkattributes(preserved)==nil)
                preserved_hash=file_bytes(original,2097152)
                check(os.rename(original,preserved)) -- Only fresh isolated synthetic state.
            end
            stop_child(system,fs,sdk,directory,name,function(wrapped)
                local child_runtime={codec=codec,sqlite=wrapped}
                if name:match("^restore_") then must(outbox.restore(directory,leaf,child_runtime))
                else
                    local active=must(outbox.open(directory,child_runtime))
                    if name:match("^stage_") then must(active.stage(batch))
                    else must(active.backup()) end
                end
            end)
            if name=="restore_before_commit" then
                local absent,reason=outbox.open(directory,runtime)
                check(absent==nil and reason=="unsupported_outbox_schema")
            else
                local active=must(outbox.open(directory,runtime))
                same_context(active.context(),context)
                local status=must(active.status())
                local expected=name=="stage_before_commit" and 0 or 2
                check(status.pending==expected and status.review==(expected==0 and 0 or 1)
                    and status.canonical_ack==false and status.source_watermark==nil)
                pending_equal(active,batch.event_lines,expected)
                -- Real paired owner, no approved session: matching raw claims
                -- cannot prune. Offline tests never manufacture a receipt.
                local rejected,reason=active.consume_receipt({}, {accepted_events=batch.event_lines},"untrusted")
                check(rejected==nil and reason=="unverified_reading_receipt")
                check(must(active.status()).pending==expected)
            end
            if name:match("^backup_") or name:match("^restore_") then
                leaf=leaf or recovery_leaf(fs,directory)
                local snapshot,reason=outbox.inspect_backup(directory,leaf,runtime)
                if name=="backup_before_commit" then
                    check(snapshot==nil and reason=="unsupported_outbox_schema")
                else
                    same_context(must(snapshot),context)
                    check(snapshot.pending==2 and snapshot.review==1 and snapshot.canonical_ack==false)
                    verify_copy(sdk,codec,directory.."/"..leaf,context,batch.event_lines)
                end
            end
            if preserved_hash then
                check(file_bytes(directory.."/quartzo_sync_state_preserved.sqlite3",2097152)==preserved_hash)
                verify_copy(sdk,codec,directory.."/quartzo_sync_state_preserved.sqlite3",context,batch.event_lines)
            end
            report.case_checks[name]=true
        end
        report.process_stop_cases=6
        report.raw_receipt_rejections=5
        report.native_entropy_cases=6
        report.identity_and_pending_verified=true
        report.phase="passed"
    end)
    if system then
        local restored=pcall(system.restore)
        if not restored then ok=false end
    end
    if not ok then report.phase="failed";report.error_code="outbox_probe_check_failed" end
    return report
end
return M
