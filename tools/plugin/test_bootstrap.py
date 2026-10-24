"""Bootstrap behavior on Lua 5.1 and LuaJIT; not PW3 installation evidence."""
from pathlib import Path
import unittest

from lupa.lua51 import LuaRuntime
from lupa.luajit21 import LuaRuntime as LuaJITRuntime


ROOT = Path(__file__).resolve().parents[2]


class BootstrapTest(unittest.TestCase):
    lua_type = LuaRuntime

    def setUp(self):
        self.lua = self.lua_type(unpack_returned_tuples=True)
        self.environment = self.lua.execute('''
            local e = {registered = {}, shown = {}, closed = {}, ticks = {}, settings_calls = 0}
            local container = {}
            function container:extend(t)
                t.__index = t
                setmetatable(t, {__index = self})
                return t
            end
            function container:new(t)
                local instance = setmetatable(t or {}, self)
                instance:init()
                return instance
            end
            local modules = {
                ["gettext"] = function(text) return text end,
                ["datastorage"] = {getSettingsDir = function()
                    e.settings_calls = e.settings_calls + 1
                    return "/synthetic/custom/settings"
                end},
                ["ui/widget/container/widgetcontainer"] = container,
                ["ui/widget/infomessage"] = {new = function(_, t) return t end},
                ["ui/widget/buttondialog"] = {new = function(_, t)
                    -- Native v2026.07.1 renders title; an arbitrary text field is ignored.
                    assert(t.title and not t.text, "unsupported ButtonDialog text")
                    return t
                end},
                ["ui/widget/confirmbox"] = {new = function(_, t) return t end},
                ["ui/uimanager"] = {show = function(_, message)
                    table.insert(e.shown, message)
                end, close = function(_, message) table.insert(e.closed, message) end,
                    nextTick = function(_, callback) table.insert(e.ticks, callback) end},
            }
            require = function(name)
                assert(modules[name], "unexpected dependency: " .. name)
                return modules[name]
            end
            e.set_statistics = function(module) modules["quartzo/statistics"] = module end
            e.set_delivery = function(module)
                modules["quartzo/outbox"] = module
                modules["quartzo/koreader_deps"] = {load = function() return {} end}
                modules["quartzo/codec"] = {new = function() return {} end}
            end
            e.ui = {menu = {registerToMainMenu = function(_, plugin)
                table.insert(e.registered, plugin)
            end}}
            e.set_clock=function()
                os={date=function() return "2026-10-24T00:00:00.000Z" end}
            end
            -- Any accidental filesystem, process, DB or network access must fail.
            io, os, package, dofile, loadfile = nil, nil, nil, nil, nil
            return e
        ''')
        self.plugin = self.lua.execute((ROOT / "quartzo.koplugin/main.lua").read_text())
        self.meta = self.lua.execute((ROOT / "quartzo.koplugin/_meta.lua").read_text())
        # KOReader v2026.07.1 PluginLoader applies metadata after main.lua loads.
        for name, value in self.meta.items():
            self.plugin[name] = value

    def instance(self):
        return self.plugin.new(self.plugin, self.lua.table(ui=self.environment.ui))

    def test_load_is_inert_and_available_without_a_document(self):
        self.assertFalse(self.plugin.is_doc_only)
        self.assertEqual(self.environment.settings_calls, 0)
        self.assertEqual(len(self.environment.registered), 0)
        self.assertEqual(len(self.environment.shown), 0)

    def test_init_registers_and_reserves_only_own_canonical_settings_paths(self):
        instance = self.instance()
        self.assertEqual(len(self.environment.registered), 1)
        self.assertEqual(self.environment.settings_calls, 1)
        self.assertEqual(instance.config_path, "/synthetic/custom/settings/quartzo.lua")
        self.assertEqual(instance.state_path, "/synthetic/custom/settings/quartzo_sync_state.sqlite3")
        self.assertEqual(len(self.environment.shown), 0)

    def test_menu_diagnostics_use_metadata_version_without_private_data(self):
        instance = self.instance()
        items = self.lua.table()
        instance.addToMainMenu(instance, items)
        self.assertEqual(items.quartzo.sorting_hint, "more_tools")
        self.assertEqual(items.quartzo.text, "Quartzo")
        self.assertEqual(len(self.environment.shown), 0)
        self.assertEqual(len(items.quartzo.sub_item_table), 4)
        items.quartzo.sub_item_table[1].callback()
        self.assertEqual(len(self.environment.shown), 1)
        text = self.environment.shown[1].text
        self.assertIn("Quartzo " + self.meta.version, text)
        self.assertIn("Statistics access: read-only, on request", text)
        self.assertIn("Synchronization: inactive", text)
        self.assertNotIn("synthetic", text)
        self.assertEqual(self.environment.settings_calls, 1)

    def delivery_owner(self, missing=False, source_state="matches_enrollment"):
        self.delivery_calls = []
        self.delivery_preview = self.lua.table(device_id="qrd_fixture", source_epoch="epoch_fixture",
                                                pending=2, review=1, selection_key="reviewed_content", canonical_ack=False)
        self.delivery_error = None
        self.delivery_open_error = None
        self.delivery_status_error = None
        self.source_reconfirmation = False
        self.empty_generation = False
        self.collection_stages = [dict(pending=2, review=1, complete=True)]
        self.source_review = self.lua.table()
        leaf = "quartzo_sync_recovery_" + "41" * 16 + ".sqlite3"

        def opened(root, runtime):
            self.delivery_calls.append(("open", root))
            if self.delivery_open_error:
                return None, self.delivery_open_error
            return (None, "outbox_missing") if missing else queue

        def backup():
            self.delivery_calls.append(("backup",))
            return self.lua.table(backup_leaf=leaf, pending=2, review=1)

        def restore(root, selected, runtime, expected):
            self.delivery_calls.append(("restore", root, selected, dict(expected.items())))
            return (None, self.delivery_error) if self.delivery_error else queue

        def review_source(root, source, runtime):
            self.delivery_calls.append(("review_source", root, source))
            return self.lua.table(review=self.source_review, has_history=True, canonical_ack=False)

        def enroll(root, reviewed, runtime):
            self.delivery_calls.append(("enroll", root, reviewed))
            return (None, self.delivery_error) if self.delivery_error else queue

        def review_change(source):
            self.delivery_calls.append(("review_source_change", source))
            return self.lua.table(review=self.source_review) if self.source_reconfirmation else (None, self.delivery_error)

        def renew(reviewed):
            self.delivery_calls.append(("renew_source", reviewed))
            return (None, self.delivery_error) if self.delivery_error else queue

        def review_collection(source, observed, limit, mode=None):
            self.delivery_calls.append(("review_collection", source, observed, limit))
            return self.lua.table(**{"pass": self.source_review, "scanned_count": 2, "event_count": 2, "review_count": 0})

        def stage_collection(reviewed):
            self.delivery_calls.append(("stage_collection", reviewed))
            if self.delivery_error:
                return None, self.delivery_error
            return self.lua.table_from(self.collection_stages.pop(0))

        def next_collection(reviewed, observed):
            self.delivery_calls.append(("next_collection", reviewed))
            return self.lua.table(**{"pass": self.source_review})

        def review_generation(source):
            self.delivery_calls.append(("review_new_generation", source))
            return self.lua.table(review=self.source_review) if self.empty_generation else (None, self.delivery_error)

        def begin_generation(reviewed):
            self.delivery_calls.append(("begin_new_generation", reviewed))
            return self.lua.table(queue=queue)

        def resolve(reviewed):
            self.delivery_calls.append(("resolve_rejections", reviewed))
            return self.lua.table(retained=1, unresolved=0)

        def upgrade(reviewed):
            self.delivery_calls.append(("upgrade_queue", reviewed))
            return self.lua.table(queue=queue)

        queue = self.lua.table(status=lambda: (None,self.delivery_status_error) if self.delivery_status_error
                              else self.lua.table(pending=2, review=1, unresolved_review=1,
                              collection_supported=source_state=="matches_enrollment"), backup=backup,
            review_source_change=review_change, renew_source=renew,
            review_new_generation=review_generation, begin_new_generation=begin_generation,
            review_collection=review_collection, stage_collection=stage_collection, next_collection=next_collection,
            review_rejections=lambda limit: self.lua.table(review=self.source_review, count=1, remaining=0),
            resolve_rejections=resolve,
            review_upgrade=lambda source: self.lua.table(review=self.source_review), upgrade_queue=upgrade,
            check_source=lambda source: (None, self.delivery_error) if self.delivery_error
                         else self.lua.table(source_state=source_state))
        owner = self.lua.table(open=opened,
            list_backups=lambda root, runtime: self.lua.table(backups=self.lua.table_from([
                self.lua.table(leaf=leaf)]), unsupported=0),
            inspect_backup=lambda root, selected, runtime: self.delivery_preview, restore=restore,
            review_source=review_source, enroll=enroll)
        self.environment.set_delivery(owner)
        return leaf

    def test_delivery_dependency_failure_is_safe_and_does_not_initialize_state(self):
        instance = self.instance()
        instance.showDeliveryState(instance)
        self.assertIn("needs review", self.environment.shown[1].text)
        self.assertNotIn("unexpected dependency", self.environment.shown[1].text)
        self.assertNotIn("synthetic", self.environment.shown[1].text)

    def test_missing_queue_keeps_backup_disabled_without_creating_or_scanning(self):
        self.delivery_owner(missing=True)
        instance = self.instance()
        instance.showDeliveryState(instance)
        dialog = self.environment.shown[1]
        self.assertIn("No reading queue found", dialog.title)
        self.assertIn("Synchronization: inactive", dialog.title)
        self.assertFalse(dialog.buttons[1][1].enabled)
        self.assertEqual(self.delivery_calls, [("open", "/synthetic/custom/settings")])

    def test_backup_is_confirmed_deferred_visible_and_not_duplicated_while_busy(self):
        self.delivery_owner()
        instance = self.instance()
        instance.showDeliveryState(instance)
        self.environment.shown[1].buttons[1][1].callback()
        confirmation = self.environment.shown[2]
        self.assertIn("queued events", confirmation.text)
        self.assertEqual(len(self.environment.ticks), 0)
        confirmation.ok_callback()
        self.assertTrue(instance.delivery_busy)
        self.assertIn("Creating recovery copy", self.environment.shown[3].text)
        self.assertNotIn(("backup",), self.delivery_calls)
        confirmation.ok_callback()
        self.assertEqual(len(self.environment.ticks), 1)
        self.environment.ticks[1]()
        self.assertFalse(instance.delivery_busy)
        self.assertEqual(self.delivery_calls.count(("backup",)), 1)
        self.assertIn("Recovery copy saved", self.environment.shown[4].text)

    def test_unreadable_primary_keeps_recovery_review_accessible_without_replacing_state(self):
        for error in ("invalid_outbox_state", "unsupported_outbox_file"):
            with self.subTest(error=error):
                self.setUp()
                self.delivery_owner()
                self.delivery_open_error=error
                instance=self.instance()
                instance.showDeliveryState(instance)
                dialog=self.environment.shown[1]
                self.assertIsNotNone(dialog.title)
                self.assertIn("needs review",dialog.title)
                self.assertIn("Synchronization: inactive",dialog.title)
                self.assertFalse(dialog.buttons[1][1].enabled)
                self.assertFalse(dialog.buttons[3][1].enabled)
                dialog.buttons[2][1].callback()
                self.environment.shown[2].buttons[1][1].callback()
                confirmation=self.environment.shown[3]
                self.assertIn("current queue is absent",confirmation.text)
                self.assertEqual([c[0] for c in self.delivery_calls],["open"])
                self.delivery_error="outbox_exists"
                confirmation.ok_callback()
                self.environment.ticks[1]()
                self.assertEqual(self.delivery_calls[-1][0],"restore")
                self.assertIn("current reading queue was preserved",self.environment.shown[5].text)
                self.assertFalse(instance.delivery_busy)

    def test_failed_status_keeps_recovery_review_available_and_mutations_disabled(self):
        self.delivery_owner()
        self.delivery_status_error="invalid_outbox_state"
        instance=self.instance()
        instance.showDeliveryState(instance)
        dialog=self.environment.shown[1]
        self.assertIsNotNone(dialog.title)
        self.assertIn("needs review",dialog.title)
        self.assertFalse(dialog.buttons[1][1].enabled)
        self.assertFalse(dialog.buttons[3][1].enabled)
        self.assertFalse(dialog.buttons[4][1].enabled)
        self.assertFalse(dialog.buttons[5][1].enabled)
        self.assertFalse(dialog.buttons[6][1].enabled)
        dialog.buttons[2][1].callback()
        self.assertEqual(self.environment.shown[2].title.split("\n")[0],"Recovery copies")
        self.assertEqual([c[0] for c in self.delivery_calls],["open"])

    def test_restore_passes_the_reviewed_identity_counts_and_keeps_failure_visible(self):
        leaf = self.delivery_owner(missing=True)
        instance = self.instance()
        instance.showRecoveryCopies(instance)
        self.environment.shown[1].buttons[1][1].callback()
        confirmation = self.environment.shown[2]
        self.assertIn("current queue is absent", confirmation.text)
        self.assertIn("Source setup still requires review", confirmation.text)
        self.delivery_preview.source_epoch = "changed_after_review"
        self.delivery_preview.selection_key = "changed_content_after_review"
        self.delivery_error = "outbox_backup_changed"
        confirmation.ok_callback()
        self.environment.ticks[1]()
        call = self.delivery_calls[-1]
        self.assertEqual(call[:3], ("restore", "/synthetic/custom/settings", leaf))
        self.assertEqual(call[3], dict(device_id="qrd_fixture", source_epoch="epoch_fixture",
                                     pending=2, review=1, selection_key="reviewed_content", canonical_ack=False))
        self.assertIn("recovery copy changed", self.environment.shown[4].text)
        self.assertFalse(instance.delivery_busy)

    def test_source_setup_is_manual_confirmed_deferred_and_passes_only_owner_review(self):
        self.delivery_owner(missing=True)
        instance = self.instance()
        self.assertEqual(self.delivery_calls, [])
        instance.showReadingSource(instance)
        confirmation = self.environment.shown[1]
        self.assertIn("recover its earlier queue first", confirmation.text)
        self.assertIn("Existing history will not be imported", confirmation.text)
        self.assertFalse(any(call[0] == "enroll" for call in self.delivery_calls))
        confirmation.ok_callback()
        confirmation.ok_callback()
        self.assertEqual(len(self.environment.ticks), 1)
        self.assertFalse(any(call[0] == "enroll" for call in self.delivery_calls))
        self.environment.ticks[1]()
        self.assertEqual(self.delivery_calls[-1][:2], ("enroll", "/synthetic/custom/settings"))
        self.assertTrue(self.lua.eval("function(a,b) return rawequal(a,b) end")(
            self.delivery_calls[-1][2], self.source_review))
        self.assertIn("Synchronization remains inactive", self.environment.shown[3].text)

    def test_existing_source_view_never_creates_or_replaces_identity_and_keeps_failure_visible(self):
        self.delivery_owner()
        instance = self.instance()
        instance.showReadingSource(instance)
        self.assertIn("matches the source reviewed", self.environment.shown[1].text)
        self.assertEqual(self.delivery_calls, [("open", "/synthetic/custom/settings")])
        self.delivery_error = "statistics_source_changed"
        instance.showReadingSource(instance)
        self.assertIn("identity were preserved", self.environment.shown[2].text)
        self.assertEqual([call[0] for call in self.delivery_calls], ["open", "open", "review_source_change", "review_new_generation"])

    def test_source_reconfirmation_preserves_identity_and_uses_explicit_owner_review(self):
        self.delivery_owner()
        self.delivery_error = "statistics_source_changed"
        self.source_reconfirmation = True
        instance = self.instance()
        instance.showReadingSource(instance)
        confirmation = self.environment.shown[1]
        self.assertIn("same Statistics history", confirmation.text)
        self.assertIn("reset or a different database needs separate review", confirmation.text)
        self.assertFalse(any(call[0] == "renew_source" for call in self.delivery_calls))
        self.delivery_error = None
        confirmation.ok_callback()
        self.environment.ticks[1]()
        self.assertEqual(self.delivery_calls[-2][0], "open")
        self.assertEqual(self.delivery_calls[-1][0], "renew_source")
        self.assertTrue(self.lua.eval("function(a,b) return rawequal(a,b) end")(
            self.delivery_calls[-1][1], self.source_review))
        self.assertIn("history boundary were retained", self.environment.shown[3].text)

    def test_legacy_source_state_does_not_offer_automatic_epoch_or_schema_migration(self):
        self.delivery_owner(source_state="review_required")
        instance = self.instance()
        instance.showReadingSource(instance)
        self.assertIn("existing reading identity was preserved", self.environment.shown[1].text)
        self.assertIn("needs review", self.environment.shown[1].text)
        self.assertEqual([call[0] for call in self.delivery_calls], ["open"])

    def test_manual_collection_requires_history_consent_and_processes_bounded_ticks(self):
        self.delivery_owner()
        self.environment.set_clock()
        self.collection_stages = [dict(pending=2, review=0, complete=False), dict(pending=4, review=1, complete=True)]
        instance = self.instance()
        instance.showCollection(instance)
        confirmation = self.environment.shown[1]
        self.assertIn("includes reading history", confirmation.text)
        self.assertIn("No data is sent", confirmation.text)
        self.assertFalse(any(call[0] == "stage_collection" for call in self.delivery_calls))
        confirmation.ok_callback()
        confirmation.ok_callback()
        self.assertEqual(len(self.environment.ticks), 1)
        self.environment.ticks[1]()
        self.assertTrue(instance.delivery_busy)
        self.environment.ticks[2]()
        self.assertFalse(instance.delivery_busy)
        self.assertEqual([call[0] for call in self.delivery_calls].count("stage_collection"), 2)
        self.assertIn("Queued events: 4", self.environment.shown[3].text)
        self.assertIn("Synchronization: inactive", self.environment.shown[3].text)

    def test_collection_capacity_failure_is_visible_and_ends_busy_state_without_success(self):
        self.delivery_owner()
        self.environment.set_clock()
        instance = self.instance()
        instance.showCollection(instance)
        self.delivery_error = "outbox_capacity"
        self.environment.shown[1].ok_callback()
        self.environment.ticks[1]()
        self.assertFalse(instance.delivery_busy)
        self.assertIn("queue is full", self.environment.shown[3].text)
        self.assertFalse(any(message.text and "selection queued" in message.text
                             for message in self.environment.shown.values()))

    def test_collection_stops_at_finite_work_budget(self):
        self.delivery_owner()
        self.environment.set_clock()
        self.collection_stages = [dict(pending=100, review=0, complete=False) for _ in range(10)]
        instance = self.instance()
        instance.showCollection(instance)
        self.environment.shown[1].ok_callback()
        for index in range(1, 11):
            self.environment.ticks[index]()
        self.assertFalse(instance.delivery_busy)
        self.assertEqual(len(self.environment.ticks), 10)
        self.assertIn("work limit", self.environment.shown[3].text)

    def test_source_and_collection_actions_require_closed_book_before_any_owner_access(self):
        self.delivery_owner()
        self.environment.ui.document = self.lua.table()
        instance = self.instance()
        instance.showCollection(instance)
        instance.showReadingSource(instance)
        self.assertEqual(self.delivery_calls, [])
        self.assertIn("Close the book", self.environment.shown[1].text)

    def test_invalid_entry_resolution_requires_explicit_exclusion_and_keeps_audit_message(self):
        self.delivery_owner()
        instance = self.instance()
        instance.showRejectionReview(instance)
        confirmation = self.environment.shown[1]
        self.assertIn("Keep these entries for audit", confirmation.text)
        self.assertIn("does not confirm delivery", confirmation.text)
        self.assertFalse(any(call[0] == "resolve_rejections" for call in self.delivery_calls))
        confirmation.ok_callback()
        self.environment.ticks[1]()
        self.assertEqual(self.delivery_calls[-1][0], "resolve_rejections")
        self.assertIn("No reading time was added", self.environment.shown[3].text)

    def test_empty_new_generation_is_explicit_and_preserves_old_recovery(self):
        self.delivery_owner()
        self.delivery_error = "statistics_source_changed"
        self.empty_generation = True
        instance = self.instance()
        instance.showReadingSource(instance)
        confirmation = self.environment.shown[1]
        self.assertIn("history is empty", confirmation.text)
        self.assertIn("recovery copy", confirmation.text)
        self.assertFalse(any(call[0] == "begin_new_generation" for call in self.delivery_calls))
        self.delivery_error = None
        confirmation.ok_callback()
        self.environment.ticks[1]()
        self.assertEqual(self.delivery_calls[-1][0], "begin_new_generation")
        self.assertIn("device identity", self.environment.shown[3].text)

    def test_queue_upgrade_requires_explicit_recovery_and_identity_preservation_consent(self):
        self.delivery_owner()
        instance = self.instance()
        instance.showQueueUpgrade(instance)
        confirmation = self.environment.shown[1]
        self.assertIn("recovery copy will be saved first", confirmation.text)
        self.assertIn("reading identities will be retained", confirmation.text)
        self.assertFalse(any(call[0] == "upgrade_queue" for call in self.delivery_calls))
        confirmation.ok_callback()
        self.environment.ticks[1]()
        self.assertEqual(self.delivery_calls[-1][0], "upgrade_queue")
        self.assertIn("recovery copy were retained", self.environment.shown[3].text)

    def test_missing_statistics_sdk_is_a_sanitized_manual_diagnostic(self):
        instance = self.instance()
        instance.showStatistics(instance)
        self.assertEqual(self.environment.shown[1].text,
                         "Reading Statistics could not be read. No data was collected.")

    def test_manual_statistics_action_displays_capped_counts_and_safe_date_failure(self):
        calls = []
        result = self.lua.table(schema_version=20221111, book_count=2,
                                event_count=100000, event_count_limited=True,
                                first_started_at=100, last_started_at=200)

        def probe(path):
            calls.append(path)
            return result

        self.environment.set_statistics(self.lua.table(probe=probe))
        instance = self.instance()
        items = self.lua.table()
        instance.addToMainMenu(instance, items)
        self.assertEqual(calls, [])
        items.quartzo.sub_item_table[2].callback()
        self.assertEqual(calls, ["/synthetic/custom/settings/statistics.sqlite3"])
        text = self.environment.shown[1].text
        self.assertIn("Raw events: 100000+", text)
        self.assertIn("Book rows: 2", text)
        self.assertIn("Earliest event: Unavailable", text)
        self.assertNotIn("synthetic", text)


class BootstrapLuaJITTest(BootstrapTest):
    lua_type = LuaJITRuntime


if __name__ == "__main__":
    unittest.main()
