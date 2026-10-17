-- Launched only by the separate KUAL extension, from KOReader's directory.
local directory = "/mnt/us/extensions/quartzo-transport-probe"
local function boundedRead(path, limit)
    local file = assert(io.open(path, "rb"))
    local value = file:read(limit + 1)
    file:close()
    assert(value and #value <= limit, "bounded read failed")
    return value
end
local function execute()
    -- Minimal native module setup; never require production reader.lua/device/UI.
    require("setupkoenv")
    local json = require("json")
    local socket = require("socket")
    local https = require("ssl.https")
    local harness = dofile(directory .. "/device.lua")
    local report = harness.run(directory, {
        decode=json.decode, read=boundedRead, now=socket.gettime, sleep=socket.sleep,
        client=dofile(directory .. "/client.lua"), https=https, ltn12=require("ltn12")})
    report.lua_version = _VERSION
    report.luasec_version = https._VERSION
    report.koreader_version = boundedRead("git-rev", 64):gsub("%s+$", "")
    local encoded = json.encode(report)
    assert(#encoded <= 4096)
    local target = directory .. "/device-observation.json"
    local file = assert(io.open(target .. ".tmp", "wb"))
    assert(file:write(encoded))
    assert(file:close())
    assert(os.rename(target .. ".tmp", target))
    return report.phase == "passed"
end
local ok, passed = pcall(execute)
-- The launcher discards native stdout/stderr; never expose exception values.
os.exit(ok and passed and 0 or 1)
