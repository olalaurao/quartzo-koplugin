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
            local e = {registered = {}, shown = {}, settings_calls = 0}
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
                ["ui/uimanager"] = {show = function(_, message)
                    table.insert(e.shown, message)
                end},
            }
            require = function(name)
                assert(modules[name], "unexpected dependency: " .. name)
                return modules[name]
            end
            e.set_statistics = function(module) modules["quartzo/statistics"] = module end
            e.ui = {menu = {registerToMainMenu = function(_, plugin)
                table.insert(e.registered, plugin)
            end}}
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
        self.assertEqual(instance.state_path, "/synthetic/custom/settings/quartzo_sync_state.lua")
        self.assertEqual(len(self.environment.shown), 0)

    def test_menu_diagnostics_use_metadata_version_without_private_data(self):
        instance = self.instance()
        items = self.lua.table()
        instance.addToMainMenu(instance, items)
        self.assertEqual(items.quartzo.sorting_hint, "more_tools")
        self.assertEqual(items.quartzo.text, "Quartzo")
        self.assertEqual(len(self.environment.shown), 0)
        self.assertEqual(len(items.quartzo.sub_item_table), 2)
        items.quartzo.sub_item_table[1].callback()
        self.assertEqual(len(self.environment.shown), 1)
        text = self.environment.shown[1].text
        self.assertIn("Quartzo " + self.meta.version, text)
        self.assertIn("Statistics access: read-only, on request", text)
        self.assertIn("Synchronization: inactive", text)
        self.assertNotIn("synthetic", text)
        self.assertEqual(self.environment.settings_calls, 1)

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
