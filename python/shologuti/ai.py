"""AI agents for the Shologuti 16-piece game."""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from typing import List, Optional

from .game.board import MoveOption, PlayerId, opponent
from .game.rules import GameRules


Score = float


@dataclass(frozen=True)
class PlannedMove:
    """Represents a move chosen by an AI agent."""

    origin: int
    target: int


def _winner_for_state(state: GameRules) -> Optional[PlayerId]:
    """Return the winner for ``state`` if the match has ended."""

    red_remaining = state.remaining(1)
    green_remaining = state.remaining(2)

    if red_remaining == 0 and green_remaining == 0:
        return None
    if red_remaining == 0:
        return 2
    if green_remaining == 0:
        return 1

    # No pieces captured but current player cannot move.
    if not _generate_moves(state):
        return opponent(state.turn.to_move)

    return None


def _generate_moves(state: GameRules, for_player: Optional[PlayerId] = None) -> List[MoveOption]:
    """Enumerate all legal moves for the player who is about to act."""

    player = state.turn.to_move if for_player is None else for_player
    snapshot = state.board.snapshot()

    if state.turn.pending_capture_from is not None and player == state.turn.to_move:
        origin = state.turn.pending_capture_from
        return state.board.legal_moves(origin, player, require_capture=True)

    moves: List[MoveOption] = []
    for origin, occupant_id in snapshot.items():
        if occupant_id != player:
            continue
        moves.extend(state.board.legal_moves(origin, player))
    return moves


class MinimaxAgent:
    """A depth-limited minimax agent with alpha-beta pruning."""

    def __init__(self, player: PlayerId, depth: int = 3) -> None:
        self.player = player
        self.depth = depth

    def choose_move(self, state: GameRules) -> Optional[PlannedMove]:
        """Return the best move for this agent from ``state``."""

        moves = _generate_moves(state)
        if not moves:
            return None

        best_score = -math.inf
        best_move: Optional[MoveOption] = None

        alpha = -math.inf
        beta = math.inf

        for option in moves:
            child_state = copy.deepcopy(state)
            result = child_state.apply_player_move(self.player, option.origin, option.target)
            if not result.legal:
                continue

            score = self._minimax(child_state, self.depth - 1, alpha, beta)

            if score > best_score:
                best_score = score
                best_move = option

            alpha = max(alpha, best_score)
            if beta <= alpha:
                break

        if best_move is None:
            return None

        return PlannedMove(origin=best_move.origin, target=best_move.target)

    def _minimax(self, state: GameRules, depth: int, alpha: float, beta: float) -> Score:
        winner = _winner_for_state(state)
        if winner is not None:
            if winner == self.player:
                return math.inf
            return -math.inf

        if depth <= 0:
            return self._evaluate(state)

        player_to_move = state.turn.to_move
        maximizing = player_to_move == self.player

        moves = _generate_moves(state)
        if not moves:
            return self._evaluate(state)

        if maximizing:
            value = -math.inf
            for option in moves:
                child_state = copy.deepcopy(state)
                result = child_state.apply_player_move(player_to_move, option.origin, option.target)
                if not result.legal:
                    continue

                value = max(value, self._minimax(child_state, depth - 1, alpha, beta))
                alpha = max(alpha, value)
                if beta <= alpha:
                    break
            return value

        value = math.inf
        for option in moves:
            child_state = copy.deepcopy(state)
            result = child_state.apply_player_move(player_to_move, option.origin, option.target)
            if not result.legal:
                continue

            value = min(value, self._minimax(child_state, depth - 1, alpha, beta))
            beta = min(beta, value)
            if beta <= alpha:
                break
        return value

    def _evaluate(self, state: GameRules) -> Score:
        my_pieces = state.remaining(self.player)
        opp_pieces = state.remaining(opponent(self.player))
        material = my_pieces - opp_pieces

        my_moves = len(_generate_moves(state, for_player=self.player))
        opp_moves = len(_generate_moves(state, for_player=opponent(self.player)))
        mobility = my_moves - opp_moves

        pending_bonus = 0
        if state.turn.pending_capture_from is not None and state.turn.to_move == self.player:
            pending_bonus = 1

        return material * 10 + mobility + pending_bonus


__all__ = ["MinimaxAgent", "PlannedMove"]


