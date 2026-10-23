local DataStorage = require("datastorage")
local InfoMessage = require("ui/widget/infomessage")
local ButtonDialog = require("ui/widget/buttondialog")
local ConfirmBox = require("ui/widget/confirmbox")
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
    self.state_root = settings_dir
    self.config_path = settings_dir .. "/quartzo.lua"
    self.state_path = settings_dir .. "/quartzo_sync_state.sqlite3"
    self.statistics_path = settings_dir .. "/statistics.sqlite3"
    self.ui.menu:registerToMainMenu(self)
end

function Quartzo:showDeliveryError(code)
    local messages = {
        outbox_exists = _("The current reading queue was preserved. Restore is available only when it is absent."),
        outbox_backup_changed = _("The recovery copy changed. Review it again before restoring. Existing files were preserved."),
        outbox_recovery_list_limit = _("There are too many files to list recovery copies safely. Existing files were preserved."),
    }
    UIManager:show(InfoMessage:new{
        text = messages[code] or _("The reading queue needs review. Existing files were preserved. Synchronization is inactive."),
    })
end

function Quartzo:deliveryRequest(action)
    local ok,result,code=pcall(function()
        if not self.delivery_runtime then
            local deps=assert(require("quartzo/koreader_deps").load(require))
            local codec=assert(require("quartzo/codec").new(deps))
            self.delivery_owner=require("quartzo/outbox")
            self.delivery_runtime={codec=codec}
        end
        return action(self.delivery_owner,self.delivery_runtime)
    end)
    if not ok or not result then self:showDeliveryError(ok and code or nil) end
    return ok and result
end

function Quartzo:deliveryChange(label, action)
    if self.delivery_busy then return end
    self.delivery_busy=true
    local progress=InfoMessage:new{ text=label }
    UIManager:show(progress)
    UIManager:nextTick(function()
        self:deliveryRequest(action)
        self.delivery_busy=false
        UIManager:close(progress)
    end)
end

function Quartzo:showDeliveryState()
    if self.delivery_busy then return end
    self:deliveryRequest(function(owner,runtime)
        local queue,code=owner.open(self.state_root,runtime)
        if not queue and code~="outbox_missing" then return nil,code end
        local status
        if queue then
            status,code=queue.status()
            if not status then return nil,code end
        end
        local text=status and (_("Queued events:").." "..status.pending.."\n"
            .._("Needs review:").." "..status.review)
            or _("No reading queue found. Existing recovery copies can be reviewed below.")
        local dialog
        dialog=ButtonDialog:new{
            title=_("Offline reading queue").."\n\n"..text.."\n\n".._("Synchronization: inactive"),
            buttons={
                {{text=_("Create recovery copy"),enabled=queue~=nil,callback=function()
                    UIManager:close(dialog)
                    UIManager:show(ConfirmBox:new{
                        text=_("Save a recovery copy of the currently queued events and items needing review? This does not back up events queued later."),
                        ok_text=_("Create copy"),
                        ok_callback=function()
                            self:deliveryChange(_("Creating recovery copy…"),function(current,current_runtime)
                                local active,reason=current.open(self.state_root,current_runtime)
                                if not active then return nil,reason end
                                local saved
                                saved,reason=active.backup()
                                if not saved then return nil,reason end
                                UIManager:show(InfoMessage:new{ text=_("Recovery copy saved.").."\n"
                                    .._("Queued events:").." "..saved.pending.."\n"
                                    .._("Needs review:").." "..saved.review })
                                return true
                            end)
                        end,
                    })
                end}},
                {{text=_("Review recovery copies"),callback=function()
                    UIManager:close(dialog)
                    self:showRecoveryCopies()
                end}},
                {{text=_("Close"),callback=function() UIManager:close(dialog) end}},
            },
        }
        UIManager:show(dialog)
        return true
    end)
end

function Quartzo:showRecoveryCopies()
    self:deliveryRequest(function(owner,runtime)
        local listing,code=owner.list_backups(self.state_root,runtime)
        if not listing then return nil,code end
        if #listing.backups==0 then
            UIManager:show(InfoMessage:new{ text=_("No supported recovery copies found. Existing files were preserved.") })
            return true
        end
        local buttons,dialog={},nil
        for index,entry in ipairs(listing.backups) do
            local leaf=entry.leaf
            local date=_("Date unavailable")
            if entry.modified then
                local ok,value=pcall(function() return os.date("!%Y-%m-%d %H:%M UTC",entry.modified) end)
                if ok and value then date=value end
            end
            buttons[#buttons+1]={{text=_("Copy").." "..index.." · "..date,callback=function()
                UIManager:close(dialog)
                self:showRecoveryCopy(leaf)
            end}}
        end
        buttons[#buttons+1]={{text=_("Close"),callback=function() UIManager:close(dialog) end}}
        dialog=ButtonDialog:new{ title=_("Recovery copies").."\n\n"
            .._("Choose a copy to review. File dates do not verify the Statistics source."),buttons=buttons }
        UIManager:show(dialog)
        return true
    end)
end

function Quartzo:showRecoveryCopy(leaf)
    self:deliveryRequest(function(owner,runtime)
        local preview,code=owner.inspect_backup(self.state_root,leaf,runtime)
        if not preview then return nil,code end
        local expected={device_id=preview.device_id,source_epoch=preview.source_epoch,
            pending=preview.pending,review=preview.review,canonical_ack=false}
        UIManager:show(ConfirmBox:new{
            text=_("Queued events:").." "..preview.pending.."\n".._("Needs review:").." "..preview.review
                .."\n\n".._("Restore this point-in-time copy only if the current queue is absent? It retains its original identity and cannot recover later events. Source setup still requires review. Synchronization remains inactive."),
            ok_text=_("Restore copy"),
            ok_callback=function()
                self:deliveryChange(_("Restoring reading queue…"),function(current,current_runtime)
                    local restored,reason=current.restore(self.state_root,leaf,current_runtime,expected)
                    if not restored then return nil,reason end
                    UIManager:show(InfoMessage:new{ text=_("Reading queue restored. Its original identity was retained. Synchronization remains inactive.") })
                    return true
                end)
            end,
        })
        return true
    end)
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
            { text = _("Offline reading queue"), callback = function() self:showDeliveryState() end },
        },
    }
end

return Quartzo
