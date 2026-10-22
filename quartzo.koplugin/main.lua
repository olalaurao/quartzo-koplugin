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
    -- Reserve only our own paths. Bootstrap does not open or write either file.
    local settings_dir = DataStorage:getSettingsDir()
    self.config_path = settings_dir .. "/quartzo.lua"
    self.state_path = settings_dir .. "/quartzo_sync_state.lua"
    self.ui.menu:registerToMainMenu(self)
end

function Quartzo:showDiagnostics()
    UIManager:show(InfoMessage:new{
        text = _("Quartzo") .. " " .. self.version .. "\n\n"
            .. _("Plugin loaded.") .. "\n"
            .. _("Statistics access: inactive") .. "\n"
            .. _("Synchronization: inactive"),
    })
end

function Quartzo:addToMainMenu(menu_items)
    menu_items.quartzo = {
        text = _("Quartzo"),
        sorting_hint = "more_tools",
        callback = function() self:showDiagnostics() end,
    }
end

return Quartzo
