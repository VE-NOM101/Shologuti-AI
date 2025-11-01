"""Higher-level rule helpers built on top of :mod:`shologuti.game.board`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .board import BoardState, MoveResult, PlayerId


@dataclass
class TurnState:
    """Tracks per-match turn metadata beyond the raw board."""

    to_move: PlayerId = 2  # Green traditionally opens.
    pending_capture_from: Optional[int] = None

    def swap_turn(self) -> None:
        self.pending_capture_from = None
        self.to_move = 2 if self.to_move == 1 else 1


class GameRules:
    """Encapsulates turn enforcement and capture chaining requirements."""

    def __init__(self) -> None:
        self.board = BoardState()
        self.turn = TurnState()

    def reset(self) -> None:
        self.board.reset()
        self.turn = TurnState()

    def apply_player_move(self, player: PlayerId, origin: int, target: int) -> MoveResult:
        if player != self.turn.to_move:
            return MoveResult(legal=False, error="not_your_turn")

        forced_origin = self.turn.pending_capture_from
        require_capture = forced_origin is not None

        if forced_origin is not None:
            if origin != forced_origin:
                return MoveResult(legal=False, error="must_continue_capture")

        result = self.board.apply_move(player, origin, target, require_capture=require_capture)
        if not result.legal:
            return result

        if result.captured is not None and result.must_continue:
            self.turn.pending_capture_from = target
        else:
            self.turn.swap_turn()

        if result.winner is not None:
            self.turn.pending_capture_from = None

        return result

    def remaining(self, player: PlayerId) -> int:
        return self.board.remaining(player)


