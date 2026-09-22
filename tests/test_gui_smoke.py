import tempfile
import unittest
from pathlib import Path

try:
    import tkinter as tk

    _root = tk.Tk()
    _root.destroy()
    TK_OK = True
except Exception:
    TK_OK = False

if TK_OK:
    from dlss5_enhance import gui
    from dlss5_enhance.gui import App


@unittest.skipUnless(TK_OK, "tkinter/display unavailable")
class GuiSmokeTests(unittest.TestCase):
    def _app(self, tmp: str):
        base = Path(tmp)
        (base / "config.yaml").write_text(
            "presets:\n"
            "  un:\n    label: Premier\n    upscaling_mode: 1x\n"
            "  deux:\n    label: Second\n    upscaling_mode: 2x\n"
            "processing:\n  output: sorties\n"
            "workflow:\n  path: mon_workflow.json\n",
            encoding="utf-8",
        )
        root = gui.make_root()
        root.withdraw()
        return (
            root,
            App(root, config_path=base / "config.yaml", state_path=base / "settings.json"),
            base,
        )

    def test_presets_become_radio_buttons(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, _ = self._app(tmp)
            try:
                root.update()
                buttons = app.preset_row.winfo_children()
                self.assertEqual(len(buttons), len(app.config.presets))
                labels = sorted(button.cget("text") for button in buttons)
                self.assertIn("Premier", labels)
                self.assertIn("Second", labels)
                self.assertEqual(app.preset_var.get(), next(iter(app.config.presets)))
                self.assertIn("Upscaling", app.mode_var.get())
            finally:
                root.destroy()

    def test_paths_are_prefilled_from_the_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, base = self._app(tmp)
            try:
                root.update()
                self.assertEqual(app.output_var.get(), str(base / "sorties"))
                self.assertEqual(app.workflow_var.get(), str(base / "mon_workflow.json"))
            finally:
                root.destroy()

    def test_mode_label_follows_the_selection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, _ = self._app(tmp)
            try:
                root.update()
                app.preset_var.set("deux")
                app._refresh_mode()
                self.assertIn("2x (Performance)", app.mode_var.get())
            finally:
                root.destroy()

    def test_log_and_progress_messages_are_consumed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, _ = self._app(tmp)
            try:
                root.update()
                app.sink.line("bonjour")
                app.sink.progress("[1/1] clip.mp4  42.0%  42/100 frames  ETA 00:10")
                app.messages.put(("log", ("ERROR", "quelque chose")))
                app._drain()
                root.update()
                text = app.log.get("1.0", "end")
                self.assertIn("bonjour", text)
                self.assertIn("quelque chose", text)
                self.assertIn("42.0%", app.status_var.get())
                self.assertAlmostEqual(app.bar["value"], 42.0)
                app.messages.put(("done", 0))
                app._drain()
                root.update()
                self.assertEqual(app.status_var.get(), "Done.")
                self.assertEqual(str(app.run_button["state"]), "normal")
            finally:
                root.destroy()

    def test_first_run_opens_the_setup_screen(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, _ = self._app(tmp)
            try:
                root.update()
                app._maybe_first_run_setup()
                root.update()
                self.assertIsNotNone(app.setup_dialog)
                app.setup_dialog.close()
                root.update()
                self.assertIsNone(app.setup_dialog)
            finally:
                root.destroy()

    def test_dropping_files_fills_the_queue(self):
        class Drop:
            def __init__(self, data: str) -> None:
                self.data = data

        with tempfile.TemporaryDirectory() as tmp:
            root, app, base = self._app(tmp)
            try:
                root.update()
                video = base / "a.mp4"
                video.write_bytes(b"x")
                app._on_drop(Drop("{" + str(video) + "}"))  # tkdnd braces paths
                app._on_drop(Drop("{" + str(video) + "}"))  # duplicate
                app._on_drop(Drop(str(video)))  # a plain path is accepted too
                missing = base / "gone.mp4"
                app._on_drop(Drop("{" + str(missing) + "}"))
                root.update()
                self.assertEqual(app.queue, [video])
                self.assertEqual(app.queue_list.size(), 1)
                self.assertIn("gone.mp4", app.log.get("1.0", "end"))
                self.assertIn("1 item", app.queue_var.get())
            finally:
                root.destroy()

    def test_queue_survives_a_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, base = self._app(tmp)
            video = base / "a.mp4"
            video.write_bytes(b"x")
            app._add_paths([video])
            app.container_var.set("MP4")
            app.codec_var.set("H.264")
            app._save_state()
            root.destroy()

            root2 = gui.make_root()
            root2.withdraw()
            again = App(
                root2, config_path=base / "config.yaml", state_path=base / "settings.json"
            )
            try:
                root2.update()
                self.assertEqual(again.queue, [video])
                self.assertEqual(again.container_var.get(), "MP4")
                self.assertEqual(again.codec_var.get(), "H.264")
            finally:
                root2.destroy()

    def test_a_preset_moves_the_sliders_and_marks_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, _ = self._app(tmp)
            try:
                root.update()
                app.preset_var.set("deux")
                app._apply_preset()
                root.update()
                self.assertEqual(app.setting_vars["upscaling_mode"].get(), "2x (Performance)")
                self.assertIn("upscaling_mode", app.setting_dirty)
                self.assertEqual(
                    app._settings_overrides(), {"upscaling_mode": "2x (Performance)"}
                )
            finally:
                root.destroy()

    def test_reading_the_workflow_again_clears_the_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, base = self._app(tmp)
            try:
                root.update()
                workflow = base / "mon_workflow.json"
                workflow.write_text(
                    '{"1": {"class_type": "DLSS5Settings", "inputs": '
                    '{"upscaling_mode": "3x (Ultra Performance)", '
                    '"local_structure_strength": 1.8}}, '
                    '"2": {"class_type": "DLSS5EnhanceVideoFile", "inputs": {}}}',
                    encoding="utf-8",
                )
                app.workflow_var.set(str(workflow))
                app._reload_settings_from_workflow()
                root.update()
                self.assertEqual(
                    app.setting_vars["upscaling_mode"].get(), "3x (Ultra Performance)"
                )
                self.assertAlmostEqual(
                    float(app.setting_vars["local_structure_strength"].get()), 1.8
                )
                self.assertEqual(app.setting_dirty, set())
                self.assertEqual(app._settings_overrides(), {})
            finally:
                root.destroy()

    def test_moving_one_slider_only_overrides_that_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, _ = self._app(tmp)
            try:
                root.update()
                app.setting_vars["local_structure_strength"].set(2.0)
                app._mark_dirty("local_structure_strength")
                root.update()
                self.assertEqual(
                    app._settings_overrides(), {"local_structure_strength": 2.0}
                )
            finally:
                root.destroy()


if __name__ == "__main__":
    unittest.main()
