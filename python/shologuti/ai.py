from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass
from typing import List, Optional

from .game.board import MoveOption, PlayerId, opponent
from .game.rules import GameRules


Score = float


@dataclass(frozen=True)
class PlannedMove:
    origin: int
    target: int


# Determine if someone already won
def _winner_for_state(state: GameRules) -> Optional[PlayerId]:
    red_remaining = state.remaining(1)
    green_remaining = state.remaining(2)

    if red_remaining == 0 and green_remaining == 0:
        return None
    if red_remaining == 0:
        return 2
    if green_remaining == 0:
        return 1

    if not _generate_moves(state):
        return opponent(state.turn.to_move)

    return None


# List legal moves for a player
def _generate_moves(state: GameRules, for_player: Optional[PlayerId] = None) -> List[MoveOption]:
    player = state.turn.to_move if for_player is None else for_player

    enforce_origin: Optional[int] = None
    if player == state.turn.to_move:
        enforce_origin = state.turn.pending_capture_from

    if enforce_origin is not None:
        if state.board.occupant(enforce_origin) != player:
            return []
        forced = state.board.capture_moves(enforce_origin, player)
        return forced

    captures: List[MoveOption] = []
    quiets: List[MoveOption] = []
    snapshot = state.board.snapshot()
    for origin, occupant_id in snapshot.items():
        if occupant_id != player:
            continue
        capture_moves = state.board.capture_moves(origin, player)
        if capture_moves:
            captures.extend(capture_moves)
        else:
            quiets.extend(state.board.simple_moves(origin, player))

    if captures:
        return captures
    return quiets


class MinimaxAgent:
    def __init__(self, player: PlayerId, depth: int = 3) -> None:
        self.player = player
        self.depth = depth

    def choose_move(self, state: GameRules) -> Optional[PlannedMove]:
        # Single-ply search entry point
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

            if score > best_score or best_move is None:
                best_score = score
                best_move = option

            alpha = max(alpha, best_score)
            if beta <= alpha:
                break

        if best_move is None:
            return None

        return PlannedMove(origin=best_move.origin, target=best_move.target)

    def _minimax(self, state: GameRules, depth: int, alpha: float, beta: float) -> Score:
        # Depth-limited minimax core
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
            legal_branch_found = False
            for option in moves:
                child_state = copy.deepcopy(state)
                result = child_state.apply_player_move(player_to_move, option.origin, option.target)
                if not result.legal:
                    continue

                legal_branch_found = True
                value = max(value, self._minimax(child_state, depth - 1, alpha, beta))
                alpha = max(alpha, value)
                if beta <= alpha:
                    break
            if not legal_branch_found:
                return self._evaluate(state)
            return value

        value = math.inf
        legal_branch_found = False
        for option in moves:
            child_state = copy.deepcopy(state)
            result = child_state.apply_player_move(player_to_move, option.origin, option.target)
            if not result.legal:
                continue

            legal_branch_found = True
            value = min(value, self._minimax(child_state, depth - 1, alpha, beta))
            beta = min(beta, value)
            if beta <= alpha:
                break
        if not legal_branch_found:
            return self._evaluate(state)
        return value

    def _evaluate(self, state: GameRules) -> Score:
        # Simple material plus mobility score
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

    @property
    def description(self) -> str:
        return f"Minimax(depth={self.depth})"


class _MCTSNode:
    def __init__(
        self,
        state: GameRules,
        parent: Optional["_MCTSNode"],
        move: Optional[MoveOption],
    ) -> None:
        self.state = state
        self.parent = parent
        self.move = move
        self.children: List[_MCTSNode] = []
        self.untried_moves: List[MoveOption] = _generate_moves(state)
        self.visits: int = 0
        self.wins: float = 0.0

    def is_terminal(self) -> bool:
        if _winner_for_state(self.state) is not None:
            return True
        return len(_generate_moves(self.state)) == 0

    def is_fully_expanded(self) -> bool:
        return len(self.untried_moves) == 0

    def best_child(self, exploration_constant: float) -> "_MCTSNode":
        def ucb_score(child: _MCTSNode) -> float:
            if child.visits == 0:
                return math.inf
            exploitation = child.wins / child.visits
            exploration = exploration_constant * math.sqrt(max(math.log(self.visits), 0.0) / child.visits)
            return exploitation + exploration

        return max(self.children, key=ucb_score)


class MCTSAgent:
    def __init__(
        self,
        player: PlayerId,
        iterations: int = 100,
        exploration_constant: float = math.sqrt(2.0),
    ) -> None:
        self.player = player
        self.iterations = max(1, iterations)
        self.exploration_constant = exploration_constant

    def choose_move(self, state: GameRules) -> Optional[PlannedMove]:
        # Run the requested number of rollouts
        root = _MCTSNode(copy.deepcopy(state), parent=None, move=None)

        for _ in range(self.iterations):
            node = root
            while node.is_fully_expanded() and not node.is_terminal():
                if not node.children:
                    break
                node = node.best_child(self.exploration_constant)
            if not node.is_terminal() and node.untried_moves:
                move_index = random.randrange(len(node.untried_moves))
                move = node.untried_moves.pop(move_index)
                next_state = copy.deepcopy(node.state)
                player_to_move = next_state.turn.to_move
                result = next_state.apply_player_move(player_to_move, move.origin, move.target)
                if result.legal:
                    child = _MCTSNode(next_state, parent=node, move=move)
                    node.children.append(child)
                    node = child
                else:
                    continue
            reward = self._rollout(node.state)
            while node is not None:
                node.visits += 1
                node.wins += reward
                node = node.parent

        if not root.children:
            return None

        best_child = max(root.children, key=lambda child: child.visits)
        if best_child.move is None:
            return None
        return PlannedMove(origin=best_child.move.origin, target=best_child.move.target)

    def _rollout(self, state: GameRules) -> float:
        # Play random moves until outcome
        simulation = copy.deepcopy(state)
        steps = 0
        max_steps = 200

        while steps < max_steps:
            winner = _winner_for_state(simulation)
            if winner is not None:
                if winner == self.player:
                    return 1.0
                if winner == opponent(self.player):
                    return 0.0
                return 0.5

            moves = _generate_moves(simulation)
            if not moves:
                return 0.5

            move = random.choice(moves)
            player_to_move = simulation.turn.to_move
            result = simulation.apply_player_move(player_to_move, move.origin, move.target)
            if not result.legal:
                return 0.5
            steps += 1

        return 0.5

    @property
    def description(self) -> str:
        return f"MCTS(iterations={self.iterations})"


__all__ = ["MinimaxAgent", "MCTSAgent", "PlannedMove"]


