"""Display backends for X11 (xrandr) and Wayland (wlr-randr)."""

from __future__ import annotations

import abc
import json
import os
import re
import subprocess
from .model import DisplayConfig, Mode, Monitor


class DisplayBackend(abc.ABC):
    @abc.abstractmethod
    def query(self) -> DisplayConfig:
        """Parse current display state."""
        ...

    @abc.abstractmethod
    def apply(self, config: DisplayConfig) -> None:
        """Apply display configuration."""
        ...

    @abc.abstractmethod
    def backend_name(self) -> str:
        ...

    @property
    def supports_brightness(self) -> bool:
        return False


def detect_backend() -> DisplayBackend:
    """Auto-detect the appropriate backend."""
    session = os.environ.get("XDG_SESSION_TYPE", "").lower()
    if session == "wayland" or os.environ.get("WAYLAND_DISPLAY"):
        return WlrRandrBackend()
    if session == "x11" or os.environ.get("DISPLAY"):
        return XrandrBackend()
    raise RuntimeError("Cannot detect display server")


class XrandrBackend(DisplayBackend):
    """Backend using the xrandr CLI tool."""

    # Header: OutputName connected [primary] [WxH+X+Y] [(0xNN)] [rotation] (supported...) [WmmxHmm]
    _HEADER_RE = re.compile(
        r'^(\S+)\s+(connected|disconnected)\s*'
        r'(primary\s+)?'
        r'(?:(\d+)x(\d+)\+(\d+)\+(\d+)\s+)?'
        r'(?:\(0x[0-9a-f]+\)\s+)?'
        r'(normal|left|right|inverted)?\s*'
        r'\(([^)]*)\)\s*'
        r'(?:(\d+)mm\s+x\s+(\d+)mm)?'
    )

    # Mode line (verbose): "  3840x1080 (0x5a) 270.270MHz +HSync -VSync *current +preferred"
    _MODE_RE = re.compile(
        r'^\s{2}(\d+)x(\d+)\s+\(0x[0-9a-f]+\)\s+\S+\s+(.*)'
    )

    # v: line: "        v: height 1080 ... clock  60.00Hz"
    _VLINE_RE = re.compile(r'^\s+v:\s+.*clock\s+(\d+\.?\d*)Hz')

    # Screen line
    _SCREEN_RE = re.compile(
        r'^Screen\s+\d+:.*current\s+(\d+)\s+x\s+(\d+),\s+maximum\s+(\d+)\s+x\s+(\d+)'
    )

    def backend_name(self) -> str:
        return "xrandr (X11)"

    @property
    def supports_brightness(self) -> bool:
        return True

    def query(self) -> DisplayConfig:
        result = subprocess.run(
            ["xrandr", "--verbose"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(f"xrandr --verbose failed: {result.stderr}")
        return self._parse_verbose(result.stdout)

    def _parse_verbose(self, text: str) -> DisplayConfig:
        config = DisplayConfig()
        lines = text.splitlines()
        i = 0

        while i < len(lines):
            line = lines[i]

            # Screen line
            m = self._SCREEN_RE.match(line)
            if m:
                config.screen_width = int(m.group(1))
                config.screen_height = int(m.group(2))
                config.screen_max_width = int(m.group(3))
                config.screen_max_height = int(m.group(4))
                i += 1
                continue

            # Output header
            m = self._HEADER_RE.match(line)
            if m:
                monitor = Monitor(name=m.group(1))
                monitor.connected = m.group(2) == "connected"
                monitor.primary = m.group(3) is not None
                if m.group(4):
                    monitor.width = int(m.group(4))
                    monitor.height = int(m.group(5))
                    monitor.x = int(m.group(6))
                    monitor.y = int(m.group(7))
                    monitor.enabled = True
                else:
                    monitor.enabled = False if monitor.connected else False
                monitor.rotation = m.group(8) or "normal"
                # Parse reflection from supported list
                # The reflection state isn't directly in header; default to normal
                monitor.reflection = "normal"
                if m.group(10):
                    monitor.physical_width_mm = int(m.group(10))
                if m.group(11):
                    monitor.physical_height_mm = int(m.group(11))
                i += 1

                # Parse properties and modes
                while i < len(lines):
                    pline = lines[i]

                    # Tab-indented property
                    if pline.startswith('\t'):
                        bm = re.match(r'\tBrightness:\s+([\d.]+)', pline)
                        if bm:
                            monitor.brightness = float(bm.group(1))
                        i += 1
                        continue

                    # Mode header (2-space indent, not 8-space/tab)
                    mm = self._MODE_RE.match(pline)
                    if mm:
                        mw = int(mm.group(1))
                        mh = int(mm.group(2))
                        flags = mm.group(3)
                        is_current = "*current" in flags
                        is_preferred = "+preferred" in flags
                        i += 1

                        # Read h: and v: lines
                        refresh = 0.0
                        while i < len(lines) and lines[i].startswith('        '):
                            vm = self._VLINE_RE.match(lines[i])
                            if vm:
                                refresh = float(vm.group(1))
                            i += 1

                        mode = Mode(
                            width=mw, height=mh,
                            refresh_rate=refresh,
                            current=is_current,
                            preferred=is_preferred,
                        )
                        monitor.modes.append(mode)
                        continue

                    # Next output or unknown line — break
                    break

                config.monitors.append(monitor)
                continue

            i += 1

        return config

    def apply(self, config: DisplayConfig) -> None:
        cmd = ["xrandr"]
        for mon in config.monitors:
            if not mon.connected:
                continue
            cmd += ["--output", mon.name]
            if not mon.enabled:
                cmd.append("--off")
            else:
                current = mon.current_mode
                if current:
                    cmd += ["--mode", current.resolution]
                    cmd += ["--rate", f"{current.refresh_rate:.2f}"]
                cmd += ["--pos", f"{mon.x}x{mon.y}"]
                cmd += ["--rotate", mon.rotation]
                cmd += ["--reflect", mon.reflection]
                cmd += ["--scale", f"{mon.scale}x{mon.scale}"]
                cmd += ["--brightness", f"{mon.brightness:.2f}"]
                if mon.primary:
                    cmd.append("--primary")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            raise RuntimeError(f"xrandr failed: {result.stderr}")


class WlrRandrBackend(DisplayBackend):
    """Backend using wlr-randr for wlroots-based Wayland compositors."""

    def backend_name(self) -> str:
        return "wlr-randr (Wayland)"

    def query(self) -> DisplayConfig:
        # Try JSON output first
        try:
            result = subprocess.run(
                ["wlr-randr", "--json"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return self._parse_json(result.stdout)
        except FileNotFoundError:
            raise RuntimeError("wlr-randr not found")

        # Fallback to text
        result = subprocess.run(
            ["wlr-randr"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(f"wlr-randr failed: {result.stderr}")
        return self._parse_text(result.stdout)

    def _parse_json(self, text: str) -> DisplayConfig:
        data = json.loads(text)
        config = DisplayConfig()
        for output in data:
            mon = Monitor(name=output["name"])
            mon.connected = True
            mon.enabled = output.get("enabled", False)
            if mon.enabled:
                current = output.get("current_mode", {})
                mon.width = current.get("width", 0)
                mon.height = current.get("height", 0)
                mon.x = output.get("position", {}).get("x", 0)
                mon.y = output.get("position", {}).get("y", 0)
                mon.scale = output.get("scale", 1.0)
                transform = output.get("transform", "normal")
                mon.rotation, mon.reflection = self._parse_transform(transform)
            for m in output.get("modes", []):
                mode = Mode(
                    width=m["width"],
                    height=m["height"],
                    refresh_rate=round(m["refresh"] / 1000, 2) if m["refresh"] > 1000 else m["refresh"],
                    current=m.get("current", False),
                    preferred=m.get("preferred", False),
                )
                mon.modes.append(mode)
            config.monitors.append(mon)
        return config

    def _parse_text(self, text: str) -> DisplayConfig:
        config = DisplayConfig()
        current_mon: Monitor | None = None
        in_modes = False

        for line in text.splitlines():
            # Output header (not indented)
            if line and not line[0].isspace():
                if current_mon:
                    config.monitors.append(current_mon)
                name = line.split('"')[0].strip().rstrip()
                # Name might have trailing description in quotes
                name = line.split()[0]
                current_mon = Monitor(name=name, connected=True)
                in_modes = False
                continue

            if not current_mon:
                continue

            stripped = line.strip()

            if stripped.startswith("Enabled:"):
                current_mon.enabled = "yes" in stripped.lower()
            elif stripped.startswith("Position:"):
                pos = stripped.split(":", 1)[1].strip()
                parts = pos.split(",")
                if len(parts) == 2:
                    current_mon.x = int(parts[0])
                    current_mon.y = int(parts[1])
            elif stripped.startswith("Transform:"):
                transform = stripped.split(":", 1)[1].strip()
                current_mon.rotation, current_mon.reflection = self._parse_transform(transform)
            elif stripped.startswith("Scale:"):
                current_mon.scale = float(stripped.split(":", 1)[1].strip())
            elif stripped.startswith("Modes:"):
                in_modes = True
            elif stripped.startswith("Physical size:"):
                pm = re.match(r'Physical size:\s+(\d+)x(\d+)', stripped)
                if pm:
                    current_mon.physical_width_mm = int(pm.group(1))
                    current_mon.physical_height_mm = int(pm.group(2))
            elif in_modes and stripped and stripped[0].isdigit():
                # Mode line: "3840x2160 px, 60.000000 Hz (preferred, current)"
                mm = re.match(r'(\d+)x(\d+)\s+px,\s+([\d.]+)\s+Hz\s*(.*)', stripped)
                if mm:
                    flags = mm.group(4)
                    is_current = "current" in flags
                    is_preferred = "preferred" in flags
                    mode = Mode(
                        width=int(mm.group(1)),
                        height=int(mm.group(2)),
                        refresh_rate=float(mm.group(3)),
                        current=is_current,
                        preferred=is_preferred,
                    )
                    current_mon.modes.append(mode)
                    if is_current:
                        current_mon.width = mode.width
                        current_mon.height = mode.height
            elif in_modes and not stripped:
                in_modes = False

        if current_mon:
            config.monitors.append(current_mon)
        return config

    def _parse_transform(self, transform: str) -> tuple[str, str]:
        """Parse wlr-randr transform to (rotation, reflection)."""
        t = transform.lower().strip()
        mapping = {
            "normal": ("normal", "normal"),
            "90": ("left", "normal"),
            "180": ("inverted", "normal"),
            "270": ("right", "normal"),
            "flipped": ("normal", "x"),
            "flipped-90": ("left", "x"),
            "flipped-180": ("inverted", "x"),
            "flipped-270": ("right", "x"),
        }
        return mapping.get(t, ("normal", "normal"))

    def _to_transform(self, rotation: str, reflection: str) -> str:
        """Convert rotation+reflection to wlr-randr transform string."""
        flipped = reflection in ("x", "y", "xy")
        mapping = {
            ("normal", False): "normal",
            ("left", False): "90",
            ("inverted", False): "180",
            ("right", False): "270",
            ("normal", True): "flipped",
            ("left", True): "flipped-90",
            ("inverted", True): "flipped-180",
            ("right", True): "flipped-270",
        }
        return mapping.get((rotation, flipped), "normal")

    def apply(self, config: DisplayConfig) -> None:
        cmd = ["wlr-randr"]
        for mon in config.monitors:
            if not mon.connected:
                continue
            cmd += ["--output", mon.name]
            if not mon.enabled:
                cmd.append("--off")
            else:
                cmd.append("--on")
                current = mon.current_mode
                if current:
                    cmd += ["--mode", f"{current.width}x{current.height}@{current.refresh_rate:.6f}Hz"]
                cmd += ["--pos", f"{mon.x},{mon.y}"]
                cmd += ["--transform", self._to_transform(mon.rotation, mon.reflection)]
                cmd += ["--scale", str(mon.scale)]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            raise RuntimeError(f"wlr-randr failed: {result.stderr}")
