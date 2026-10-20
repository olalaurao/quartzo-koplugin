-- Disposable KUAL TLS diagnostic only, launched from the KOReader directory.
local directory = "/mnt/us/extensions/quartzo-wire-tls-probe"
local function read(path, limit)
    local file = assert(io.open(path,"rb"))
    local value = file:read(limit+1)
    file:close()
    assert(value and #value <= limit)
    return value
end
local function hex(value, length)
    return type(value) == "string" and #value == length and not value:find("[^a-f0-9]")
end
local files = {"codec.lua","koreader_deps.lua","exchange.lua","sequence.lua","client.lua",
    "kindle.lua","run.sh","menu.json","config.xml","private-session.json",
    "server.pem","untrusted.pem","synthetic-fixture.json"}
local function execute()
    require("setupkoenv")
    local json = require("dkjson")
    local report = {probe_revision="canonical-wire-sequence-v1",phase="failed",source_data="synthetic",
        canonical_ack=false,canonical_persistence_proven=false,physical_execution_attested=false,
        statistics_accessed=false,source_cursor_changed=false,wifi_changed=false}
    local ok = pcall(function()
        local deps = dofile(directory .. "/koreader_deps.lua").load(require)
        assert(deps)
        local manifest_bytes = read(directory .. "/bundle-manifest.json",8192)
        local manifest = deps.decode_json(manifest_bytes)
        assert(manifest.probe_revision == "canonical-wire-sequence-v1" and hex(manifest.run_id,32)
            and manifest.koreader_baseline == "v2026.07.1" and hex(manifest.source_commit,40))
        local allowed = {}
        for _, name in ipairs(files) do allowed[name] = true end
        for name in pairs(manifest.files) do assert(allowed[name]) end
        for _, name in ipairs(files) do
            assert(hex(manifest.files[name],64)
                and deps.sha256(read(directory .. "/" .. name,65536)) == manifest.files[name])
        end
        report.run_id, report.source_commit = manifest.run_id, manifest.source_commit
        report.manifest_digest = deps.sha256(manifest_bytes)
        local config = deps.decode_json(read(directory .. "/private-session.json",2048))
        local fixture = deps.decode_json(read(directory .. "/synthetic-fixture.json",16384))
        local expected = {endpoint=true,token=true,run_id=true,not_before_epoch=true,expires_at_epoch=true}
        for key in pairs(config) do assert(expected[key]) end
        for key in pairs(expected) do assert(config[key] ~= nil) end
        assert(config.run_id == manifest.run_id and fixture.run_id == manifest.run_id)
        for _, key in ipairs({"not_before_epoch","expires_at_epoch"}) do
            assert(type(config[key]) == "number" and config[key] % 1 == 0
                and config[key] > 0 and config[key] < 253402300000)
        end
        local socket, https = require("socket"), require("ssl.https")
        local function seconds()
            local value = socket.gettime()
            assert(type(value) == "number" and value >= config.not_before_epoch
                and config.expires_at_epoch-value > 30 and config.expires_at_epoch-value <= 1800)
            return math.floor(value)
        end
        local function utc(value) return os.date("!%Y-%m-%dT%H:%M:%S",value) .. ".000Z" end
        local baseline = read("git-rev",64):gsub("%s+$","")
        assert(baseline == "v2026.07.1")
        local carrier = dofile(directory .. "/client.lua").wire_transport({
            endpoint=config.endpoint,binding_id=fixture.binding.binding_id,
            ca_file=directory .. "/server.pem",bad_ca_file=directory .. "/untrusted.pem",
        },https,require("ltn12"))
        local counter = 0
        local checks = dofile(directory .. "/sequence.lua").run(deps,dofile(directory .. "/codec.lua"),
            dofile(directory .. "/exchange.lua"),fixture,{
                token=config.token,transport=carrier,now=function() return utc(seconds()) end,
                window=function() local now=seconds(); return utc(now),utc(now+30) end,
                nonce=function() counter=counter+1; assert(counter<=10)
                    return "qrtr_" .. config.run_id:sub(1,16) .. string.format("%016x",counter) end,
                pause=function(value) assert(value==1); socket.sleep(1); seconds(); return true end,
            })
        for key, value in pairs(checks) do report[key] = value end
        report.lua_version, report.jit_version, report.jit_arch = _VERSION,jit.version,jit.arch
        report.koreader_version, report.json_version = baseline,json.version
        assert(type(https._VERSION) == "string" and #https._VERSION<=64)
        report.luasec_version = https._VERSION
        report.native_source_sha256 = {
            dkjson=deps.sha256(read("common/dkjson.lua",1048576)),
            sha2=deps.sha256(read("ffi/sha2.lua",1048576))}
    end)
    if not ok then report.phase,report.error_code = "failed","wire_sequence_driver_failed" end
    local encoded = assert(json.encode(report))
    assert(#encoded<=12288)
    local target = directory .. "/device-observation.json"
    local file = assert(io.open(target .. ".tmp","wb"))
    assert(file:write(encoded))
    assert(file:close())
    assert(os.rename(target .. ".tmp",target))
    return report.phase == "wire_claims_checked"
end
-- Single-use launcher discards arbitrary stdout/stderr and bounds this process.
local ok, complete = pcall(execute)
os.exit(ok and complete and 0 or 1)
