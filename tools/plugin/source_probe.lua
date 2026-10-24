-- Finite schema-3 trial on fresh SYNTHETIC Statistics only. No network or user DB.
local M = {}
M.cases={"collection_before_commit","collection_after_commit","continuation","generation","upgrade"}
local OBSERVED="2026-10-24T00:00:00.000Z"
local PRIMARY="/quartzo_sync_state.sqlite3"
local function check(value) if not value then error("source_probe_check_failed",0) end end
local function must(value) check(type(value)=="table");return value end
local function bytes(path)
    local file=assert(io.open(path,"rb"))
    local result=file:read(2097153)
    check(file:close() and result and #result<=2097152)
    return result
end
local function same(a,b) check(a.device_id==b.device_id and a.source_epoch==b.source_epoch) end
local function sql(sdk,path,body)
    local conn=sdk.open(path,"rwc")
    local ok,result=pcall(body,conn)
    local closed=pcall(conn.close,conn)
    check(ok and closed)
    return result
end
local function statistics(sdk,fs,path,rows)
    check(fs.symlinkattributes(path)==nil)
    sql(sdk,path,function(conn)
        conn:exec("BEGIN IMMEDIATE")
        conn:exec([[PRAGMA user_version=20221111;
CREATE TABLE book(id INTEGER PRIMARY KEY AUTOINCREMENT,title TEXT,authors TEXT,
notes INTEGER,last_open INTEGER,highlights INTEGER,pages INTEGER,series TEXT,
language TEXT,md5 TEXT,total_read_time INTEGER,total_read_pages INTEGER);
CREATE UNIQUE INDEX book_title_authors_md5 ON book(title,authors,md5);
CREATE TABLE page_stat_data(id_book INTEGER,page INTEGER NOT NULL DEFAULT 0,
start_time INTEGER NOT NULL DEFAULT 0,duration INTEGER NOT NULL DEFAULT 0,
total_pages INTEGER NOT NULL DEFAULT 0,UNIQUE(id_book,page,start_time),
FOREIGN KEY(id_book) REFERENCES book(id));
CREATE INDEX page_stat_data_start_time ON page_stat_data(start_time);]])
        if rows then
            conn:exec("INSERT INTO book(title) VALUES('synthetic source fixture')")
            for page=1,rows do
                conn:exec("INSERT INTO page_stat_data VALUES(1,"..page..",100,20,300)")
            end
            conn:exec("INSERT INTO page_stat_data VALUES(1,0,100,20,300)")
        end
        conn:exec("COMMIT")
    end)
end
local function fill(sdk,path)
    sql(sdk,path,function(conn)
        conn:exec("BEGIN IMMEDIATE;INSERT INTO book(title) VALUES('synthetic source fixture');"
            .."INSERT INTO page_stat_data VALUES(1,1,100,20,300),(1,2,100,20,300),(1,0,100,20,300)")
        conn:exec("COMMIT")
    end)
end
local function status(queue,pending,review,unresolved)
    local state=must(queue.status())
    check(state.pending==pending and state.review==review and state.unresolved_review==unresolved
        and state.source_watermark==nil and state.canonical_ack==false)
end
local function lines(queue)
    return table.concat(must(queue.pending(100)).event_lines,"\n")
end
function M.run(root,run_id,outbox,codec,sdk,fs,process)
    local report={probe_version=1,probe_kind="source_lifecycle",phase="failed",source_data="synthetic",
        uses_synthetic_clock=true,user_statistics_accessed=false,synthetic_statistics_accessed=true,
        network_accessed=false,wifi_changed=false,canonical_ack=false,ack_watermark_changed=false,
        source_epoch_verified=false,gate4_passed=false,case_checks={}}
    local system
    local ok=pcall(function()
        check(type(run_id)=="string" and #run_id==32 and not run_id:find("[^a-f0-9]"))
        check(type(root)=="string" and root:sub(1,1)=="/" and fs.symlinkattributes(root)==nil)
        check(fs.mkdir(root))
        check(type(process)=="table" and type(process.stop_owned_child)=="function")
        system=process.native_process_system()
        local runtime={codec=codec,sqlite=sdk,filesystem=fs}
        local statistics_owner=require("quartzo/statistics")
        local collector=require("quartzo/collector")
        local devices={}
        for _,name in ipairs(M.cases) do
            local directory=root.."/"..name
            check(fs.mkdir(directory))
            local source=directory.."/synthetic-statistics.sqlite3"
            statistics(sdk,fs,source,name=="continuation" and 251
                or ((name=="generation" or name=="upgrade") and 2 or nil))
            local queue,context
            if name=="upgrade" then
                -- Test-owned legacy fixture through the existing schema-1 owner.
                queue=must(outbox.create(directory,"probe_"..run_id,runtime))
                local preview=must(statistics_owner.review_source(source,runtime))
                local checkpoint=must(statistics_owner.accept_source_review(preview.review,function(value) return value end))
                sql(sdk,directory..PRIMARY,function(conn)
                    conn:exec("CREATE TABLE source(id INTEGER PRIMARY KEY CHECK(id=1),volume TEXT NOT NULL,inode TEXT NOT NULL,"
                        .."book_sequence TEXT NOT NULL,first_event TEXT NOT NULL,last_event TEXT NOT NULL,history_boundary TEXT NOT NULL)")
                    local stmt=conn:prepare("INSERT INTO source VALUES(1,?,?,?,?,?,?)")
                    stmt:bind(checkpoint.volume,checkpoint.inode,checkpoint.book_sequence,
                        checkpoint.first_event,checkpoint.last_event,checkpoint.history_boundary)
                    stmt:step();stmt:close()
                    conn:exec("PRAGMA user_version=2")
                end)
                queue=must(outbox.open(directory,runtime))
            else
                local preview=must(outbox.review_source(directory,source,runtime))
                queue=must(outbox.enroll(directory,preview.review,runtime))
            end
            context=queue.context()
            check(context.device_id:match("^qrd_[a-f0-9]+$") and #context.device_id==36
                and not devices[context.device_id])
            devices[context.device_id]=true
            if name:match("^collection_") then
                fill(sdk,source)
                local before=bytes(source)
                process.stop_owned_child(system,fs,sdk,directory,name,function(wrapped)
                    local child_runtime={codec=codec,sqlite=wrapped,filesystem=fs}
                    local child=must(outbox.open(directory,child_runtime))
                    local preview=must(child.review_collection(source,OBSERVED))
                    must(child.stage_collection(preview.pass))
                end)
                queue=must(outbox.open(directory,runtime))
                same(queue.context(),context)
                local committed=name=="collection_after_commit"
                status(queue,committed and 2 or 0,committed and 1 or 0,committed and 1 or 0)
                check(bytes(source)==before)
                must(queue.check_source(source))
                if committed then
                    local selected=lines(queue)
                    local backup=must(queue.backup())
                    local reviewed=must(outbox.inspect_backup(directory,backup.backup_leaf,runtime))
                    check(os.rename(directory..PRIMARY,directory.."/preserved-state.sqlite3"))
                    local missing,code=outbox.review_source(directory,source,runtime)
                    check(not missing and code=="outbox_recovery_review_required")
                    queue=must(outbox.restore(directory,backup.backup_leaf,runtime,reviewed))
                    same(queue.context(),context)
                    check(lines(queue)==selected)
                    local replay=must(queue.review_collection(source,OBSERVED,100,"all_history"))
                    must(queue.stage_collection(replay.pass))
                    check(lines(queue)==selected)
                    status(queue,2,1,1)
                end
            elseif name=="continuation" then
                local before=bytes(source)
                local preview=must(queue.review_collection(source,OBSERVED,100))
                local batches=0
                while preview do
                    batches=batches+1;check(batches<=3)
                    local staged=must(queue.stage_collection(preview.pass))
                    if staged.complete then preview=nil
                    else preview=must(queue.next_collection(preview.pass,OBSERVED)) end
                end
                check(batches==3 and bytes(source)==before)
                status(queue,251,1,1)
                local reviewed=must(queue.review_rejections(100))
                must(queue.resolve_rejections(reviewed.review))
                status(queue,251,1,0)
            elseif name=="generation" then
                local replacement=directory.."/nonempty-replacement.sqlite3"
                statistics(sdk,fs,replacement,2)
                local before=bytes(directory..PRIMARY)
                local rejected,code=queue.review_new_generation(replacement)
                check(not rejected and code=="statistics_source_reconciliation_required" and bytes(directory..PRIMARY)==before)
                local empty=directory.."/empty-replacement.sqlite3"
                statistics(sdk,fs,empty)
                local preview=must(queue.review_new_generation(empty))
                local changed=must(queue.begin_new_generation(preview.review))
                queue=changed.queue
                local next_context=queue.context()
                check(next_context.device_id==context.device_id and next_context.source_epoch~=context.source_epoch)
                local previous=must(outbox.inspect_backup(directory,changed.backup_leaf,runtime))
                same(previous,context)
                must(queue.check_source(empty))
                status(queue,0,0,0)
            elseif name=="upgrade" then
                local fields={device_id=context.device_id,source_epoch=context.source_epoch,observed_at_utc=OBSERVED}
                must(queue.stage(must(collector.collect(source,fields,codec,sdk))))
                local selected=lines(queue)
                local preview=must(queue.review_upgrade(source))
                local upgraded=must(queue.upgrade_queue(preview.review))
                queue=upgraded.queue
                same(queue.context(),context)
                check(lines(queue)==selected)
                local backup=must(outbox.inspect_backup(directory,upgraded.backup_leaf,runtime))
                same(backup,context)
                status(queue,2,1,1)
                must(queue.check_source(source))
            end
            report.case_checks[name]=true
        end
        report.process_stop_cases=2
        report.same_second_events=251
        report.recovery_identity_retained=true
        report.legacy_upgrade_preserved=true
        report.nonempty_generation_refused=true
        report.phase="passed"
    end)
    if system and system.restore then
        local restored=pcall(system.restore)
        if not restored then ok=false end
    end
    if not ok then report.phase="failed";report.error_code="source_probe_check_failed" end
    return report
end
return M
