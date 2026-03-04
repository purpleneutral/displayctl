"""Visual display layout canvas with drag-and-drop positioning."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("PangoCairo", "1.0")

from gi.repository import Gdk, GLib, Gtk, Pango, PangoCairo

from .model import DisplayConfig, Monitor
from .snap import Snap

# Colors
BG_COLOR = (0.12, 0.12, 0.14)
MONITOR_COLOR = (0.75, 0.78, 0.82, 0.85)
SELECTED_COLOR = (0.30, 0.50, 0.90, 0.85)
DISABLED_COLOR = (0.45, 0.45, 0.48, 0.5)
BORDER_COLOR = (0.25, 0.25, 0.28)
SELECTED_BORDER = (0.20, 0.40, 0.80)
TEXT_COLOR = (0.10, 0.10, 0.12)
SUBTEXT_COLOR = (0.35, 0.35, 0.40)

SNAP_TOLERANCE_PX = 15  # pixels on screen (canvas space)


class DisplayCanvas(Gtk.DrawingArea):
    """Canvas rendering monitor rectangles with drag-to-reposition."""

    def __init__(self):
        super().__init__()
        self._config: DisplayConfig | None = None
        self._selected: str | None = None
        self._scale: float = 1.0
        self._offset_x: float = 0.0
        self._offset_y: float = 0.0

        # Drag state
        self._drag_mon_origin_x: int = 0
        self._drag_mon_origin_y: int = 0
        self._snap: Snap | None = None

        # Callbacks
        self._on_select: list = []
        self._on_position_changed: list = []

        self.set_draw_func(self._draw)
        self.set_hexpand(True)
        self.set_vexpand(True)

        # Click to select
        click = Gtk.GestureClick()
        click.connect("pressed", self._on_click)
        self.add_controller(click)

        # Drag to reposition
        drag = Gtk.GestureDrag()
        drag.connect("drag-begin", self._on_drag_begin)
        drag.connect("drag-update", self._on_drag_update)
        drag.connect("drag-end", self._on_drag_end)
        self.add_controller(drag)

    # --- Public API ---

    def set_config(self, config: DisplayConfig):
        self._config = config
        if config.enabled and not self._selected:
            self._selected = config.enabled[0].name
        self.queue_draw()

    def set_selected(self, name: str | None):
        self._selected = name
        self.queue_draw()

    @property
    def selected(self) -> str | None:
        return self._selected

    def on_select(self, callback):
        self._on_select.append(callback)

    def on_position_changed(self, callback):
        self._on_position_changed.append(callback)

    # --- Drawing ---

    def _compute_layout(self, canvas_w: float, canvas_h: float):
        """Compute scale and offset to center monitors in canvas."""
        if not self._config or not self._config.enabled:
            self._scale = 1.0
            self._offset_x = canvas_w / 2
            self._offset_y = canvas_h / 2
            return

        monitors = self._config.enabled
        min_x = min(m.display_x for m in monitors)
        min_y = min(m.display_y for m in monitors)
        max_x = max(m.display_x + m.display_width for m in monitors)
        max_y = max(m.display_y + m.display_height for m in monitors)

        bbox_w = max_x - min_x
        bbox_h = max_y - min_y

        if bbox_w == 0 or bbox_h == 0:
            self._scale = 1.0
            self._offset_x = canvas_w / 2
            self._offset_y = canvas_h / 2
            return

        padding = 0.85
        sx = (canvas_w * padding) / bbox_w
        sy = (canvas_h * padding) / bbox_h
        self._scale = min(sx, sy)

        # Center the bounding box
        self._offset_x = (canvas_w - bbox_w * self._scale) / 2 - min_x * self._scale
        self._offset_y = (canvas_h - bbox_h * self._scale) / 2 - min_y * self._scale

    def _mon_to_screen(self, mon: Monitor) -> tuple[float, float, float, float]:
        """Convert monitor coords to screen (canvas) pixel coords."""
        x = mon.display_x * self._scale + self._offset_x
        y = mon.display_y * self._scale + self._offset_y
        w = mon.display_width * self._scale
        h = mon.display_height * self._scale
        return x, y, w, h

    def _draw(self, area, cr, width, height):
        # Background
        cr.set_source_rgb(*BG_COLOR)
        cr.rectangle(0, 0, width, height)
        cr.fill()

        if not self._config:
            return

        self._compute_layout(width, height)

        # Draw disabled monitors faintly
        for mon in self._config.connected:
            if mon.enabled:
                continue
            x, y, w, h = self._mon_to_screen(mon)
            cr.set_source_rgba(*DISABLED_COLOR)
            cr.rectangle(x, y, w, h)
            cr.fill()
            self._draw_label(cr, mon, x, y, w, h, dim=True)

        # Draw enabled monitors
        for mon in self._config.enabled:
            x, y, w, h = self._mon_to_screen(mon)
            is_sel = mon.name == self._selected

            # Fill
            if is_sel:
                cr.set_source_rgba(*SELECTED_COLOR)
            else:
                cr.set_source_rgba(*MONITOR_COLOR)
            self._rounded_rect(cr, x, y, w, h, 6)
            cr.fill()

            # Border
            if is_sel:
                cr.set_source_rgb(*SELECTED_BORDER)
                cr.set_line_width(3.0)
            else:
                cr.set_source_rgb(*BORDER_COLOR)
                cr.set_line_width(1.5)
            self._rounded_rect(cr, x, y, w, h, 6)
            cr.stroke()

            self._draw_label(cr, mon, x, y, w, h)

    def _rounded_rect(self, cr, x, y, w, h, r):
        """Draw a rounded rectangle path."""
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -1.5708, 0)
        cr.arc(x + w - r, y + h - r, r, 0, 1.5708)
        cr.arc(x + r, y + h - r, r, 1.5708, 3.14159)
        cr.arc(x + r, y + r, r, 3.14159, 4.71239)
        cr.close_path()

    def _draw_label(self, cr, mon: Monitor, x, y, w, h, dim=False):
        cr.save()

        # Name
        layout = PangoCairo.create_layout(cr)
        font_size = max(9, min(14, int(w / 12)))
        desc = Pango.FontDescription(f"sans bold {font_size}")
        layout.set_font_description(desc)

        name = mon.name
        if mon.primary:
            name += " [P]"
        layout.set_text(name, -1)
        _ink, logical = layout.get_pixel_extents()

        tx = x + (w - logical.width) / 2
        ty = y + (h - logical.height) / 2 - 8

        if dim:
            cr.set_source_rgba(*SUBTEXT_COLOR, 0.5)
        else:
            cr.set_source_rgb(*TEXT_COLOR)
        cr.move_to(tx, ty)
        PangoCairo.show_layout(cr, layout)

        # Resolution + refresh
        layout2 = PangoCairo.create_layout(cr)
        sub_size = max(7, font_size - 2)
        desc2 = Pango.FontDescription(f"sans {sub_size}")
        layout2.set_font_description(desc2)
        cur = mon.current_mode
        res_text = f"{mon.width}x{mon.height}"
        if cur:
            res_text += f" @ {cur.refresh_rate:.0f}Hz"
        layout2.set_text(res_text, -1)
        _ink2, logical2 = layout2.get_pixel_extents()

        if dim:
            cr.set_source_rgba(*SUBTEXT_COLOR, 0.4)
        else:
            cr.set_source_rgb(*SUBTEXT_COLOR)
        cr.move_to(x + (w - logical2.width) / 2, ty + logical.height + 4)
        PangoCairo.show_layout(cr, layout2)

        cr.restore()

    # --- Hit testing ---

    def _hit_test(self, sx: float, sy: float) -> Monitor | None:
        if not self._config:
            return None
        # Test enabled monitors in reverse (topmost first)
        for mon in reversed(self._config.enabled):
            x, y, w, h = self._mon_to_screen(mon)
            if x <= sx <= x + w and y <= sy <= y + h:
                return mon
        return None

    def _get_monitor(self, name: str) -> Monitor | None:
        if not self._config:
            return None
        return next((m for m in self._config.monitors if m.name == name), None)

    # --- Input handling ---

    def _on_click(self, gesture, n_press, x, y):
        mon = self._hit_test(x, y)
        if mon:
            self._selected = mon.name
            self.queue_draw()
            for cb in self._on_select:
                cb(mon.name)

    def _on_drag_begin(self, gesture, start_x, start_y):
        mon = self._hit_test(start_x, start_y)
        if not mon:
            gesture.set_state(Gtk.EventSequenceState.DENIED)
            return

        self._selected = mon.name
        self._drag_mon_origin_x = mon.x
        self._drag_mon_origin_y = mon.y

        # Build snap targets from other enabled monitors
        others = [
            (m.x, m.y, m.display_width, m.display_height)
            for m in self._config.enabled
            if m.name != mon.name
        ]
        # Convert screen-pixel tolerance to monitor-space
        tol = int(SNAP_TOLERANCE_PX / self._scale) if self._scale > 0 else 50
        self._snap = Snap(
            (mon.display_width, mon.display_height),
            tolerance=tol,
            rects=others,
        )
        for cb in self._on_select:
            cb(mon.name)

    def _on_drag_update(self, gesture, offset_x, offset_y):
        if not self._selected:
            return
        mon = self._get_monitor(self._selected)
        if not mon:
            return

        dx = offset_x / self._scale
        dy = offset_y / self._scale
        new_x = int(self._drag_mon_origin_x + dx)
        new_y = int(self._drag_mon_origin_y + dy)

        if self._snap:
            new_x, new_y = self._snap.suggest(new_x, new_y)

        mon.drag_x = new_x
        mon.drag_y = new_y
        self.queue_draw()

    def _on_drag_end(self, gesture, offset_x, offset_y):
        if not self._selected:
            return
        mon = self._get_monitor(self._selected)
        if not mon:
            return

        if mon.drag_x is not None:
            mon.x = mon.drag_x
            mon.y = mon.drag_y
            mon.drag_x = None
            mon.drag_y = None

        # Normalize so bounding box starts at (0,0) — prevents dead zones
        if self._config:
            self._config.normalize_positions()

        self._snap = None
        self.queue_draw()

        for cb in self._on_position_changed:
            cb(mon.name, mon.x, mon.y)
