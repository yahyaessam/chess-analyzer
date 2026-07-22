"""Async Stockfish wrapper using python-chess native UCI support."""
from typing import Any, Dict, List, Optional

import chess
import chess.engine


class StockfishEngine:
    """Lightweight wrapper around a local Stockfish binary."""

    def __init__(self, path: str = "stockfish"):
        self.path = path
        self._transport: Optional[Any] = None
        self._engine: Optional[chess.engine.UciProtocol] = None

    async def start(self) -> None:
        self._transport, self._engine = await chess.engine.popen_uci(self.path)
        # Configure engine for better analysis quality
        await self._engine.configure({
            "Threads": 2,
            "Hash": 128,
        })

    async def stop(self) -> None:
        try:
            if self._engine:
                await self._engine.quit()
        except Exception:
            pass
        finally:
            self._engine = None
            if self._transport:
                self._transport.close()
                self._transport = None

    async def analyze(
        self,
        board: chess.Board,
        limit: chess.engine.Limit = None,
        multipv: int = 3,
    ) -> List[Dict[str, Any]]:
        if limit is None:
            limit = chess.engine.Limit(time=0.2)
        result = await self._engine.analyse(board, limit, multipv=multipv)
        return result if isinstance(result, list) else [result]

    async def null_move_threat(
        self,
        board: chess.Board,
        limit: chess.engine.Limit = None,
    ) -> Optional[Dict[str, Any]]:
        """Ask Stockfish for the opponent's strongest reply from the same position.

        Instead of pushing a null move (which UCI cannot transmit), create a board
        with the opponent to move. This is equivalent to passing the turn.
        """
        if limit is None:
            limit = chess.engine.Limit(time=0.1)

        # If the side to move is in check, a pass would be illegal; there is no useful
        # null-move threat to report (the engine's best move will deal with the check).
        if board.is_check():
            return None

        fen = board.fen()
        parts = fen.split(" ")
        parts[1] = "b" if board.turn == chess.WHITE else "w"
        opp_fen = " ".join(parts)

        nm_board = chess.Board(opp_fen)
        if not nm_board.is_valid():
            return None

        result = await self._engine.analyse(nm_board, limit, multipv=1)
        info = result[0] if isinstance(result, list) else result

        if not info or "pv" not in info or not info["pv"]:
            return None

        move = info["pv"][0]
        score = info["score"].pov(nm_board.turn)

        if score.is_mate():
            value = score.mate()
            severity = "high"
            threat_type = "mate"
        else:
            cp = score.score(mate_score=10000)
            value = cp
            if cp is None:
                return None
            if cp > 300:
                severity = "high"
            elif cp > 150:
                severity = "medium"
            else:
                severity = "low"
            threat_type = "attack"

        return {
            "from": chess.square_name(move.from_square),
            "to": chess.square_name(move.to_square),
            "severity": severity,
            "type": threat_type,
            "score": value,
        }
