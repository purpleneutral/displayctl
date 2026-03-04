# displayctl

GTK 4 display configuration tool with a visual layout editor. Like arandr, but supports both X11 and Wayland.

## Features

- Visual drag-and-drop monitor layout editor with edge snapping
- Resolution and refresh rate selection per monitor
- Rotation, reflection, scaling, and brightness controls
- Primary monitor designation and enable/disable toggles
- Save/load display profiles as JSON
- Auto-detects X11 (xrandr) or Wayland (wlr-randr) backend

## Dependencies

- Python 3.10+
- GTK 4
- PyGObject
- `xrandr` (X11) or `wlr-randr` (Wayland)

## Install

### From AUR (Arch Linux)

```
yay -S displayctl
```

### From source

```
python -m build --wheel
pip install dist/displayctl-*.whl
```

## Usage

```
displayctl
```

Or run directly from source:

```
python -m displayctl
```

## License

GPL-3.0-or-later
