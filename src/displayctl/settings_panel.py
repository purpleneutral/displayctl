"""Right-side settings panel for per-monitor configuration."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .model import DisplayConfig, Monitor

ROTATION_MAP = ["normal", "left", "inverted", "right"]
ROTATION_LABELS = ["Normal", "Left (90)", "Inverted (180)", "Right (270)"]
REFLECTION_MAP = ["normal", "x", "y", "xy"]
REFLECTION_LABELS = ["None", "X axis", "Y axis", "Both axes"]
SCALE_VALUES = ["0.5", "0.75", "1.0", "1.25", "1.5", "2.0", "3.0"]


class SettingsPanel(Gtk.Box):
    """Per-monitor settings panel."""

    def __init__(self):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.set_margin_top(12)
        self.set_margin_bottom(12)
        self.set_margin_start(12)
        self.set_margin_end(12)
        self.set_size_request(260, -1)

        self._config: DisplayConfig | None = None
        self._selected: str | None = None
        self._updating = False
        self._on_change: list = []

        # Monitor selector
        self._monitor_model = Gtk.StringList()
        self._monitor_dd = Gtk.DropDown(model=self._monitor_model)
        self._monitor_dd.connect("notify::selected", self._on_monitor_selected)
        self._add_row("Monitor", self._monitor_dd)

        # Separator
        self.append(Gtk.Separator())

        # Enabled
        self._enabled_sw = Gtk.Switch(halign=Gtk.Align.START)
        self._enabled_sw.connect("notify::active", self._on_enabled)
        self._add_row("Enabled", self._enabled_sw)

        # Primary
        self._primary_sw = Gtk.Switch(halign=Gtk.Align.START)
        self._primary_sw.connect("notify::active", self._on_primary)
        self._add_row("Primary", self._primary_sw)

        self.append(Gtk.Separator())

        # Resolution
        self._res_model = Gtk.StringList()
        self._res_dd = Gtk.DropDown(model=self._res_model)
        self._res_dd.connect("notify::selected", self._on_resolution)
        self._add_row("Resolution", self._res_dd)

        # Refresh rate
        self._rate_model = Gtk.StringList()
        self._rate_dd = Gtk.DropDown(model=self._rate_model)
        self._rate_dd.connect("notify::selected", self._on_refresh)
        self._add_row("Refresh Rate", self._rate_dd)

        self.append(Gtk.Separator())

        # Rotation
        self._rot_dd = Gtk.DropDown.new_from_strings(ROTATION_LABELS)
        self._rot_dd.connect("notify::selected", self._on_rotation)
        self._add_row("Rotation", self._rot_dd)

        # Reflection
        self._ref_dd = Gtk.DropDown.new_from_strings(REFLECTION_LABELS)
        self._ref_dd.connect("notify::selected", self._on_reflection)
        self._add_row("Reflection", self._ref_dd)

        # Scale
        self._scale_dd = Gtk.DropDown.new_from_strings(SCALE_VALUES)
        self._scale_dd.connect("notify::selected", self._on_scale)
        self._add_row("Scale", self._scale_dd)

        # Brightness
        self._bright_adj = Gtk.Adjustment(
            value=1.0, lower=0.1, upper=1.0, step_increment=0.05, page_increment=0.1
        )
        self._bright_scale = Gtk.Scale(
            orientation=Gtk.Orientation.HORIZONTAL,
            adjustment=self._bright_adj,
            digits=2,
            draw_value=True,
        )
        self._bright_adj.connect("value-changed", self._on_brightness)
        self._bright_row = self._add_row("Brightness", self._bright_scale)

        self.append(Gtk.Separator())

        # Position
        pos_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        pos_box.append(Gtk.Label(label="X:"))
        self._pos_x = Gtk.SpinButton(
            adjustment=Gtk.Adjustment(value=0, lower=-32768, upper=32768, step_increment=1, page_increment=10),
        )
        self._pos_x.connect("value-changed", self._on_pos_x)
        pos_box.append(self._pos_x)
        pos_box.append(Gtk.Label(label="Y:"))
        self._pos_y = Gtk.SpinButton(
            adjustment=Gtk.Adjustment(value=0, lower=-32768, upper=32768, step_increment=1, page_increment=10),
        )
        self._pos_y.connect("value-changed", self._on_pos_y)
        pos_box.append(self._pos_y)
        self._add_row("Position", pos_box)

    def _add_row(self, label_text: str, widget: Gtk.Widget) -> Gtk.Box:
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        label = Gtk.Label(label=label_text, halign=Gtk.Align.START)
        label.add_css_class("dim-label")
        row.append(label)
        row.append(widget)
        self.append(row)
        return row

    # --- Public API ---

    def set_config(self, config: DisplayConfig):
        self._config = config
        self._refresh_monitor_list()

    def set_selected(self, name: str):
        """Select a monitor by name and populate widgets."""
        self._selected = name
        self._sync_monitor_dropdown()
        self._populate()

    def set_brightness_visible(self, visible: bool):
        self._bright_row.set_visible(visible)

    def update_position(self, name: str, x: int, y: int):
        """Update position fields from canvas drag."""
        if self._selected == name:
            self._updating = True
            self._pos_x.set_value(x)
            self._pos_y.set_value(y)
            self._updating = False

    def on_change(self, callback):
        self._on_change.append(callback)

    # --- Internal ---

    def _get_mon(self) -> Monitor | None:
        if not self._config or not self._selected:
            return None
        return next((m for m in self._config.monitors if m.name == self._selected), None)

    def _refresh_monitor_list(self):
        self._updating = True
        # Clear and repopulate
        while self._monitor_model.get_n_items() > 0:
            self._monitor_model.remove(0)
        if self._config:
            for mon in self._config.connected:
                label = mon.name
                if mon.primary:
                    label += " [P]"
                if not mon.enabled:
                    label += " (off)"
                self._monitor_model.append(label)
        self._sync_monitor_dropdown()
        self._updating = False

    def _sync_monitor_dropdown(self):
        """Set the monitor dropdown to match self._selected."""
        if not self._config or not self._selected:
            return
        self._updating = True
        for i, mon in enumerate(self._config.connected):
            if mon.name == self._selected:
                self._monitor_dd.set_selected(i)
                break
        self._updating = False

    def _populate(self):
        """Populate all widgets from the selected monitor."""
        mon = self._get_mon()
        if not mon:
            return

        self._updating = True
        try:
            self._enabled_sw.set_active(mon.enabled)
            self._primary_sw.set_active(mon.primary)

            # Resolution dropdown
            while self._res_model.get_n_items() > 0:
                self._res_model.remove(0)
            resolutions = mon.resolutions()
            current_res_idx = 0
            for i, r in enumerate(resolutions):
                self._res_model.append(r)
                if mon.current_mode and mon.current_mode.resolution == r:
                    current_res_idx = i
            self._res_dd.set_selected(current_res_idx)

            # Refresh rate dropdown
            self._populate_rates(mon, resolutions[current_res_idx] if resolutions else None)

            # Rotation
            rot_idx = ROTATION_MAP.index(mon.rotation) if mon.rotation in ROTATION_MAP else 0
            self._rot_dd.set_selected(rot_idx)

            # Reflection
            ref_idx = REFLECTION_MAP.index(mon.reflection) if mon.reflection in REFLECTION_MAP else 0
            self._ref_dd.set_selected(ref_idx)

            # Scale
            scale_str = str(mon.scale)
            if scale_str in SCALE_VALUES:
                self._scale_dd.set_selected(SCALE_VALUES.index(scale_str))
            else:
                self._scale_dd.set_selected(2)  # default 1.0

            # Brightness
            self._bright_adj.set_value(mon.brightness)

            # Position
            self._pos_x.set_value(mon.x)
            self._pos_y.set_value(mon.y)

            # Enable/disable controls based on enabled state
            sensitive = mon.enabled
            for w in [self._res_dd, self._rate_dd, self._rot_dd, self._ref_dd,
                       self._scale_dd, self._bright_scale, self._pos_x, self._pos_y]:
                w.set_sensitive(sensitive)
        finally:
            self._updating = False

    def _populate_rates(self, mon: Monitor, resolution: str | None):
        """Populate refresh rate dropdown for a given resolution."""
        while self._rate_model.get_n_items() > 0:
            self._rate_model.remove(0)
        if not resolution:
            return
        modes = mon.refresh_rates_for(resolution)
        current_idx = 0
        for i, mode in enumerate(modes):
            self._rate_model.append(mode.label)
            if mode.current:
                current_idx = i
        if modes:
            self._rate_dd.set_selected(current_idx)

    def _notify(self):
        if not self._updating:
            for cb in self._on_change:
                cb()

    # --- Signal handlers ---

    def _on_monitor_selected(self, dd, _pspec):
        if self._updating or not self._config:
            return
        idx = dd.get_selected()
        connected = self._config.connected
        if 0 <= idx < len(connected):
            self._selected = connected[idx].name
            self._populate()
            self._notify()

    def _on_enabled(self, sw, _pspec):
        if self._updating:
            return
        mon = self._get_mon()
        if mon:
            mon.enabled = sw.get_active()
            self._populate()  # refresh controls sensitivity
            self._refresh_monitor_list()
            self._notify()

    def _on_primary(self, sw, _pspec):
        if self._updating:
            return
        mon = self._get_mon()
        if not mon or not self._config:
            return
        if sw.get_active():
            # Unset primary on all others
            for m in self._config.monitors:
                m.primary = False
            mon.primary = True
        else:
            mon.primary = False
        self._refresh_monitor_list()
        self._notify()

    def _on_resolution(self, dd, _pspec):
        if self._updating:
            return
        mon = self._get_mon()
        if not mon:
            return
        idx = dd.get_selected()
        resolutions = mon.resolutions()
        if 0 <= idx < len(resolutions):
            res = resolutions[idx]
            # Clear current on all modes, then pick best for new resolution
            for m in mon.modes:
                m.current = False
            modes = mon.refresh_rates_for(res)
            # Prefer preferred mode, otherwise first
            pick = next((m for m in modes if m.preferred), modes[0] if modes else None)
            if pick:
                pick.current = True
                mon.width = pick.width
                mon.height = pick.height
            # Refresh rate dropdown
            self._updating = True
            self._populate_rates(mon, res)
            self._updating = False
            self._notify()

    def _on_refresh(self, dd, _pspec):
        if self._updating:
            return
        mon = self._get_mon()
        if not mon:
            return
        idx = dd.get_selected()
        res_idx = self._res_dd.get_selected()
        resolutions = mon.resolutions()
        if 0 <= res_idx < len(resolutions):
            modes = mon.refresh_rates_for(resolutions[res_idx])
            if 0 <= idx < len(modes):
                for m in mon.modes:
                    m.current = False
                modes[idx].current = True
                self._notify()

    def _on_rotation(self, dd, _pspec):
        if self._updating:
            return
        mon = self._get_mon()
        if mon:
            mon.rotation = ROTATION_MAP[dd.get_selected()]
            self._notify()

    def _on_reflection(self, dd, _pspec):
        if self._updating:
            return
        mon = self._get_mon()
        if mon:
            mon.reflection = REFLECTION_MAP[dd.get_selected()]
            self._notify()

    def _on_scale(self, dd, _pspec):
        if self._updating:
            return
        mon = self._get_mon()
        if mon:
            mon.scale = float(SCALE_VALUES[dd.get_selected()])
            self._notify()

    def _on_brightness(self, adj):
        if self._updating:
            return
        mon = self._get_mon()
        if mon:
            mon.brightness = adj.get_value()
            self._notify()

    def _on_pos_x(self, spin):
        if self._updating:
            return
        mon = self._get_mon()
        if mon:
            mon.x = int(spin.get_value())
            self._notify()

    def _on_pos_y(self, spin):
        if self._updating:
            return
        mon = self._get_mon()
        if mon:
            mon.y = int(spin.get_value())
            self._notify()
