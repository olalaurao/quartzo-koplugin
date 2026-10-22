local DataStorage = require("datastorage")
local InfoMessage = require("ui/widget/infomessage")
local UIManager = require("ui/uimanager")
local WidgetContainer = require("ui/widget/container/widgetcontainer")
local _ = require("gettext")

local Quartzo = WidgetContainer:extend{
    name = "quartzo",
    is_doc_only = false,
}

function Quartzo:init()
    -- Locate paths without opening files. Our config/state remain untouched.
    local settings_dir = DataStorage:getSettingsDir()
    self.config_path = settings_dir .. "/quartzo.lua"
    self.state_path = settings_dir .. "/quartzo_sync_state.lua"
    self.statistics_path = settings_dir .. "/statistics.sqlite3"
    self.ui.menu:registerToMainMenu(self)
end

function Quartzo:showDiagnostics()
    UIManager:show(InfoMessage:new{
        text = _("Quartzo") .. " " .. self.version .. "\n\n"
            .. _("Plugin loaded.") .. "\n"
            .. _("Statistics access: read-only, on request") .. "\n"
            .. _("Synchronization: inactive"),
    })
end

function Quartzo:showStatistics()
    local ok, result, code = pcall(function()
        return require("quartzo/statistics").probe(self.statistics_path)
    end)
    local text
    if not ok or not result then
        if code == "unsupported_statistics_schema" then
            text = _("Unsupported Reading Statistics schema. No data was collected.")
        elseif code == "statistics_busy" then
            text = _("Reading Statistics is busy. Try again later.")
        else
            text = _("Reading Statistics could not be read. No data was collected.")
        end
    else
        local function count(value, limited)
            return tostring(value) .. (limited and "+" or "")
        end
        local function date(value)
            if not value then return _("None") end
            local formatted, text = pcall(function()
                return os.date("!%Y-%m-%d %H:%M:%S UTC", value)
            end)
            return formatted and text or _("Unavailable")
        end
        text = _("Reading Statistics (read-only)") .. "\n\n"
            .. _("Schema:") .. " " .. tostring(result.schema_version) .. "\n"
            .. _("Book rows:") .. " " .. count(result.book_count, result.book_count_limited) .. "\n"
            .. _("Raw events:") .. " " .. count(result.event_count, result.event_count_limited) .. "\n"
            .. _("Earliest event:") .. " " .. date(result.first_started_at) .. "\n"
            .. _("Latest event:") .. " " .. date(result.last_started_at)
    end
    UIManager:show(InfoMessage:new{ text = text })
end

function Quartzo:addToMainMenu(menu_items)
    menu_items.quartzo = {
        text = _("Quartzo"),
        sorting_hint = "more_tools",
        sub_item_table = {
            { text = _("Diagnostics"), callback = function() self:showDiagnostics() end },
            { text = _("Reading Statistics"), callback = function() self:showStatistics() end },
        },
    }
end

return Quartzo
