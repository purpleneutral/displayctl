"""Save/load display profiles as JSON."""

from __future__ import annotations

import json
from pathlib import Path

from .model import DisplayConfig

PROFILES_DIR = Path.home() / ".config" / "displayctl" / "profiles"


def save_profile(config: DisplayConfig, name: str) -> Path:
    """Save current configuration as a named profile."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    path = PROFILES_DIR / f"{name}.json"
    data = {
        "monitors": [
            {
                "name": m.name,
                "enabled": m.enabled,
                "primary": m.primary,
                "x": m.x,
                "y": m.y,
                "mode": {
                    "width": m.width,
                    "height": m.height,
                    "refresh_rate": m.current_mode.refresh_rate if m.current_mode else 60.0,
                },
                "rotation": m.rotation,
                "reflection": m.reflection,
                "scale": m.scale,
                "brightness": m.brightness,
            }
            for m in config.monitors
            if m.connected
        ]
    }
    path.write_text(json.dumps(data, indent=2))
    return path


def load_profile(name: str) -> dict:
    """Load a profile by name."""
    path = PROFILES_DIR / f"{name}.json"
    return json.loads(path.read_text())


def list_profiles() -> list[str]:
    """List available profile names."""
    if not PROFILES_DIR.exists():
        return []
    return sorted(p.stem for p in PROFILES_DIR.glob("*.json"))


def delete_profile(name: str) -> None:
    """Delete a profile."""
    path = PROFILES_DIR / f"{name}.json"
    if path.exists():
        path.unlink()


def apply_profile(config: DisplayConfig, profile_data: dict) -> None:
    """Merge profile data into current config, matching by monitor name."""
    by_name = {m["name"]: m for m in profile_data.get("monitors", [])}
    for mon in config.monitors:
        if mon.name not in by_name:
            continue
        p = by_name[mon.name]
        mon.enabled = p.get("enabled", True)
        mon.primary = p.get("primary", False)
        mon.x = p.get("x", 0)
        mon.y = p.get("y", 0)
        mon.rotation = p.get("rotation", "normal")
        mon.reflection = p.get("reflection", "normal")
        mon.scale = p.get("scale", 1.0)
        mon.brightness = p.get("brightness", 1.0)

        # Find matching mode
        pm = p.get("mode", {})
        tw, th, tr = pm.get("width", 0), pm.get("height", 0), pm.get("refresh_rate", 0)
        for mode in mon.modes:
            mode.current = False
        for mode in mon.modes:
            if mode.width == tw and mode.height == th and abs(mode.refresh_rate - tr) < 0.1:
                mode.current = True
                mon.width = mode.width
                mon.height = mode.height
                break
