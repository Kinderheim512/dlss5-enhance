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
        root = tk.Tk()
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


if __name__ == "__main__":
    unittest.main()
