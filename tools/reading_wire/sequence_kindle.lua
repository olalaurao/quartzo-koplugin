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
local files={"codec.lua","koreader_deps.lua","exchange.lua","sequence.lua","client.lua",
    "kindle.lua","run.sh","menu.json","config.xml","private-pairing.json","server.pem","synthetic-fixture.json"}
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
        local allowed={}
        for _,name in ipairs(files) do allowed[name]=true end
        for name in pairs(manifest.files) do assert(allowed[name]) end
        for _,name in ipairs(files) do
            assert(hex(manifest.files[name],64)
                and deps.sha256(read(directory.."/"..name,65536))==manifest.files[name])
        end
        report.run_id,report.source_commit=manifest.run_id,manifest.source_commit
        report.manifest_digest=deps.sha256(manifest_bytes)
        local fixture=deps.decode_json(read(directory.."/synthetic-fixture.json",16384))
        assert(fixture.run_id==manifest.run_id)
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
        local checks=dofile(directory.."/sequence.lua").run(deps,dofile(directory.."/codec.lua"),
            dofile(directory.."/exchange.lua"),fixture,{
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
            })
        for key,value in pairs(checks) do report[key]=value end
        report.lua_version,report.jit_version,report.jit_arch=_VERSION,jit.version,jit.arch
        report.koreader_version,report.json_version=baseline,json.version
        assert(type(https._VERSION)=="string" and #https._VERSION<=64)
        report.luasec_version=https._VERSION
        report.native_source_sha256={dkjson=deps.sha256(read("common/dkjson.lua",1048576)),
            sha2=deps.sha256(read("ffi/sha2.lua",1048576))}
    end)
    if not ok then report.phase,report.error_code="failed","paired_sequence_driver_failed" end
    local encoded=assert(json.encode(report))
    assert(#encoded<=12288)
    local target=directory.."/device-observation.json"
    local file=assert(io.open(target..".tmp","wb"))
    assert(file:write(encoded));assert(file:close());assert(os.rename(target..".tmp",target))
    return report.phase=="paired_receipts_checked"
end
local ok,complete=pcall(execute)
os.exit(ok and complete and 0 or 1)
