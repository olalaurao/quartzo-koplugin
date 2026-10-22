-- Single-use offline KUAL entry, from the KOReader working directory.
local directory="/mnt/us/extensions/quartzo-outbox-probe"
local files={"outbox.lua","paired_exchange.lua","codec.lua","koreader_deps.lua","probe.lua",
    "kindle.lua","run.sh","menu.json","config.xml"}
local native={dkjson="common/dkjson.lua",sha2="ffi/sha2.lua",sqlite_wrapper="common/lua-ljsqlite3/init.lua",
    posix="ffi/posix_h.lua",sqlite="libs/libsqlite3.so.0",filesystem="libs/libkoreader-lfs.so",luajit="luajit"}
local function read(path,limit)
    local file=assert(io.open(path,"rb"))
    local bytes=file:read(limit+1)
    assert(file:close() and bytes and #bytes<=limit)
    return bytes
end
local function hex(value,length)
    return type(value)=="string" and #value==length and not value:find("[^a-f0-9]")
end
local function execute()
    local started=os.clock()
    require("setupkoenv")
    local json=require("dkjson")
    local report={probe_version=1,phase="failed",error_code="outbox_probe_exception"}
    local ok=pcall(function()
        local deps=assert(dofile(directory.."/koreader_deps.lua").load(require))
        local function decode(bytes)
            local value,position,failure=json.decode(bytes)
            assert(not failure and position==#bytes+1 and type(value)=="table")
            return value
        end
        local session=decode(read(directory.."/public-session.json",1024))
        local manifest_bytes=read(directory.."/bundle-manifest.json",8192)
        assert(session.probe_version==1 and hex(session.run_id,32)
            and hex(session.manifest_digest,64) and session.manifest_digest==deps.sha256(manifest_bytes))
        local manifest=decode(manifest_bytes)
        assert(manifest.probe_version==1 and manifest.run_id==session.run_id
            and manifest.koreader_baseline=="v2026.07.1" and hex(manifest.source_commit,40))
        local allowed={}
        for _,name in ipairs(files) do allowed[name]=true end
        for name in pairs(manifest.files) do assert(allowed[name]) end
        for _,name in ipairs(files) do
            assert(hex(manifest.files[name],64)
                and deps.sha256(read(directory.."/"..name,65536))==manifest.files[name])
        end
        assert(read("git-rev",64):gsub("%s+$","")=="v2026.07.1" and jit.arch=="arm")
        local hashes={}
        for key,path in pairs(native) do hashes[key]=deps.sha256(read(path,2097152)) end
        -- The same owner, without registration or a receipt issuer.
        package.loaded["quartzo/paired_exchange"]=dofile(directory.."/paired_exchange.lua")
        report=dofile(directory.."/probe.lua").run(directory.."/state",session.run_id,
            dofile(directory.."/outbox.lua"),dofile(directory.."/codec.lua").new(deps),
            require("lua-ljsqlite3/init"),require("libs/libkoreader-lfs"))
        assert(report.phase=="passed" and report.canonical_ack==false)
        for key,path in pairs(native) do assert(deps.sha256(read(path,2097152))==hashes[key]) end
        report.run_id,report.manifest_digest,report.source_commit=session.run_id,session.manifest_digest,manifest.source_commit
        report.lua_version,report.jit_version,report.jit_arch=_VERSION,jit.version,jit.arch
        report.koreader_version="v2026.07.1"
        assert(type(json.version)=="string" and #json.version<=32 and json.version:match("^dkjson %d+%.%d+$"))
        report.json_version=json.version
        report.native_source_sha256=hashes
        report.cpu_seconds=os.clock()-started
        assert(report.cpu_seconds>=0 and report.cpu_seconds<120)
    end)
    if not ok then report.phase,report.error_code="failed","outbox_probe_exception" end
    local encoded=assert(json.encode(report))
    assert(#encoded<=8192)
    local file=assert(io.open(directory.."/device-observation.json.tmp","wb"))
    assert(file:write(encoded) and file:close())
    assert(os.rename(directory.."/device-observation.json.tmp",directory.."/device-observation.json"))
    return report.phase=="passed"
end
local ok,passed=pcall(execute)
os.exit(ok and passed and 0 or 1)
