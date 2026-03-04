#!/usr/bin/env python3
"""displayctl — GTK 4 Display Management Tool"""

from __future__ import annotations

import sys

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gio, Gtk

from .backend import detect_backend
from .window import DisplayWindow


class DisplayCtlApp(Gtk.Application):
    def __init__(self):
        super().__init__(
            application_id="com.github.displayctl",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self.backend = None

    def do_activate(self):
        try:
            self.backend = detect_backend()
        except RuntimeError as e:
            dialog = Gtk.AlertDialog()
            dialog.set_message("Cannot detect display server")
            dialog.set_detail(str(e))
            dialog.set_buttons(["Quit"])
            # No parent window yet — show on default display
            dialog.show(None)
            return

        win = DisplayWindow(self, self.backend)
        win.present()


def main():
    app = DisplayCtlApp()
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
