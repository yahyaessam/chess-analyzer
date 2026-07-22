"""Chessboard vision: grid slicing, template matching, and FEN generation."""
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import chess

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "assets" / "templates"


class BoardVision:
    """Convert a cropped board image into a FEN string."""

    def __init__(
        self,
        template_dir: Path = TEMPLATE_DIR,
        threshold: float = 0.55,
        square_margin: float = 0.0,
    ):
        self.template_dir = template_dir
        self.threshold = threshold
        self.square_margin = square_margin
        self.templates: List[Tuple[str, np.ndarray, np.ndarray]] = []
        self.load_templates()

    def load_templates(self) -> None:
        """Load piece template images (w_P.png, b_p.png, ...)."""
        self.templates.clear()
        if not self.template_dir.exists():
            return
        for path in sorted(self.template_dir.glob("*.png")):
            name = path.stem
            if not (name.startswith("w_") or name.startswith("b_")):
                continue
            img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            if img is None:
                continue
            bgr = img[:, :, :3]
            if img.shape[2] == 4:
                mask = (img[:, :, 3] > 128).astype(np.uint8)
            else:
                mask = np.ones(bgr.shape[:2], dtype=np.uint8)
            self.templates.append((name, bgr, mask))

    def calibrate(self, capture) -> Optional[Dict[str, int]]:
        """Open a manual ROI selector to choose the board region."""
        frame = capture.grab_full()
        print("calibrate: grabbed full frame shape:", frame.shape if frame is not None else None)
        if frame is None:
            return None
        win = "Drag to select the chessboard, press SPACE or ENTER"
        cv2.namedWindow(win, cv2.WINDOW_NORMAL)
        r = cv2.selectROI(win, frame, fromCenter=False, showCrosshair=True)
        cv2.destroyWindow(win)
        print("calibrate: selectROI returned:", r)
        if r[2] <= 0 or r[3] <= 0:
            print("calibrate: selection cancelled or invalid")
            return None
        return {"x": int(r[0]), "y": int(r[1]), "w": int(r[2]), "h": int(r[3])}

    @staticmethod
    def _cell_bgr(cell: np.ndarray) -> np.ndarray:
        """Drop alpha channel from a mss BGRA capture."""
        return cell[:, :, :3] if cell.shape[2] == 4 else cell

    def get_fen(self, board_img: np.ndarray, is_flipped: bool = False, turn: str = "w") -> Optional[str]:
        """Slice the board image into 64 squares and build a FEN."""
        if board_img is None or board_img.size == 0:
            return None
        h, w = board_img.shape[:2]
        sq_w, sq_h = w / 8, h / 8
        rows: List[str] = []

        cells: List[np.ndarray] = []
        for rank in range(8):
            for file in range(8):
                if is_flipped:
                    sq_file = 7 - file
                    sq_rank = 7 - rank
                else:
                    sq_file = file
                    sq_rank = rank

                x1 = int(round(sq_file * sq_w + sq_w * self.square_margin))
                y1 = int(round(sq_rank * sq_h + sq_h * self.square_margin))
                x2 = int(round((sq_file + 1) * sq_w - sq_w * self.square_margin))
                y2 = int(round((sq_rank + 1) * sq_h - sq_h * self.square_margin))
                cells.append(board_img[y1:y2, x1:x2])

        for rank in range(8):
            row = ""
            empty = 0
            for file in range(8):
                idx = rank * 8 + file
                cell = cells[idx]
                piece = self._classify(cell)

                if piece == ".":
                    empty += 1
                else:
                    if empty:
                        row += str(empty)
                        empty = 0
                    row += piece

            if empty:
                row += str(empty)
            rows.append(row)

        fen = "/".join(rows) + f" {turn} - - 0 1"
        try:
            board = chess.Board(fen)
            if board.king(chess.WHITE) is None or board.king(chess.BLACK) is None:
                return None
            return board.fen()
        except ValueError:
            return None

    @staticmethod
    def _masked_score(cell_bgr: np.ndarray, templ_bgr: np.ndarray, mask: np.ndarray, color_weight: float = 1.5) -> float:
        """Shape + color score using only the masked (piece) pixels."""
        mask_bool = mask > 0
        mask_3d = mask_bool.astype(np.float32)
        if mask_3d.ndim == 2:
            mask_3d = mask_3d[..., None]
        mask_sum = mask_3d.sum()
        if mask_sum == 0:
            return -1.0

        cell_f = cell_bgr.astype(np.float32)
        templ_f = templ_bgr.astype(np.float32)

        cell_mean = (cell_f * mask_3d).sum(axis=(0, 1)) / mask_sum
        templ_mean = (templ_f * mask_3d).sum(axis=(0, 1)) / mask_sum

        cell_centered = (cell_f - cell_mean) * mask_3d
        templ_centered = (templ_f - templ_mean) * mask_3d

        numerator = float(np.sum(cell_centered * templ_centered))
        denom = float(np.sqrt(np.sum(cell_centered * cell_centered) * np.sum(templ_centered * templ_centered)))
        shape_score = 0.0 if denom < 1e-6 else numerator / denom

        max_color_dist = 255.0 * np.sqrt(3.0)
        color_dist = float(np.linalg.norm(cell_mean - templ_mean)) / max_color_dist

        return shape_score - color_weight * color_dist

    def _classify(self, cell: np.ndarray) -> str:
        """Return FEN character for the cell, or '.' for empty."""
        if not self.templates:
            return "."

        best_score = self.threshold
        best_label = "."
        cell_bgr = self._cell_bgr(cell)
        cw, ch = cell_bgr.shape[1], cell_bgr.shape[0]

        for label, templ, mask in self.templates:
            resized = cv2.resize(templ, (cw, ch))
            rmask = cv2.resize(mask, (cw, ch))
            score = self._masked_score(cell_bgr, resized, rmask)
            if score > best_score:
                best_score = score
                best_label = label

        if best_label == ".":
            return "."
        return self._label_to_fen(best_label)

    @staticmethod
    def _label_to_fen(label: str) -> str:
        color, ptype = label.split("_")
        return ptype.upper() if color == "w" else ptype.lower()
