"""Data model for display configuration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Mode:
    """A display mode (resolution + refresh rate)."""

    width: int
    height: int
    refresh_rate: float
    current: bool = False
    preferred: bool = False

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"

    @property
    def label(self) -> str:
        suffix = " *" if self.preferred else ""
        return f"{self.refresh_rate:.2f} Hz{suffix}"


@dataclass
class Monitor:
    """A physical display output."""

    name: str
    connected: bool = True
    enabled: bool = True
    primary: bool = False
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    rotation: str = "normal"          # normal, left, right, inverted
    reflection: str = "normal"        # normal, x, y, xy
    scale: float = 1.0
    brightness: float = 1.0
    modes: list[Mode] = field(default_factory=list)
    physical_width_mm: int = 0
    physical_height_mm: int = 0

    # Transient drag state (not persisted)
    drag_x: int | None = None
    drag_y: int | None = None

    @property
    def display_x(self) -> int:
        return self.drag_x if self.drag_x is not None else self.x

    @property
    def display_y(self) -> int:
        return self.drag_y if self.drag_y is not None else self.y

    @property
    def display_width(self) -> int:
        """Width accounting for rotation."""
        if self.rotation in ("left", "right"):
            return self.height
        return self.width

    @property
    def display_height(self) -> int:
        """Height accounting for rotation."""
        if self.rotation in ("left", "right"):
            return self.width
        return self.height

    @property
    def current_mode(self) -> Mode | None:
        return next((m for m in self.modes if m.current), None)

    def resolutions(self) -> list[str]:
        """Unique resolutions preserving order."""
        seen = set()
        result = []
        for m in self.modes:
            r = m.resolution
            if r not in seen:
                seen.add(r)
                result.append(r)
        return result

    def refresh_rates_for(self, resolution: str) -> list[Mode]:
        """All modes matching a given resolution."""
        return [m for m in self.modes if m.resolution == resolution]


@dataclass
class DisplayConfig:
    """Complete state of all monitors."""

    monitors: list[Monitor] = field(default_factory=list)
    screen_width: int = 0
    screen_height: int = 0
    screen_max_width: int = 16384
    screen_max_height: int = 16384

    @property
    def connected(self) -> list[Monitor]:
        return [m for m in self.monitors if m.connected]

    @property
    def enabled(self) -> list[Monitor]:
        return [m for m in self.monitors if m.connected and m.enabled]

    def normalize_positions(self) -> None:
        """Normalize monitor positions to prevent dead zones.

        1. Shift bounding box to (0, 0).
        2. Close vertical gaps: pull each monitor up to the nearest
           monitor above it (in x-range overlap), eliminating dead
           zones that break tools like flameshot.
        3. Re-shift to origin.
        """
        active = self.enabled
        if not active:
            return

        # Phase 1: shift bounding box to origin
        min_x = min(m.x for m in active)
        min_y = min(m.y for m in active)
        if min_x != 0 or min_y != 0:
            for m in active:
                m.x -= min_x
                m.y -= min_y

        # Phase 2: close vertical gaps (process top-to-bottom)
        active.sort(key=lambda m: m.y)
        for i, m in enumerate(active):
            if m.y == 0:
                continue
            # Find the max bottom-edge of monitors above this one
            # that overlap in x (strict — touching edges don't count)
            best_y = 0
            for o in active[:i]:
                if o.x >= m.x + m.display_width:
                    continue
                if o.x + o.display_width <= m.x:
                    continue
                if o.y + o.display_height <= m.y:
                    best_y = max(best_y, o.y + o.display_height)
            m.y = best_y

        # Phase 3: re-shift to origin
        min_x = min(m.x for m in active)
        min_y = min(m.y for m in active)
        if min_x != 0 or min_y != 0:
            for m in active:
                m.x -= min_x
                m.y -= min_y
