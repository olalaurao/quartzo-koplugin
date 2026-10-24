-- Disposable single-use KUAL diagnostic, launched in the actual KOReader root.
local directory="/mnt/us/extensions/quartzo-wire-tls-probe"
local function read(path,limit)
    local file=assert(io.open(path,"rb"))
    local bytes=file:read(limit+1)
    assert(file:close() and bytes and #bytes<=limit)
    return bytes
end
local function hex(value,count)
    return type(value)=="string" and #value==count and not value:find("[^a-f0-9]")
end
local files={"codec.lua","koreader_deps.lua","exchange.lua","sequence.lua","client.lua","outbox.lua","process.lua",
    "kindle.lua","run.sh","menu.json","config.xml","private-pairing.json","server.pem","synthetic-fixture.json"}
local function write_report(leaf,report)
    local encoded=assert(require("dkjson").encode(report))
    assert(#encoded<=12288)
    local target=directory.."/"..leaf
    local file=assert(io.open(target..".tmp","wb"))
    assert(file:write(encoded) and file:close() and os.rename(target..".tmp",target))
end
local function seed_child(body)
    local system=dofile(directory.."/process.lua").native_process_system()
    local ffi=system.ffi
    local status=ffi.new("int[1]")
    local parent=system.getpid()
    local pid=system.fork()
    if pid<0 then system.restore();error("paired_sequence_child_failed",0) end
    if pid==0 then
        local zero=ffi.cast("unsigned long",0)
        if system.prctl(1,ffi.cast("unsigned long",9),zero,zero,zero)~=0
            or system.getppid()~=parent then system.exit(111) end
        local ok=pcall(body,tonumber(system.getpid()))
        system.exit(ok and 0 or 112)
    end
    local reaped=false
    local ok=pcall(function()
        -- Only our own unreused child PID. Parent death also kills the child.
        for _=1,400 do
            local result=system.waitpid(pid,status,1)
            if result==pid then reaped=true;assert(status[0]==0);return end
            assert(result==0)
            system.usleep(100000)
        end
        error("paired_sequence_child_timeout",0)
    end)
    if not reaped then
        system.kill(pid,9)
        assert(system.waitpid(pid,status,0)==pid)
    end
    system.restore()
    assert(ok)
    return tonumber(pid),tonumber(parent)
end
local function execute()
    require("setupkoenv")
    local json=require("dkjson")
    local report={probe_revision="canonical-paired-sequence-v1",phase="failed",source_data="synthetic",
        canonical_ack=false,canonical_persistence_proven=false,physical_execution_attested=false,
        statistics_accessed=false,source_cursor_changed=false,wifi_changed=false}
    local ok=pcall(function()
        local deps=assert(dofile(directory.."/koreader_deps.lua").load(require))
        local manifest_bytes=read(directory.."/bundle-manifest.json",8192)
        local manifest=deps.decode_json(manifest_bytes)
        assert(manifest.probe_revision=="canonical-paired-sequence-v1" and hex(manifest.run_id,32)
            and manifest.koreader_baseline=="v2026.07.1" and hex(manifest.source_commit,40))
        local native=manifest.files["outbox-seed.sqlite3"]~=nil
        local allowed={}
        for _,name in ipairs(files) do allowed[name]=true end
        if native then allowed["outbox-seed.sqlite3"]=true end
        for name in pairs(manifest.files) do assert(allowed[name]) end
        for _,name in ipairs(files) do
            assert(hex(manifest.files[name],64)
                and deps.sha256(read(directory.."/"..name,65536))==manifest.files[name])
        end
        if native then
            assert(hex(manifest.files["outbox-seed.sqlite3"],64)
                and deps.sha256(read(directory.."/outbox-seed.sqlite3",65536))==manifest.files["outbox-seed.sqlite3"])
        end
        report.run_id,report.source_commit=manifest.run_id,manifest.source_commit
        report.manifest_digest=deps.sha256(manifest_bytes)
        local fixture=deps.decode_json(read(directory.."/synthetic-fixture.json",16384))
        assert(fixture.run_id==manifest.run_id)
        assert(native==(type(fixture.binding.device_id)=="string"
            and fixture.binding.device_id:sub(1,4)=="qrd_"))
        local baseline=read("git-rev",64):gsub("%s+$","")
        assert(baseline=="v2026.07.1")
        local socket,https=require("socket"),require("ssl.https")
        local function seconds()
            local value=socket.gettime()
            assert(type(value)=="number" and value==value and value>0 and value<253402300000)
            return math.floor(value)
        end
        local function utc(value) return os.date("!%Y-%m-%dT%H:%M:%S",value)..".000Z" end
        local counter=0
        local sequence=dofile(directory.."/sequence.lua")
        local codec_module=dofile(directory.."/codec.lua")
        local paired=dofile(directory.."/exchange.lua")
        local runtime={
                document_bytes=read(directory.."/private-pairing.json",8192),
                -- This approved hash is delivered by the trusted USB installer
                -- from the identity-checked app. Never self-approve HTTP input.
                approved_sha256=manifest.files["private-pairing.json"],
                carrier=dofile(directory.."/client.lua"),ca_file=directory.."/server.pem",
                https=https,ltn12=require("ltn12"),http=require("socket.http"),
                now=function() return utc(seconds()) end,
                window=function() local value=seconds();return utc(value),utc(value+30) end,
                nonce=function() counter=counter+1;assert(counter<=6)
                    return "qrtr_"..manifest.run_id:sub(1,16)..string.format("%016x",counter) end,
            }
        local native_files={dkjson="common/dkjson.lua",sha2="ffi/sha2.lua"}
        local before={}
        if native then
            native_files.sqlite_wrapper="common/lua-ljsqlite3/init.lua"
            native_files.posix="ffi/posix_h.lua"
            native_files.sqlite="libs/libsqlite3.so.0"
            native_files.filesystem="libs/libkoreader-lfs.so"
            native_files.luajit="luajit"
            -- The same pinned x64 SDK exercises the process branch on CI.
            -- Physical collection separately requires the actual ARM report.
            assert(jit.arch=="arm" or jit.arch=="x64")
            local fs=require("libs/libkoreader-lfs")
            local root=directory.."/outbox-state"
            assert(fs.symlinkattributes(root)==nil and fs.mkdir(root))
            local target=root.."/quartzo_sync_state.sqlite3"
            assert(fs.symlinkattributes(target)==nil)
            local output=assert(io.open(target,"wb"))
            assert(output:write(read(directory.."/outbox-seed.sqlite3",65536)) and output:close())
            runtime.outbox=dofile(directory.."/outbox.lua")
            runtime.queue_root=root
            runtime.sqlite=require("lua-ljsqlite3/init")
            runtime.attributes=fs.symlinkattributes
            package.loaded["quartzo/paired_exchange"]=paired
            for key,path in pairs(native_files) do before[key]=deps.sha256(read(path,2097152)) end
            local child,parent=seed_child(function(pid)
                runtime.seed_only=true
                runtime.nonce=function()
                    return "qrtr_"..manifest.run_id:sub(1,16)..string.format("%016x",7)
                end
                local seed=sequence.run(deps,codec_module,paired,fixture,runtime)
                seed.source_process_id=pid
                write_report("seed-observation.json",seed)
                assert(seed.phase=="outbox_seed_receipt_discarded")
            end)
            local seed=deps.decode_json(read(directory.."/seed-observation.json",12288))
            assert(seed.phase=="outbox_seed_receipt_discarded" and seed.run_id==fixture.run_id
                and seed.source_process_id==child and child~=parent
                and seed.outbox_final_pending==3 and seed.outbox_pruned==0)
            runtime.expected_seed_pending=true
            report.seed_process_id,report.source_process_id=child,parent
            report.distinct_seed_and_replay_processes=true
        end
        local checks=sequence.run(deps,codec_module,paired,fixture,runtime)
        for key,value in pairs(checks) do report[key]=value end
        report.lua_version,report.jit_version,report.jit_arch=_VERSION,jit.version,jit.arch
        report.koreader_version,report.json_version=baseline,json.version
        assert(type(https._VERSION)=="string" and #https._VERSION<=64)
        report.luasec_version=https._VERSION
        report.native_source_sha256={}
        for key,path in pairs(native_files) do
            local value=deps.sha256(read(path,2097152))
            assert(not native or value==before[key])
            report.native_source_sha256[key]=value
        end
    end)
    if not ok then report.phase,report.error_code="failed","paired_sequence_driver_failed" end
    write_report("device-observation.json",report)
    return report.phase=="paired_receipts_checked"
end
local ok,complete=pcall(execute)
os.exit(ok and complete and 0 or 1)
