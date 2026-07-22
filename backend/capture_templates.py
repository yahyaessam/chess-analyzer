"""Capture piece templates from a real board in the starting position.

Run this while the calibrated board is in the normal starting position.
It extracts one template per piece type and writes transparent PNGs to
assets/templates/ so the analyzer can match your chess site's pieces.
"""
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import mss
import numpy as np

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "assets" / "templates"
CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "board_bounds.json"
LOG_FILE = Path(__file__).resolve().parent.parent / "config" / "capture_templates.log"


def capture_board() -> Tuple[np.ndarray, Dict[str, int]]:
    """Capture the currently calibrated board region."""
    if not CONFIG_FILE.exists():
        raise FileNotFoundError("No calibration found. Run backend and calibrate first.")
    with open(CONFIG_FILE, encoding="utf-8") as f:
        data = json.load(f)
    bounds = data.get("physical", data)
    with mss.MSS() as sct:
        bbox = {
            "left": bounds["x"],
            "top": bounds["y"],
            "width": bounds["w"],
            "height": bounds["h"],
        }
        return np.array(sct.grab(bbox)), bounds


def slice_cells(board_img: np.ndarray) -> List[Tuple[int, int, np.ndarray]]:
    """Return (rank, file, cell_image) for each of the 64 squares.

    rank and file are in visual coordinates: rank 0 is the top row on screen.
    """
    h, w = board_img.shape[:2]
    sq_w, sq_h = w / 8, h / 8
    cells: List[Tuple[int, int, np.ndarray]] = []
    for rank in range(8):
        for file in range(8):
            x1 = int(round(file * sq_w))
            y1 = int(round(rank * sq_h))
            x2 = int(round((file + 1) * sq_w))
            y2 = int(round((rank + 1) * sq_h))
            cells.append((rank, file, board_img[y1:y2, x1:x2]))
    return cells


def cluster_square_colors(cells: List[Tuple[int, int, np.ndarray]]) -> Tuple[np.ndarray, np.ndarray]:
    """Cluster the 64 square median BGR colors into light and dark groups."""
    medians = np.float32([np.median(cell[:, :, :3], axis=(0, 1)) for (_, _, cell) in cells])
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(medians, 2, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)
    # Determine which cluster is lighter by average brightness.
    brightness = centers.mean(axis=1)
    light_idx = int(np.argmax(brightness))
    dark_idx = 1 - light_idx
    light_color = centers[light_idx]
    dark_color = centers[dark_idx]
    return light_color, dark_color


def square_color(cell: np.ndarray, light_color: np.ndarray, dark_color: np.ndarray) -> int:
    """Return 1 for light, 0 for dark based on median BGR color distance."""
    median = np.median(cell[:, :, :3], axis=(0, 1))
    return 1 if np.linalg.norm(median - light_color) < np.linalg.norm(median - dark_color) else 0


def piece_mask(cell: np.ndarray, light_color: np.ndarray, dark_color: np.ndarray) -> np.ndarray:
    """Create a mask isolating the piece from the square background."""
    bgr = cell[:, :, :3]
    color = square_color(cell, light_color, dark_color)
    bg = light_color if color == 1 else dark_color
    bg = bg.astype(np.uint8)
    diff = cv2.absdiff(bgr, bg)
    gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    # Otsu threshold separates piece/shadows from background.
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Keep only the largest connected region (the piece + close shadow).
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        largest = max(contours, key=cv2.contourArea)
        mask = np.zeros_like(mask)
        cv2.drawContours(mask, [largest], -1, 255, -1)
    # Close small gaps inside the piece.
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    return mask


def build_templates(cells: List[Tuple[int, int, np.ndarray]], white_bottom: bool) -> Dict[str, np.ndarray]:
    """Extract piece templates from the starting position."""
    light_color, dark_color = cluster_square_colors(cells)

    # Label grid for the starting position in visual coordinates.
    if white_bottom:
        grid = [
            ["b_R", "b_N", "b_B", "b_Q", "b_K", "b_B", "b_N", "b_R"],
            ["b_P"] * 8,
            [" "] * 8,
            [" "] * 8,
            [" "] * 8,
            [" "] * 8,
            ["w_P"] * 8,
            ["w_R", "w_N", "w_B", "w_Q", "w_K", "w_B", "w_N", "w_R"],
        ]
    else:
        grid = [
            ["w_R", "w_N", "w_B", "w_Q", "w_K", "w_B", "w_N", "w_R"],
            ["w_P"] * 8,
            [" "] * 8,
            [" "] * 8,
            [" "] * 8,
            [" "] * 8,
            ["b_P"] * 8,
            ["b_R", "b_N", "b_B", "b_Q", "b_K", "b_B", "b_N", "b_R"],
        ]

    candidates: Dict[str, List[Tuple[np.ndarray, np.ndarray]]] = {}
    for rank, file, cell in cells:
        label = grid[rank][file]
        if label == " ":
            continue
        mask = piece_mask(cell, light_color, dark_color)
        candidates.setdefault(label, []).append((cell, mask))

    # For each piece type, pick the cell with the largest mask area.
    chosen: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
    for label, items in candidates.items():
        best = max(items, key=lambda x: int(cv2.countNonZero(x[1])))
        chosen[label] = best
    return chosen


def save_templates(templates: Dict[str, Tuple[np.ndarray, np.ndarray]]) -> None:
    """Write transparent PNG templates to assets/templates/."""
    TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)
    for path in TEMPLATE_DIR.glob("*.png"):
        path.unlink()
    for label, (cell, mask) in templates.items():
        bgr = cell[:, :, :3]
        b, g, r = cv2.split(bgr)
        bgra = cv2.merge([b, g, r, mask])
        out_path = TEMPLATE_DIR / f"{label}.png"
        cv2.imwrite(str(out_path), bgra)
        print(f"Saved {out_path}")


def _log(message: str) -> None:
    """Print to console and write to a log file for easier debugging."""
    print(message)
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(message + "\n")
    except Exception:
        pass


def _show_preview(name: str, img: np.ndarray) -> None:
    """Show a non-blocking OpenCV preview window while the user types in the console."""
    cv2.namedWindow(name, cv2.WINDOW_NORMAL)
    cv2.imshow(name, img)
    try:
        cv2.setWindowProperty(name, cv2.WND_PROP_TOPMOST, 1)
    except cv2.error:
        pass


def _ask(prompt: str) -> str:
    """Prompt in the console and log the question."""
    _log(prompt)
    try:
        return input(prompt).strip().lower()
    except EOFError:
        return "q"


def _select_orientation(board_img: np.ndarray) -> bool | None:
    """Show the captured board and ask whether white is at the bottom."""
    preview = board_img.copy()
    cv2.putText(
        preview,
        "White pieces at bottom?  W = bottom  B = top  Q = quit",
        (20, 40),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.7,
        (0, 255, 0),
        2,
    )
    _show_preview("Template Capture", preview)
    answer = _ask("White pieces at bottom? (w/b/q): ")
    cv2.destroyAllWindows()

    if answer in ("q", "quit"):
        return None
    if answer == "w":
        return True
    if answer == "b":
        return False
    return None


def main() -> None:
    # Clear previous log.
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        LOG_FILE.write_text("", encoding="utf-8")
    except Exception:
        pass

    if not CONFIG_FILE.exists():
        _log("No calibration found. Calibrate the board first (Ctrl+Shift+C).")
        return

    _log("Template capture started.")
    cv2.startWindowThread()

    _log("=" * 50)
    _log("INSTRUCTIONS:")
    _log("1. HIDE the analyzer overlay (Ctrl+Shift+H or Hide/Show).")
    _log("2. Open your chess site in the STARTING POSITION.")
    _log("3. Make sure the board is fully visible.")
    _log("4. Come back to this window and press Enter.")
    _log("5. After pressing Enter you will have 3 seconds to switch")
    _log("   to the chess site before the capture happens.")
    _log("=" * 50)

    ready = _ask("Ready to capture? Press Enter, or type Q to quit: ")
    if ready == "q":
        _log("Cancelled by user.")
        return

    for i in range(3, 0, -1):
        _log(f"Capturing in {i}... switch to the chess site now.")
        time.sleep(1)

    board_img, bounds = capture_board()
    _log(f"Captured board region: {bounds}")

    # Show the captured board while asking orientation.
    _show_preview("Template Capture", board_img)
    white_bottom = _select_orientation(board_img)
    cv2.destroyAllWindows()
    if white_bottom is None:
        _log("Cancelled during orientation selection.")
        return

    cells = slice_cells(board_img)
    templates = build_templates(cells, white_bottom)
    if len(templates) != 12:
        _log(f"Warning: expected 12 templates, got {len(templates)}. Check board position.")
    save_templates(templates)
    _log("Template capture complete. Restart the backend for changes to take effect.")


if __name__ == "__main__":
    main()
