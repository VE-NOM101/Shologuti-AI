"""Board state and move validation for Sixteen - A Game of Tradition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from ..adjacency import Edge, neighbors


PlayerId = int  # 1 or 2


def opponent(player: PlayerId) -> PlayerId:
    return 2 if player == 1 else 1


@dataclass(frozen=True)
class MoveOption:
    origin: int
    target: int
    captured: Optional[int]


@dataclass
class MoveResult:
    legal: bool
    captured: Optional[int] = None
    must_continue: bool = False
    winner: Optional[PlayerId] = None
    error: Optional[str] = None


class BoardState:
    """Represents the full board and pieces for an active match."""

    def __init__(self) -> None:
        # 1-indexed board positions mirror the original Java implementation.
        self._slots: Dict[int, Optional[PlayerId]] = {i: None for i in range(1, 38)}
        self.reset()

    def reset(self) -> None:
        """Return the board to its initial state."""

        for i in self._slots:
            self._slots[i] = None

        # Opponent pieces populate the top of the board (1-16)
        for i in range(1, 17):
            self._slots[i] = 2

        # Current player pieces sit on the bottom (22-37)
        for i in range(22, 38):
            self._slots[i] = 1

    def snapshot(self) -> Dict[int, Optional[PlayerId]]:
        return dict(self._slots)

    def occupant(self, node: int) -> Optional[PlayerId]:
        return self._slots.get(node)

    def set_occupant(self, node: int, player: Optional[PlayerId]) -> None:
        self._slots[node] = player

    def simple_moves(self, origin: int, player: PlayerId) -> List[MoveOption]:
        moves: List[MoveOption] = []
        if self.occupant(origin) != player:
            return moves

        for edge in neighbors(origin):
            if self.occupant(edge.neighbor) is None:
                moves.append(MoveOption(origin=origin, target=edge.neighbor, captured=None))
        return moves

    def capture_moves(self, origin: int, player: PlayerId) -> List[MoveOption]:
        moves: List[MoveOption] = []
        if self.occupant(origin) != player:
            return moves

        for edge in neighbors(origin):
            if edge.landing is None:
                continue
            mid = self.occupant(edge.neighbor)
            if mid == opponent(player) and self.occupant(edge.landing) is None:
                moves.append(MoveOption(origin=origin, target=edge.landing, captured=edge.neighbor))
        return moves

    def legal_moves(
        self,
        origin: int,
        player: PlayerId,
        require_capture: bool = False,
    ) -> List[MoveOption]:
        captures = self.capture_moves(origin, player)
        if require_capture:
            return captures
        if captures:
            # Captures are possible but optional by default.
            return captures + self.simple_moves(origin, player)
        return self.simple_moves(origin, player)

    def apply_move(
        self,
        player: PlayerId,
        origin: int,
        target: int,
        require_capture: bool = False,
    ) -> MoveResult:
        options = self.legal_moves(origin, player, require_capture=require_capture)
        option = next((move for move in options if move.target == target), None)

        if option is None:
            return MoveResult(legal=False, error="illegal_move")

        self.set_occupant(origin, None)
        self.set_occupant(target, player)

        captured = option.captured
        if captured is not None:
            self.set_occupant(captured, None)

        winner = self._check_winner()
        must_continue = False
        if captured is not None and winner is None:
            # Verify if additional captures are available from the landing node.
            additional = self.capture_moves(target, player)
            must_continue = len(additional) > 0

        return MoveResult(legal=True, captured=captured, must_continue=must_continue, winner=winner)

    def remaining(self, player: PlayerId) -> int:
        return sum(1 for slot in self._slots.values() if slot == player)

    def _check_winner(self) -> Optional[PlayerId]:
        red = self.remaining(1)
        green = self.remaining(2)
        if red == 0 and green == 0:
            return None
        if red == 0:
            return 2
        if green == 0:
            return 1
        return None


