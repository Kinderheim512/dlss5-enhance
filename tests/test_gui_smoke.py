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


VIDEO_WORKFLOW = {
    "1": {
        "class_type": "DLSS5Settings",
        "inputs": {"upscaling_mode": "3x (Ultra Performance)", "local_structure_strength": 1.8},
    },
    "2": {"class_type": "DLSS5EnhanceVideoFile", "inputs": {}},
}
IMAGE_WORKFLOW = {
    "1": {"class_type": "DLSS5Settings", "inputs": {"upscaling_mode": "1x (DLAA / native)"}},
    "2": {"class_type": "LoadImage", "inputs": {"image": "x.png"}},
    "3": {"class_type": "DLSS5EnhanceImages", "inputs": {}},
    "4": {
        "class_type": "SaveImageAdvanced",
        "inputs": {"filename_prefix": "p", "format": "avif", "format.bit_depth": "auto"},
    },
}


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
        (base / "mon_workflow.json").write_text(
            __import__("json").dumps(VIDEO_WORKFLOW), encoding="utf-8"
        )
        (base / "image_workflow.json").write_text(
            __import__("json").dumps(IMAGE_WORKFLOW), encoding="utf-8"
        )
        root = gui.make_root()
        root.withdraw()
        app = App(root, config_path=base / "config.yaml", state_path=base / "settings.json")
        app.tabs["image"].workflow_var.set(str(base / "image_workflow.json"))
        app.tabs["image"].refresh_format()
        return root, app, base

    def test_three_tabs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, _ = self._app(tmp)
            try:
                root.update()
                self.assertEqual(len(app.tabs), 2)
                labels = [app.notebook.tab(i, "text") for i in range(3)]
                self.assertEqual(labels, ["Video", "Images", "DLSS5 settings"])
            finally:
                app.shutdown()
                root.destroy()

    def test_base_presets_are_radios_in_both_media_tabs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, _ = self._app(tmp)
            try:
                root.update()
                for kind in ("video", "image"):
                    buttons = app.tabs[kind].preset_radios
                    self.assertEqual(sorted(buttons), sorted(app.config.presets))
                    labels = sorted(button.cget("text") for button in buttons.values())
                    self.assertIn("Premier", labels)
                    self.assertIn("Second", labels)
                self.assertEqual(app.preset_var.get(), next(iter(app.config.presets)))
            finally:
                app.shutdown()
                root.destroy()

    def test_the_settings_tab_keeps_no_preset_list(self):
        def descendants(widget):
            found = []
            for child in widget.winfo_children():
                found.append(child)
                found.extend(descendants(child))
            return found

        with tempfile.TemporaryDirectory() as tmp:
            root, app, _ = self._app(tmp)
            try:
                root.update()
                classes = [w.winfo_class() for w in descendants(app._settings_frame)]
                self.assertNotIn("TRadiobutton", classes)
                self.assertFalse(hasattr(app, "preset_row"))
                for kind in ("video", "image"):
                    self.assertIn(
                        app.tabs[kind].preset_row,
                        descendants(app.notebook),
                    )
            finally:
                app.shutdown()
                root.destroy()

    def test_the_dropdown_is_disabled_until_a_preset_is_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, _ = self._app(tmp)
            try:
                root.update()
                for kind in ("video", "image"):
                    box = app.tabs[kind].user_box
                    self.assertEqual(list(box.cget("values")), [])
                    self.assertEqual(str(box["state"]), "disabled")
                    self.assertEqual(box.get(), "")
                self.assertEqual(str(app.delete_preset_button["state"]), "disabled")
            finally:
                app.shutdown()
                root.destroy()

    def test_the_dropdown_mirrors_the_selection_between_tabs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, _ = self._app(tmp)
            try:
                root.update()
                app.preset_var.set("deux")
                app._apply_preset()
                app._save_preset_named("maison")
                root.update()

                app.tabs["image"].user_box.set("maison")
                app._on_user_preset()
                root.update()
                self.assertEqual(app.preset_var.get(), "maison")
                self.assertEqual(app.tabs["video"].user_box.get(), "maison")
                self.assertEqual(str(app.delete_preset_button["state"]), "normal")

                app.tabs["video"].preset_radios["deux"].invoke()
                root.update()
                self.assertEqual(app.preset_var.get(), "deux")
                self.assertEqual(app.tabs["image"].user_box.get(), "")
                self.assertTrue(
                    app.tabs["image"].preset_radios["deux"].instate(["selected"])
                )
                self.assertFalse(
                    app.tabs["image"].preset_radios["un"].instate(["selected"])
                )
            finally:
                app.shutdown()
                root.destroy()

    def test_paths_are_prefilled_from_the_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, base = self._app(tmp)
            try:
                root.update()
                video = app.tabs["video"]
                self.assertEqual(video.output_var.get(), str(base / "sorties"))
                self.assertEqual(video.workflow_var.get(), str(base / "mon_workflow.json"))
                self.assertEqual(video.container_var.get(), "MKV")
                self.assertEqual(video.codec_var.get(), "HEVC")
                self.assertEqual(app.tabs["image"].image_format_value.cget("text"), "avif")
            finally:
                app.shutdown()
                root.destroy()

    def test_dropping_files_fills_the_queue(self):
        class Drop:
            def __init__(self, data: str) -> None:
                self.data = data

        with tempfile.TemporaryDirectory() as tmp:
            root, app, base = self._app(tmp)
            try:
                root.update()
                video = app.tabs["video"]
                clip = base / "a.mp4"
                clip.write_bytes(b"x")
                video._on_drop(Drop("{" + str(clip) + "}"))
                video._on_drop(Drop("{" + str(clip) + "}"))
                missing = base / "gone.mp4"
                video._on_drop(Drop("{" + str(missing) + "}"))
                root.update()
                self.assertEqual(video.queue, [clip])
                self.assertEqual(video.queue_list.size(), 1)
                self.assertIn("gone.mp4", app.log.get("1.0", "end"))
                self.assertIn("1 item", video.queue_var.get())
            finally:
                app.shutdown()
                root.destroy()

    def test_each_tab_keeps_its_own_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, base = self._app(tmp)
            try:
                root.update()
                clip = base / "a.mp4"
                clip.write_bytes(b"x")
                picture = base / "a.png"
                picture.write_bytes(b"x")
                app.tabs["video"]._add_paths([clip])
                app.tabs["image"]._add_paths([picture])
                app._save_state()
                self.assertEqual(app.settings.sources, [str(clip)])
                self.assertEqual(app.settings.image_sources, [str(picture)])
            finally:
                app.shutdown()
                root.destroy()

    def test_queue_survives_a_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, base = self._app(tmp)
            clip = base / "a.mp4"
            clip.write_bytes(b"x")
            app.tabs["video"]._add_paths([clip])
            app.tabs["video"].container_var.set("MP4")
            app._save_state()
            app.shutdown()
            root.destroy()

            root2 = gui.make_root()
            root2.withdraw()
            again = App(root2, config_path=base / "config.yaml", state_path=base / "settings.json")
            try:
                root2.update()
                self.assertEqual(again.tabs["video"].queue, [clip])
                self.assertEqual(again.tabs["video"].container_var.get(), "MP4")
            finally:
                again.shutdown()
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
                self.assertEqual(app._upscaling_readout.cget("text"), "2x (Performance)")
                self.assertIn("upscaling_mode", app.setting_dirty)
                self.assertTrue(
                    app.setting_labels["upscaling_mode"].cget("text").startswith("•")
                )
                self.assertEqual(
                    app._settings_overrides(), {"upscaling_mode": "2x (Performance)"}
                )
            finally:
                app.shutdown()
                root.destroy()

    def test_reading_the_workflow_again_clears_the_overrides(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, _ = self._app(tmp)
            try:
                root.update()
                app.notebook.select(0)  # the video tab is the one in front
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
                self.assertEqual(app._upscaling_readout.cget("text"), "3x (Ultra Performance)")
            finally:
                app.shutdown()
                root.destroy()

    def test_moving_one_slider_only_overrides_that_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, _ = self._app(tmp)
            try:
                root.update()
                app.setting_vars["local_structure_strength"].set(2.0)
                app._mark_dirty("local_structure_strength")
                root.update()
                self.assertEqual(app._settings_overrides(), {"local_structure_strength": 2.0})
            finally:
                app.shutdown()
                root.destroy()

    def test_advanced_toggle_only_touches_its_rows(self):
        from dlss5_enhance.dlss5_settings import SETTINGS

        with tempfile.TemporaryDirectory() as tmp:
            root, app, _ = self._app(tmp)
            try:
                root.update()
                app.advanced_var.set(False)
                app._toggle_advanced()
                root.update()
                hidden = {
                    name
                    for name, widgets in app.setting_rows.items()
                    if widgets and not widgets[0].winfo_manager()
                }
                self.assertEqual(
                    hidden, {setting.name for setting in SETTINGS if setting.advanced}
                )
                app.advanced_var.set(True)
                app._toggle_advanced()
                root.update()
                shown = {
                    name
                    for name, widgets in app.setting_rows.items()
                    if widgets and widgets[0].winfo_manager()
                }
                self.assertEqual(shown, {setting.name for setting in SETTINGS})
            finally:
                app.shutdown()
                root.destroy()

    def test_size_line_follows_the_upscaling(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, base = self._app(tmp)
            try:
                root.update()
                picture = base / "a.png"
                picture.write_bytes(b"x")
                app.tabs["image"]._add_paths([picture])
                app.setting_vars["upscaling_mode"].set("2x (Performance)")
                app._mark_dirty("upscaling_mode")
                root.update()
                self.assertEqual(app.upscaling_factor(), 2.0)
            finally:
                app.shutdown()
                root.destroy()

    def test_user_preset_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, _ = self._app(tmp)
            try:
                root.update()
                app.preset_var.set("deux")
                app._apply_preset()
                app.setting_vars["local_structure_strength"].set(2.0)
                app._mark_dirty("local_structure_strength")
                app.preset_var.set("deux")
                app._save_preset_named("maison")
                root.update()
                self.assertIn("maison", app.config.presets)
                self.assertEqual(app.config.presets["maison"].factor, 2.0)
                self.assertEqual(app.preset_var.get(), "maison")
                for kind in ("video", "image"):
                    box = app.tabs[kind].user_box
                    self.assertEqual(list(box.cget("values")), ["maison"])
                    self.assertEqual(box.get(), "maison")
                    self.assertEqual(str(box["state"]), "readonly")
                    self.assertNotIn("maison", app.tabs[kind].preset_radios)
                self.assertEqual(str(app.delete_preset_button["state"]), "normal")

                app._delete_preset_confirmed()
                root.update()
                self.assertNotIn("maison", app.config.presets)
                for kind in ("video", "image"):
                    box = app.tabs[kind].user_box
                    self.assertEqual(list(box.cget("values")), [])
                    self.assertEqual(str(box["state"]), "disabled")
                    self.assertEqual(box.get(), "")
                self.assertIn(app.preset_var.get(), app.tabs["video"].preset_radios)
                self.assertEqual(str(app.delete_preset_button["state"]), "disabled")
            finally:
                app.shutdown()
                root.destroy()

    def test_installation_banner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, _ = self._app(tmp)
            try:
                root.update()
                app._show_banner([object(), object()])
                root.update()
                self.assertIn("2", app.banner_var.get())
                self.assertTrue(app.banner.winfo_manager())
                app._show_banner([])
                root.update()
                self.assertFalse(app.banner.winfo_manager())
            finally:
                app.shutdown()
                root.destroy()

    def test_image_paths_come_back_absolute_after_a_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, base = self._app(tmp)
            out = base / "images-out"
            out.mkdir()
            app.tabs["image"].output_var.set(str(out))
            app.tabs["image"].workflow_var.set(str(base / "image_workflow.json"))
            app._save_state()
            app.shutdown()
            root.destroy()

            root2 = gui.make_root()
            root2.withdraw()
            again = App(root2, config_path=base / "config.yaml", state_path=base / "settings.json")
            try:
                root2.update()
                self.assertEqual(again.tabs["image"].output_var.get(), str(out))
                self.assertEqual(
                    again.tabs["image"].workflow_var.get(), str(base / "image_workflow.json")
                )
            finally:
                again.shutdown()
                root2.destroy()

    def test_a_user_preset_cannot_shadow_a_shipped_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, base = self._app(tmp)
            try:
                root.update()
                shipped = app.config.presets["un"].label
                (base / "presets.yaml").write_text(
                    "presets:\n  mien:\n    label: Premier\n    upscaling_mode: 2x\n",
                    encoding="utf-8",
                )
                app._load_config()
                root.update()
                labels = list(app.tabs["video"].user_box.cget("values"))
                self.assertEqual(len(labels), 1)
                self.assertNotEqual(labels[0], shipped)
                self.assertIn("mien", labels[0])
                self.assertIn(
                    shipped,
                    [b.cget("text") for b in app.tabs["video"].preset_radios.values()],
                )
            finally:
                app.shutdown()
                root.destroy()

    def test_the_settings_tab_names_the_preset_that_delete_would_remove(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, _ = self._app(tmp)
            try:
                root.update()
                active = app.config.presets[app.preset_var.get()]
                self.assertIn(active.label, app.preset_status_var.get())
                app.preset_var.set("deux")
                app._apply_preset()
                root.update()
                self.assertIn("Second", app.preset_status_var.get())
                app._save_preset_named("maison")
                root.update()
                self.assertIn("maison", app.preset_status_var.get())
            finally:
                app.shutdown()
                root.destroy()

    def test_the_run_uses_the_preset_picked_in_the_dropdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, _ = self._app(tmp)
            try:
                root.update()
                app.preset_var.set("deux")
                app._apply_preset()
                app._save_preset_named("maison")
                root.update()
                self.assertEqual(app._build_job("video")["preset"], "maison")
                app.tabs["video"].preset_radios["deux"].invoke()
                root.update()
                self.assertEqual(app._build_job("image")["preset"], "deux")
            finally:
                app.shutdown()
                root.destroy()

    def test_a_user_preset_is_restored_after_a_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, base = self._app(tmp)
            app.preset_var.set("deux")
            app._apply_preset()
            app._save_preset_named("maison")
            root.update()
            self.assertEqual(app.preset_var.get(), "maison")
            app.shutdown()
            root.destroy()

            root2 = gui.make_root()
            root2.withdraw()
            again = App(root2, config_path=base / "config.yaml", state_path=base / "settings.json")
            try:
                root2.update()
                self.assertEqual(again.preset_var.get(), "maison")
                for kind in ("video", "image"):
                    self.assertEqual(again.tabs[kind].user_box.get(), "maison")
                    self.assertEqual(str(again.delete_preset_button["state"]), "normal")
            finally:
                again.shutdown()
                root2.destroy()

    def test_the_job_handed_to_the_worker_holds_no_tk_object(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, app, base = self._app(tmp)
            try:
                root.update()
                clip = base / "a.mp4"
                clip.write_bytes(b"x")
                app.tabs["video"]._add_paths([clip])
                app.force_var.set(True)
                job = app._build_job("video")
                root.update()
                self.assertIs(type(job["force"]), bool)
                self.assertTrue(job["force"])
                for value in job.values():
                    self.assertNotIsInstance(value, tk.Variable)
                app.force_var.set(False)
                self.assertTrue(job["force"])
            finally:
                app.shutdown()
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
                app.shutdown()
                root.destroy()


if __name__ == "__main__":
    unittest.main()
