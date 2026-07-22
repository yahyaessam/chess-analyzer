"""Screen capture helpers using mss."""
import json
from pathlib import Path
from typing import Any, Dict, Optional

import cv2
import mss
import numpy as np

CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
BOUNDS_FILE = CONFIG_DIR / "board_bounds.json"


class ScreenCapture:
    """Grab raw monitor/board frames and track pixel-level changes."""

    def __init__(self, monitor_index: int = 1):
        self.sct = mss.mss()
        self.monitor_index = monitor_index
        self.bounds: Optional[Dict[str, int]] = None
        self._previous: Optional[np.ndarray] = None
        self.load_bounds()

    def load_bounds(self) -> Optional[Dict[str, int]]:
        """Load board bounds from config (physical pixel coordinates)."""
        if BOUNDS_FILE.exists():
            with open(BOUNDS_FILE, encoding="utf-8") as f:
                data = json.load(f)
            self.bounds = data.get("physical", data)
        return self.bounds

    def save_bounds(self, bounds: Dict[str, int]) -> None:
        """Persist physical board bounds."""
        self.bounds = bounds
        payload = {"physical": bounds, "logical": None}
        if BOUNDS_FILE.exists():
            with open(BOUNDS_FILE, encoding="utf-8") as f:
                existing = json.load(f)
            payload["logical"] = existing.get("logical")
        with open(BOUNDS_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)

    def set_logical_bounds(self, logical: Dict[str, int], dpr: float) -> None:
        """Convert Electron logical bounds to physical mss bounds."""
        physical = {
            "x": int(round(logical["x"] * dpr)),
            "y": int(round(logical["y"] * dpr)),
            "w": int(round(logical["w"] * dpr)),
            "h": int(round(logical["h"] * dpr)),
        }
        self.bounds = physical
        with open(BOUNDS_FILE, "w", encoding="utf-8") as f:
            json.dump({"logical": logical, "physical": physical}, f, indent=2)

    def grab_full(self) -> np.ndarray:
        """Capture the entire selected monitor."""
        monitor = self.sct.monitors[self.monitor_index]
        return np.array(self.sct.grab(monitor))

    def grab_board(self) -> Optional[np.ndarray]:
        """Capture the calibrated board region."""
        if not self.bounds:
            return None
        bbox = {
            "left": self.bounds["x"],
            "top": self.bounds["y"],
            "width": self.bounds["w"],
            "height": self.bounds["h"],
        }
        return np.array(self.sct.grab(bbox))

    def changed(self, frame: np.ndarray, threshold: float = 8.0) -> bool:
        """Fast pixel diff against the previously captured board frame."""
        if self._previous is None or self._previous.shape != frame.shape:
            self._previous = frame.copy()
            return True
        diff = float(cv2.absdiff(frame, self._previous).mean())
        if diff > threshold:
            self._previous = frame.copy()
            return True
        return False
