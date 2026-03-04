"""Edge-snapping logic for monitor positioning."""

from __future__ import annotations


class Snap:
    """Calculates snap positions from other monitor rectangles."""

    def __init__(
        self,
        dragged_size: tuple[int, int],
        tolerance: int,
        rects: list[tuple[int, int, int, int]],
    ):
        dw, dh = dragged_size
        self.tolerance = tolerance
        self.snap_x: set[int] = {0}
        self.snap_y: set[int] = {0}

        for rx, ry, rw, rh in rects:
            # Left-to-left, right-to-right edge alignment
            self.snap_x.add(rx)
            self.snap_x.add(rx + rw - dw)
            # Right-to-left, left-to-right abutment
            self.snap_x.add(rx + rw)
            self.snap_x.add(rx - dw)
            # Center alignment
            self.snap_x.add(rx + rw // 2 - dw // 2)

            # Same for Y
            self.snap_y.add(ry)
            self.snap_y.add(ry + rh - dh)
            self.snap_y.add(ry + rh)
            self.snap_y.add(ry - dh)
            self.snap_y.add(ry + rh // 2 - dh // 2)

    def suggest(self, x: int, y: int) -> tuple[int, int]:
        """Return snapped (x, y) position."""
        best_x = min(self.snap_x, key=lambda sx: abs(sx - x), default=x)
        best_y = min(self.snap_y, key=lambda sy: abs(sy - y), default=y)
        if abs(best_x - x) <= self.tolerance:
            x = best_x
        if abs(best_y - y) <= self.tolerance:
            y = best_y
        return x, y
