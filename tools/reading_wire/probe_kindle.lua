-- Offline single-use KUAL diagnostic, executed from the KOReader directory.
local directory = "/mnt/us/extensions/quartzo-wire-probe"
local function read(path, limit)
    local file = assert(io.open(path,"rb"))
    local bytes = file:read(limit+1)
    file:close()
    assert(bytes and #bytes <= limit)
    return bytes
end
local function hex(value, size)
    return type(value) == "string" and #value == size and not value:find("[^a-f0-9]")
end
local files = {"codec.lua","koreader_deps.lua","probe.lua","kindle.lua","run.sh","menu.json",
    "config.xml","wire-vectors.json","dart-reference.json"}
local function execute()
    local started = os.clock()
    require("setupkoenv")
    local json = require("dkjson")
    local report = {probe_version=1,phase="failed",source_data="synthetic",canonical_ack=false,
        canonical_persistence_proven=false,statistics_accessed=false,source_cursor_changed=false,
        network_accessed=false,wifi_changed=false,uses_synthetic_clock=true}
    local function decode(bytes)
        local value, position, failure = json.decode(bytes)
        assert(not failure and position == #bytes+1)
        return value
    end
    local ok = pcall(function()
        local deps = dofile(directory .. "/koreader_deps.lua").load(require)
        assert(deps)
        local session = decode(read(directory .. "/public-session.json",1024))
        local manifest_bytes = read(directory .. "/bundle-manifest.json",8192)
        assert(session.probe_version == 1 and hex(session.run_id,32) and hex(session.manifest_digest,64)
            and session.manifest_digest == deps.sha256(manifest_bytes))
        local manifest = decode(manifest_bytes)
        assert(manifest.probe_version == 1 and manifest.run_id == session.run_id
            and manifest.koreader_baseline == "v2026.07.1" and hex(manifest.source_commit,40))
        local allowed = {}
        for _, name in ipairs(files) do allowed[name] = true end
        for name in pairs(manifest.files) do assert(allowed[name]) end
        for _, name in ipairs(files) do
            assert(hex(manifest.files[name],64) and deps.sha256(read(directory .. "/" .. name,65536)) == manifest.files[name])
        end
        report.run_id, report.manifest_digest, report.source_commit = session.run_id, session.manifest_digest, manifest.source_commit
        -- Strip only outer fixture-file whitespace after byte verification;
        -- embedded canonical request/response/event strings remain exact.
        local wire = deps.decode_json((read(directory .. "/wire-vectors.json",65536):gsub('[ \t\r\n]+$','')))
        local reference = deps.decode_json((read(directory .. "/dart-reference.json",65536):gsub('[ \t\r\n]+$','')))
        local checks = dofile(directory .. "/probe.lua").run(deps,dofile(directory .. "/codec.lua"),wire,reference,json.encode)
        assert(checks.phase == "passed" and checks.canonical_ack == false)
        for key, value in pairs(checks) do report[key] = value end
        report.lua_version = _VERSION
        report.jit_version, report.jit_arch = jit.version, jit.arch
        report.koreader_version = read("git-rev",64):gsub("%s+$","")
        assert(report.koreader_version == "v2026.07.1")
        assert(type(json.version) == "string" and #json.version <= 32 and json.version:match('^dkjson %d+%.%d+$'))
        report.json_version = json.version
        report.native_source_sha256 = {
            dkjson=deps.sha256(read("common/dkjson.lua",1048576)),
            sha2=deps.sha256(read("ffi/sha2.lua",1048576))}
        report.cpu_seconds = os.clock()-started
        assert(report.cpu_seconds >= 0 and report.cpu_seconds < 120)
    end)
    if not ok then report.phase, report.error_code = "failed", "wire_probe_exception" end
    local encoded = assert(json.encode(report))
    assert(#encoded <= 8192)
    local file = assert(io.open(directory .. "/device-observation.json.tmp","wb"))
    assert(file:write(encoded))
    assert(file:close())
    assert(os.rename(directory .. "/device-observation.json.tmp",directory .. "/device-observation.json"))
    return report.phase == "passed"
end
-- The single-use launcher discards native stdout/stderr; no exception excerpts.
local ok, passed = pcall(execute)
os.exit(ok and passed and 0 or 1)
