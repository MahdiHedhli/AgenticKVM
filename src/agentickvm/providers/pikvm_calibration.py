"""PiKVM screenshot-based mouse calibration helpers.

The live input phase needs deterministic conversion from screenshot coordinates
to PiKVM absolute HID coordinates. This module is pure math and performs no IO.
"""

from __future__ import annotations

from dataclasses import dataclass


PIKVM_ABSOLUTE_MAX = 65535


@dataclass(frozen=True)
class PiKVMScreenshotCalibration:
    """Map screenshot pixel coordinates to absolute HID coordinates."""

    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width <= 1 or self.height <= 1:
            raise ValueError("screenshot calibration requires width and height greater than 1")

    def map_point(self, *, x: int, y: int) -> dict[str, int]:
        """Return clamped PiKVM absolute HID coordinates for a screenshot point."""

        clamped_x = min(max(x, 0), self.width - 1)
        clamped_y = min(max(y, 0), self.height - 1)
        return {
            "absolute_x": round(clamped_x * PIKVM_ABSOLUTE_MAX / (self.width - 1)),
            "absolute_y": round(clamped_y * PIKVM_ABSOLUTE_MAX / (self.height - 1)),
        }


__all__ = ["PIKVM_ABSOLUTE_MAX", "PiKVMScreenshotCalibration"]
