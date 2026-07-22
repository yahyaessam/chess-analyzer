"""Async WebSocket server that ties capture, vision, and engine together."""
import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional, Set

import chess
import websockets
from websockets.server import ServerConnection

from capture import ScreenCapture
from engine import StockfishEngine
from vision import BoardVision


class AnalyzerServer:
    """Capture board, generate FEN, analyse with Stockfish, broadcast JSON."""

    def __init__(self, stockfish_path: str = "stockfish", monitor: int = 1):
        self.stockfish_path = stockfish_path
        self.monitor = monitor
        self.clients: Set[ServerConnection] = set()
        self.capture = ScreenCapture(monitor)
        self.vision = BoardVision(threshold=0.45)
        self.engine = StockfishEngine(stockfish_path)
        self.payload: Dict[str, Any] = self._default_payload()
        self.last_fen: Optional[str] = None
        self.previous_eval_cp: Optional[int] = None
        self.is_flipped = False
        self.active_turn: str = "w"
        self._analyzing = False
        self._templates_mtime = 0.0
        self._stable_fen: Optional[str] = None
        self._stable_count = 0
        self._observed_board_fen: Optional[str] = None
        self._analyze_now = False

    @staticmethod
    def _default_payload() -> Dict[str, Any]:
        return {
            "timestamp": 0,
            "board_bounds": {"x": 0, "y": 0, "w": 0, "h": 0},
            "active_turn": "w",
            "is_flipped": False,
            "evaluation": {"type": "cp", "value": 0},
            "depth": 0,
            "moves": {"best": None, "alt_1": None, "alt_2": None},
            "threats": [],
            "blunder_alert": {"is_blunder": False, "square": None},
        }

    async def start(self) -> None:
        await self.engine.start()
        print("Analyzer server started. Listening on ws://127.0.0.1:8765")
        print("Press Ctrl+C to stop.")
        async with websockets.serve(self._ws_handler, "127.0.0.1", 8765):
            await self._loop()

    async def _ws_handler(self, ws: ServerConnection) -> None:
        self.clients.add(ws)
        try:
            async for message in ws:
                await self._handle_command(message)
        finally:
            self.clients.discard(ws)

    async def _handle_command(self, raw: str) -> None:
        try:
            cmd = json.loads(raw)
            action = cmd.get("action")
            if action == "calibrate":
                print("Calibration requested, opening ROI selector...")
                bounds = self.vision.calibrate(self.capture)
                print("Calibration returned:", bounds)
                if bounds:
                    self.capture.save_bounds(bounds)
                    self.payload["board_bounds"] = bounds
                    print("Saved board bounds:", bounds)
            elif action == "set_logical_bounds":
                self.capture.set_logical_bounds(cmd["bounds"], float(cmd["dpr"]))
                self.payload["board_bounds"] = self.capture.bounds or self.payload["board_bounds"]
            elif action == "capture_templates":
                print("Template capture requested, launching capture window...")
                script = Path(__file__).with_name("capture_templates.py")
                subprocess.Popen(
                    [sys.executable, str(script)],
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                )
            elif action == "set_flipped":
                self.is_flipped = bool(cmd.get("value", False))
                self.last_fen = None
                self._stable_fen = None
                self._stable_count = 0
                self._observed_board_fen = None
                self.payload["moves"] = {"best": None, "alt_1": None, "alt_2": None}
                self.payload["threats"] = []
                self.payload["evaluation"] = {"type": "cp", "value": 0}
                self.payload["blunder_alert"] = {"is_blunder": False, "square": None}
            elif action == "analyze":
                self._analyze_now = True
            elif action == "set_monitor":
                self.monitor = int(cmd.get("value", 1))
                self.capture = ScreenCapture(self.monitor)
        except Exception as e:
            print("command error:", e)

    def _reload_templates_if_changed(self) -> None:
        """Reload templates automatically when assets/templates changes."""
        if not self.vision.template_dir.exists():
            return
        try:
            mtime = max(p.stat().st_mtime for p in self.vision.template_dir.glob("*.png"))
            if mtime > self._templates_mtime:
                print("Templates changed, reloading...")
                self.vision.load_templates()
                self._templates_mtime = mtime
        except Exception as e:
            print("template reload error:", e)

    async def _loop(self) -> None:
        while True:
            await asyncio.sleep(0.05)
            self._reload_templates_if_changed()
            frame = self.capture.grab_board()
            self.payload["timestamp"] = int(time.time() * 1000)

            if frame is None:
                await self._broadcast()
                continue

            frame_changed = self.capture.changed(frame, threshold=0.5)
            if not frame_changed and not self._analyze_now and self._stable_count >= 2:
                await self._broadcast()
                continue

            fen = self.vision.get_fen(frame, self.is_flipped, turn=self.active_turn)
            if fen:
                try:
                    board = chess.Board(fen)
                    board_fen = board.board_fen()
                except ValueError:
                    board_fen = None

                if board_fen is not None and board_fen != self._observed_board_fen:
                    if self._observed_board_fen is not None:
                        new_turn = "b" if self.active_turn == "w" else "w"
                        parts = fen.split(" ")
                        parts[1] = new_turn
                        corrected_board = chess.Board(" ".join(parts))
                        if not corrected_board.is_valid():
                            self._stable_fen = None
                            self._stable_count = 0
                            await self._broadcast()
                            continue
                        self.active_turn = new_turn
                        fen = corrected_board.fen()
                    self._observed_board_fen = board_fen
                    self._stable_fen = fen
                    self._stable_count = 1
                    self.payload["moves"] = {"best": None, "alt_1": None, "alt_2": None}
                    self.payload["threats"] = []
                elif fen == self._stable_fen:
                    self._stable_count += 1
                else:
                    self._stable_fen = fen
                    self._stable_count = 1

                if (
                    self._stable_count >= 2
                    and not self._analyzing
                    and (fen != self.last_fen or self._analyze_now)
                ):
                    print("Detected FEN:", fen)
                    self.last_fen = fen
                    self._analyze_now = False
                    asyncio.create_task(self._analyze(chess.Board(fen)))
                    self.payload["active_turn"] = self.active_turn
            else:
                self._stable_fen = None
                self._stable_count = 0

            if self.capture.bounds:
                self.payload["board_bounds"] = self.capture.bounds
            self.payload["is_flipped"] = self.is_flipped
            await self._broadcast()

    async def _analyze(self, board: chess.Board) -> None:
        self._analyzing = True
        try:
            infos = await self.engine.analyze(board)
            self._update_moves_and_eval(board, infos)
            threat = await self.engine.null_move_threat(board)
            self.payload["threats"] = [threat] if threat else []
            self._update_blunder(board)
        except Exception as e:
            print("analysis error:", e)
        finally:
            self._analyzing = False

    def _update_moves_and_eval(self, board: chess.Board, infos: list) -> None:
        moves: Dict[str, Optional[Dict[str, Any]]] = {}
        keys = ["best", "alt_1", "alt_2"]
        top_score = None
        max_depth = 0

        for i, info in enumerate(infos[:3]):
            pv = info.get("pv", [])
            if pv:
                m = pv[0]
                score = info["score"].white()
                if score.is_mate():
                    val = score.mate()
                else:
                    val = score.score(mate_score=10000) or 0
                moves[keys[i]] = {
                    "from": chess.square_name(m.from_square),
                    "to": chess.square_name(m.to_square),
                    "pv_index": i + 1,
                    "score": val,
                }
                if top_score is None:
                    top_score = score
                depth = info.get("depth", 0)
                if depth and depth > max_depth:
                    max_depth = depth

        self.payload["moves"] = moves
        self.payload["active_turn"] = "w" if board.turn == chess.WHITE else "b"
        self.payload["depth"] = max_depth

        if top_score:
            self.payload["evaluation"] = {
                "type": "mate" if top_score.is_mate() else "cp",
                "value": top_score.mate() if top_score.is_mate() else top_score.score(),
            }

    def _update_blunder(self, board: chess.Board) -> None:
        eval_info = self.payload["evaluation"]
        if eval_info["type"] == "cp":
            current_cp = eval_info["value"]
        else:
            current_cp = 10000 if eval_info["value"] > 0 else -10000

        if self.last_fen and self.previous_eval_cp is not None:
            square = _detect_move_square(self.last_fen, board.fen())
            if square and abs(self.previous_eval_cp - current_cp) > 200:
                self.payload["blunder_alert"] = {"is_blunder": True, "square": square}
            else:
                self.payload["blunder_alert"] = {"is_blunder": False, "square": None}
        else:
            self.payload["blunder_alert"] = {"is_blunder": False, "square": None}

        self.previous_eval_cp = current_cp

    async def _broadcast(self) -> None:
        if self.clients:
            websockets.broadcast(self.clients, json.dumps(self.payload))


def _detect_move_square(old_fen: str, new_fen: str) -> Optional[str]:
    """Naively detect the destination square of the last move by FEN diff."""
    old_board = chess.Board(old_fen)
    new_board = chess.Board(new_fen)
    side = not new_board.turn
    candidates = []
    for sq in chess.SQUARES:
        old_piece = old_board.piece_at(sq)
        new_piece = new_board.piece_at(sq)
        if old_piece != new_piece and new_piece and new_piece.color == side:
            candidates.append(sq)
    return chess.square_name(candidates[0]) if candidates else None


async def main() -> None:
    stockfish = os.environ.get("STOCKFISH_PATH", "stockfish")
    monitor = int(os.environ.get("MONITOR_INDEX", "1"))

    if shutil.which(stockfish) is None:
        print(f"Stockfish not found: '{stockfish}'")
        print("Install Stockfish and add it to PATH, or set STOCKFISH_PATH to the binary.")
        print("Download: https://stockfishchess.org/download/")
        sys.exit(1)

    server = AnalyzerServer(stockfish, monitor)
    try:
        await server.start()
    except asyncio.CancelledError:
        pass
    finally:
        await server.engine.stop()


if __name__ == "__main__":
    asyncio.run(main())
