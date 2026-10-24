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
        outbox_recovery_review_required = _("Recovery copies already exist. Review them before setting up a new reading identity. Existing files were preserved."),
        statistics_source_changed = _("Reading Statistics changed since source review or setup. The reading queue and its identity were preserved. Synchronization is inactive."),
        statistics_source_unverifiable = _("The Reading Statistics source could not be checked safely. No new identity was created. Synchronization is inactive."),
        outbox_capacity = _("The offline queue is full. Queued events were kept and collection paused. Synchronization is inactive."),
        outbox_collection_changed = _("Statistics or the reading selection changed. Review the collection again. Queued events were kept."),
        outbox_source_not_settled = _("Finish queued deliveries and review invalid entries before changing the Statistics source. Existing data was preserved."),
        statistics_source_reconciliation_required = _("The replacement Statistics history needs identity reconciliation before import. Existing reading identities and recovery copies were preserved."),
    }
    UIManager:show(InfoMessage:new{
        text = messages[code] or _("The reading queue needs review. Existing files were preserved. Synchronization is inactive."),
    })
end

function Quartzo:showReadingSource()
    if self.delivery_busy then return end
    if not self:sourceActionAllowed() then return end
    self:deliveryRequest(function(owner,runtime)
        local queue,code=owner.open(self.state_root,runtime)
        if queue then
            local source
            source,code=queue.check_source(self.statistics_path)
            if not source and code=="statistics_source_changed" then
                local reviewed,reason=self:reviewSourceChange(queue)
                if reviewed then return true end
                if reason=="statistics_source_changed" or reason=="statistics_source_unverifiable" then
                    return self:reviewNewGeneration(queue)
                end
                return nil,reason
            end
            if not source then return nil,code end
            UIManager:show(InfoMessage:new{ text=source.source_state=="matches_enrollment"
                and _("Reading Statistics matches the source reviewed during setup. Historical import and synchronization are inactive.")
                or _("The existing reading identity was preserved. Source setup needs review before collection can be enabled. Synchronization is inactive.") })
            return true
        end
        if code~="outbox_missing" then return nil,code end
        local preview
        preview,code=owner.review_source(self.state_root,self.statistics_path,runtime)
        if not preview then return nil,code end
        -- Keep only the owner's opaque, one-use review. The confirmation cannot
        -- manufacture a generation from display counts, dates or a boolean.
        local review=preview.review
        UIManager:show(ConfirmBox:new{
            text=_("Set up a new reading identity for this Reading Statistics source? If Quartzo was used before, recover its earlier queue first. Existing history will not be imported. Historical import and synchronization remain inactive."),
            ok_text=_("Set up source"),
            ok_callback=function()
                self:deliveryChange(_("Setting up reading source…"),function(current,current_runtime)
                    local enrolled,reason=current.enroll(self.state_root,review,current_runtime)
                    if not enrolled then return nil,reason end
                    UIManager:show(InfoMessage:new{ text=_("Reading source set up. Existing history was not imported. Synchronization remains inactive.") })
                    return true
                end)
            end,
        })
        return true
    end)
end

function Quartzo:sourceActionAllowed()
    if not self.ui.document then return true end
    UIManager:show(InfoMessage:new{ text=_("Close the book and return to the file browser before collecting reading or changing its source.") })
    return false
end

function Quartzo:reviewNewGeneration(queue)
    local preview,code=queue.review_new_generation(self.statistics_path)
    if not preview then return nil,code end
    local token=preview.review
    UIManager:show(ConfirmBox:new{
        text=_("The current Statistics history is empty and previous queued work is settled. Start a new source generation, keeping this device identity? A recovery copy of the previous state will be saved first. No old history is imported. Synchronization remains inactive."),
        ok_text=_("Start new generation"),
        ok_callback=function()
            self:deliveryChange(_("Saving source recovery…"),function(owner,runtime)
                local current,reason=owner.open(self.state_root,runtime)
                if not current then return nil,reason end
                local changed
                changed,reason=current.begin_new_generation(token)
                if not changed then return nil,reason end
                UIManager:show(InfoMessage:new{ text=_("New source generation saved. The device identity and previous recovery copy were retained. Synchronization remains inactive.") })
                return true
            end)
        end,
    })
    return true
end

function Quartzo:showCollection(all_history)
    if self.delivery_busy or not self:sourceActionAllowed() then return end
    self:deliveryRequest(function(owner,runtime)
        local current,code=owner.open(self.state_root,runtime)
        if not current then return nil,code end
        local preview
        preview,code=current.review_collection(self.statistics_path,os.date("!%Y-%m-%dT%H:%M:%S.000Z"),100,
            all_history and "all_history" or nil)
        if not preview then return nil,code end
        if preview.scanned_count==0 then
            UIManager:show(InfoMessage:new{ text=_("No reading events found in this source selection. Synchronization is inactive.") })
            return true
        end
        local pass=preview.pass
        UIManager:show(ConfirmBox:new{
            text=(preview.clock_reset and _("The device clock is earlier than the confirmed reading boundary. A history rescan is needed.").."\n\n" or "")
                ..((all_history or preview.clock_reset)
                and _("Rescan all reading history using this same identity? Earlier scan progress will be restarted; queued events stay intact. Previously delivered events keep their identity for retry. If Statistics was merged, replaced or reset, review its source first. Collection is bounded. No data is sent.")
                or _("Collect existing and new reading events from this Statistics source into the offline queue? This includes reading history. If Quartzo was used before, recover its original identity first. Collection is bounded and pauses safely at the queue limit. Invalid entries remain for review. No data is sent.")),
            ok_text=_("Collect reading"),
            ok_callback=function() self:runCollection(pass) end,
        })
        return true
    end)
end

function Quartzo:runCollection(pass)
    if self.delivery_busy then return end
    self.delivery_busy=true
    local progress=InfoMessage:new{ text=_("Collecting reading into the offline queue…") }
    UIManager:show(progress)
    local batches=0
    local function finish(text)
        self.delivery_busy=false
        UIManager:close(progress)
        if text then UIManager:show(InfoMessage:new{ text=text }) end
    end
    local step
    step=function()
        local again=false
        local ok=self:deliveryRequest(function(owner,runtime)
            local current,code=owner.open(self.state_root,runtime)
            if not current then return nil,code end
            local staged
            staged,code=current.stage_collection(pass)
            if not staged then return nil,code end
            batches=batches+1
            if staged.complete or batches>=10 then
                finish((staged.complete and _("Reading selection queued.") or _("Collection paused at its work limit. Queued events were kept."))
                    .."\n".._("Queued events:").." "..staged.pending.."\n".._("Synchronization: inactive"))
            else
                if staged.source_reopen_required then
                    current,code=owner.open(self.state_root,runtime)
                    if not current then return nil,code end
                end
                local preview
                local now=os.date("!%Y-%m-%dT%H:%M:%S.000Z")
                if staged.source_reopen_required then preview,code=current.review_collection(self.statistics_path,now,100)
                else preview,code=current.next_collection(pass,now) end
                if not preview then return nil,code end
                pass,again=preview.pass,true
            end
            return true
        end)
        if not ok then finish() elseif again then UIManager:nextTick(step) end
    end
    UIManager:nextTick(step)
end

function Quartzo:showRejectionReview()
    if self.delivery_busy then return end
    self:deliveryRequest(function(owner,runtime)
        local current,code=owner.open(self.state_root,runtime)
        if not current then return nil,code end
        local preview
        preview,code=current.review_rejections(100)
        if not preview then return nil,code end
        if preview.count==0 then
            UIManager:show(InfoMessage:new{ text=_("No invalid entries need review.") })
            return true
        end
        local token=preview.review
        UIManager:show(ConfirmBox:new{
            text=_("Invalid entries in this review:").." "..preview.count.."\n\n"
                .._("Keep these entries for audit and exclude them from reading time? No minutes will be added for them. Reading Statistics stays unchanged. This does not confirm delivery or advance synchronization."),
            ok_text=_("Exclude invalid entries"),
            ok_callback=function()
                self:deliveryChange(_("Saving review decision…"),function(current_owner,current_runtime)
                    local active,reason=current_owner.open(self.state_root,current_runtime)
                    if not active then return nil,reason end
                    local resolved
                    resolved,reason=active.resolve_rejections(token)
                    if not resolved then return nil,reason end
                    UIManager:show(InfoMessage:new{ text=_("Entries retained for audit. No reading time was added.") })
                    return true
                end)
            end,
        })
        return true
    end)
end

function Quartzo:showQueueUpgrade()
    if self.delivery_busy or not self:sourceActionAllowed() then return end
    self:deliveryRequest(function(owner,runtime)
        local current,code=owner.open(self.state_root,runtime)
        if not current then return nil,code end
        local preview
        preview,code=current.review_upgrade(self.statistics_path)
        if not preview then return nil,code end
        local token=preview.review
        UIManager:show(ConfirmBox:new{
            text=_("Upgrade this reading queue for reviewed collection? A recovery copy will be saved first. Existing events, review entries and reading identities will be retained. Earlier events may be retried with the same identity. Synchronization stays inactive."),
            ok_text=_("Upgrade queue"),
            ok_callback=function()
                self:deliveryChange(_("Upgrading reading queue…"),function(current_owner,current_runtime)
                    local active,reason=current_owner.open(self.state_root,current_runtime)
                    if not active then return nil,reason end
                    local upgraded
                    upgraded,reason=active.upgrade_queue(token)
                    if not upgraded then return nil,reason end
                    UIManager:show(InfoMessage:new{ text=_("Reading queue upgraded. Its identity, queued data and recovery copy were retained. Synchronization is inactive.") })
                    return true
                end)
            end,
        })
        return true
    end)
end

function Quartzo:reviewSourceChange(queue)
    local preview,code=queue.review_source_change(self.statistics_path)
    if not preview then return nil,code end
    local review=preview.review
    UIManager:show(ConfirmBox:new{
        text=_("The Statistics file changed, but the retained history checks still match. Confirm only if this is the same Statistics history, for example after restoring its copy. Keep the existing reading identity? A reset or a different database needs separate review. Existing history will not be imported and synchronization remains inactive."),
        ok_text=_("Keep existing identity"),
        ok_callback=function()
            self:deliveryChange(_("Reviewing reading source…"),function(owner,runtime)
                local current,reason=owner.open(self.state_root,runtime)
                if not current then return nil,reason end
                local renewed
                renewed,reason=current.renew_source(review)
                if not renewed then return nil,reason end
                UIManager:show(InfoMessage:new{ text=_("Source review saved. The reading identity, queued events and history boundary were retained. Synchronization remains inactive.") })
                return true
            end)
        end,
    })
    return true
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
        local unavailable=not queue and code~="outbox_missing"
        local status
        if queue then
            status,code=queue.status()
            if not status then queue,unavailable=nil,true end
        end
        -- Recovery review must remain reachable when the primary cannot open.
        -- No writable action is enabled without a successfully inspected queue;
        -- the existing restore owner still refuses an existing/damaged primary.
        local text=unavailable and _("The reading queue needs review. Existing files were preserved. Recovery copies can be reviewed below.")
            or status and (_("Queued events:").." "..status.pending.."\n"
            .._("Needs review:").." "..(status.unresolved_review or status.review))
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
                                    .._("Needs review:").." "..(saved.unresolved_review or saved.review) })
                                return true
                            end)
                        end,
                    })
                end}},
                {{text=_("Review recovery copies"),callback=function()
                    UIManager:close(dialog)
                    self:showRecoveryCopies()
                end}},
                {{text=_("Collect reading into queue"),enabled=status and status.collection_supported or false,callback=function()
                    UIManager:close(dialog)
                    self:showCollection()
                end}},
                {{text=_("Review invalid entries"),enabled=status and status.collection_supported
                    and (status.unresolved_review or 0)>0 or false,callback=function()
                    UIManager:close(dialog)
                    self:showRejectionReview()
                end}},
                {{text=_("Rescan reading history"),enabled=status and status.collection_supported or false,callback=function()
                    UIManager:close(dialog)
                    self:showCollection(true)
                end}},
                {{text=_("Upgrade reading queue"),enabled=status and status.upgrade_supported or false,callback=function()
                    UIManager:close(dialog)
                    self:showQueueUpgrade()
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
            pending=preview.pending,review=preview.review,selection_key=preview.selection_key,canonical_ack=false}
        UIManager:show(ConfirmBox:new{
            text=_("Queued events:").." "..preview.pending.."\n".._("Needs review:").." "..(preview.unresolved_review or preview.review)
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
            { text = _("Reading source"), callback = function() self:showReadingSource() end },
        },
    }
end

return Quartzo
