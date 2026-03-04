"""Main application window."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .backend import DisplayBackend
from .canvas import DisplayCanvas
from .model import DisplayConfig
from .profiles import apply_profile, list_profiles, load_profile, save_profile
from .settings_panel import SettingsPanel


class DisplayWindow(Gtk.ApplicationWindow):
    def __init__(self, app: Gtk.Application, backend: DisplayBackend):
        super().__init__(application=app, title="Display Editor")
        self.backend = backend
        self.config: DisplayConfig | None = None

        self.set_default_size(1100, 650)

        # --- Header bar ---
        header = Gtk.HeaderBar()
        self.set_titlebar(header)

        # Left: save/load
        save_btn = Gtk.Button(icon_name="document-save-symbolic")
        save_btn.set_tooltip_text("Save profile")
        save_btn.connect("clicked", self._on_save_profile)
        header.pack_start(save_btn)

        load_btn = Gtk.Button(icon_name="document-open-symbolic")
        load_btn.set_tooltip_text("Load profile")
        load_btn.connect("clicked", self._on_load_profile)
        header.pack_start(load_btn)

        # Right: apply/reset
        apply_btn = Gtk.Button(label="Apply")
        apply_btn.add_css_class("suggested-action")
        apply_btn.connect("clicked", self._on_apply)
        header.pack_end(apply_btn)

        reset_btn = Gtk.Button(label="Reset")
        reset_btn.connect("clicked", self._on_reset)
        header.pack_end(reset_btn)

        # Backend label
        backend_label = Gtk.Label(label=backend.backend_name())
        backend_label.add_css_class("dim-label")
        header.pack_start(backend_label)

        # --- Layout ---
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        paned.set_shrink_start_child(False)
        paned.set_shrink_end_child(False)

        self.canvas = DisplayCanvas()
        paned.set_start_child(self.canvas)

        self.settings = SettingsPanel()
        self.settings.set_brightness_visible(backend.supports_brightness)

        scroll = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        )
        scroll.set_child(self.settings)
        paned.set_end_child(scroll)
        paned.set_position(750)

        self.set_child(paned)

        # Wire callbacks
        self.canvas.on_select(self._on_canvas_select)
        self.canvas.on_position_changed(self._on_canvas_position)
        self.settings.on_change(self._on_settings_changed)

        # Load initial state
        self._load()

    def _load(self):
        """Query backend and populate UI."""
        try:
            self.config = self.backend.query()
        except RuntimeError as e:
            self._show_error(f"Failed to query displays: {e}")
            return

        self.canvas.set_config(self.config)
        self.settings.set_config(self.config)
        if self.config.enabled:
            sel = self.canvas.selected or self.config.enabled[0].name
            self.settings.set_selected(sel)

    def _on_canvas_select(self, name: str):
        self.settings.set_selected(name)

    def _on_canvas_position(self, name: str, x: int, y: int):
        self.settings.update_position(name, x, y)

    def _on_settings_changed(self):
        self.canvas.queue_draw()

    def _on_apply(self, btn):
        if not self.config:
            return
        try:
            self.backend.apply(self.config)
        except RuntimeError as e:
            self._show_error(f"Apply failed: {e}")
            return
        # Re-query to get actual state
        self._load()

    def _on_reset(self, btn):
        self._load()

    def _on_save_profile(self, btn):
        dialog = Gtk.AlertDialog()
        dialog.set_message("Save Profile")
        dialog.set_detail("Enter a name for this profile:")
        dialog.set_buttons(["Cancel", "Save"])
        dialog.set_default_button(1)
        dialog.set_cancel_button(0)
        dialog.choose(self, None, self._on_save_dialog_response)

    def _on_save_dialog_response(self, dialog, result):
        try:
            idx = dialog.choose_finish(result)
        except Exception:
            return
        if idx != 1:
            return
        # Use a simple input dialog - since AlertDialog doesn't have text entry,
        # show a window with an entry
        self._show_name_dialog("Save Profile", self._do_save)

    def _on_load_profile(self, btn):
        names = list_profiles()
        if not names:
            self._show_error("No saved profiles found.")
            return
        self._show_profile_picker(names)

    def _show_name_dialog(self, title: str, callback):
        """Show a dialog with a text entry."""
        win = Gtk.Window(
            title=title,
            transient_for=self,
            modal=True,
            default_width=300,
            default_height=100,
        )
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)

        entry = Gtk.Entry(placeholder_text="Profile name")
        box.append(entry)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.END)
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda _: win.close())
        save = Gtk.Button(label="Save")
        save.add_css_class("suggested-action")

        def on_save(_):
            name = entry.get_text().strip()
            if name:
                callback(name)
                win.close()

        save.connect("clicked", on_save)
        entry.connect("activate", on_save)
        btn_box.append(cancel)
        btn_box.append(save)
        box.append(btn_box)

        win.set_child(box)
        win.present()

    def _do_save(self, name: str):
        if not self.config:
            return
        try:
            path = save_profile(self.config, name)
            self._show_info(f"Profile saved: {path}")
        except Exception as e:
            self._show_error(f"Save failed: {e}")

    def _show_profile_picker(self, names: list[str]):
        """Show a dialog to pick a profile to load."""
        win = Gtk.Window(
            title="Load Profile",
            transient_for=self,
            modal=True,
            default_width=300,
            default_height=200,
        )
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(16)
        box.set_margin_bottom(16)
        box.set_margin_start(16)
        box.set_margin_end(16)

        label = Gtk.Label(label="Select a profile:", halign=Gtk.Align.START)
        box.append(label)

        listbox = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
        listbox.add_css_class("boxed-list")
        for name in names:
            row = Gtk.ListBoxRow()
            row_label = Gtk.Label(label=name, halign=Gtk.Align.START)
            row_label.set_margin_top(8)
            row_label.set_margin_bottom(8)
            row_label.set_margin_start(12)
            row.set_child(row_label)
            listbox.append(row)

        scroll = Gtk.ScrolledWindow(
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
        )
        scroll.set_child(listbox)
        scroll.set_vexpand(True)
        box.append(scroll)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, halign=Gtk.Align.END)
        cancel = Gtk.Button(label="Cancel")
        cancel.connect("clicked", lambda _: win.close())
        load = Gtk.Button(label="Load")
        load.add_css_class("suggested-action")

        def on_load(_):
            row = listbox.get_selected_row()
            if row is not None:
                idx = row.get_index()
                self._do_load(names[idx])
                win.close()

        load.connect("clicked", on_load)
        btn_box.append(cancel)
        btn_box.append(load)
        box.append(btn_box)

        win.set_child(box)
        win.present()

    def _do_load(self, name: str):
        if not self.config:
            return
        try:
            data = load_profile(name)
            apply_profile(self.config, data)
            self.canvas.queue_draw()
            sel = self.canvas.selected
            if sel:
                self.settings.set_selected(sel)
            self.settings.set_config(self.config)
        except Exception as e:
            self._show_error(f"Load failed: {e}")

    def _show_error(self, message: str):
        dialog = Gtk.AlertDialog()
        dialog.set_message("Error")
        dialog.set_detail(message)
        dialog.set_buttons(["OK"])
        dialog.show(self)

    def _show_info(self, message: str):
        dialog = Gtk.AlertDialog()
        dialog.set_message("Info")
        dialog.set_detail(message)
        dialog.set_buttons(["OK"])
        dialog.show(self)
