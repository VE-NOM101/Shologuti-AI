"""Command-line interface for playing Shologuti against an AI opponent."""

from __future__ import annotations

import sys
from typing import Optional

from .ai import MCTSAgent, MinimaxAgent
from .game.board import PlayerId, opponent
from .game.rules import GameRules


def _render_board(state: GameRules) -> None:
    snapshot = state.board.snapshot()
    symbols = {None: ".", 1: "R", 2: "G"}

    print("\nBoard state:")
    for index in range(1, 38):
        symbol = symbols[snapshot[index]]
        print(f"{index:2}:{symbol} ", end="")
        if index % 8 == 0:
            print()
    print("\n")


def _prompt_integer(prompt: str) -> Optional[int]:
    try:
        value = input(prompt)
    except EOFError:
        return None

    value = value.strip()
    if value.lower() in {"q", "quit", "exit"}:
        return None

    try:
        return int(value)
    except ValueError:
        print("Please enter a number or 'q' to quit.")
        return _prompt_integer(prompt)


def _human_turn(state: GameRules, player: PlayerId) -> bool:
    while True:
        _render_board(state)
        print(f"You are playing as {'Green' if player == 2 else 'Red'}.")

        origin = _prompt_integer("Select piece to move (1-37, or q to quit): ")
        if origin is None:
            return False

        target = _prompt_integer("Select destination node (1-37): ")
        if target is None:
            return False

        result = state.apply_player_move(player, origin, target)
        if not result.legal:
            print(f"Illegal move: {result.error}. Try again.")
            continue

        print(f"Moved from {origin} to {target}.")
        if result.captured is not None:
            print(f"Captured opponent piece at {result.captured}.")

        if result.winner is not None:
            print("Congratulations! You win!" if result.winner == player else "You lose.")
            return False

        if result.must_continue:
            print("Capture chain detected - you must continue with the same piece.")
            continue

        return True


def _ai_turn(state: GameRules, agent: MinimaxAgent) -> bool:
    while True:
        planned = agent.choose_move(state)
        if planned is None:
            print("AI has no legal moves. You win!")
            return False

        result = state.apply_player_move(agent.player, planned.origin, planned.target)
        if not result.legal:
            print("AI attempted an illegal move. Ending match.")
            return False

        print(f"AI moves from {planned.origin} to {planned.target}.")
        if result.captured is not None:
            print(f"AI captures at {result.captured}.")

        if result.winner is not None:
            print("AI wins! Better luck next time.")
            return False

        if result.must_continue:
            print("AI continues capture sequence...")
            continue

        return True


def _choose_player() -> PlayerId:
    while True:
        choice = input("Play as Green (G) or Red (R)? Green moves first [G/R]: ").strip().lower()
        if choice in {"g", "green", "2"}:
            return 2
        if choice in {"r", "red", "1"}:
            return 1
        print("Please type 'G' or 'R'.")


def _run_human_vs_ai() -> int:
    state = GameRules()
    human_player = _choose_player()
    ai_player = opponent(human_player)

    depth = 3
    try:
        depth_input = input("Select AI search depth [default 3]: ").strip()
        if depth_input:
            depth = max(1, int(depth_input))
    except ValueError:
        print("Invalid depth entered; using default depth of 3.")

    agent = MinimaxAgent(ai_player, depth=depth)

    print("Game start! Enter 'q' at any prompt to quit.")

    while True:
        if state.turn.to_move == human_player:
            if not _human_turn(state, human_player):
                break
        else:
            if not _ai_turn(state, agent):
                break

    print("Thanks for playing!")
    return 0


def _run_ai_vs_ai() -> int:
    state = GameRules()

    try:
        depth_input = input("Select Minimax search depth for AI 1 (Green) [default 3]: ").strip()
        minimax_depth = max(1, int(depth_input)) if depth_input else 3
    except ValueError:
        print("Invalid depth entered; using default depth of 3.")
        minimax_depth = 3

    try:
        iter_input = input("Select MCTS simulations per move for AI 2 (Red) [default 500]: ").strip()
        mcts_iterations = max(1, int(iter_input)) if iter_input else 500
    except ValueError:
        print("Invalid iteration count; using default of 500.")
        mcts_iterations = 500

    show_board = input("Display board after each move? [y/N]: ").strip().lower() in {"y", "yes"}

    minimax_agent = MinimaxAgent(player=2, depth=minimax_depth)
    mcts_agent = MCTSAgent(player=1, iterations=mcts_iterations)

    agents = {
        2: ("AI 1 (Minimax)", minimax_agent),
        1: ("AI 2 (MCTS)", mcts_agent),
    }

    print("Game start! AI 1 plays Green (first), AI 2 plays Red.")

    turn_counter = 1
    while True:
        player_to_move = state.turn.to_move
        label, agent = agents[player_to_move]

        planned = agent.choose_move(state)
        if planned is None:
            winner = opponent(player_to_move)
            print(f"{label} has no legal moves. {agents[winner][0]} wins by default.")
            break

        result = state.apply_player_move(player_to_move, planned.origin, planned.target)
        if not result.legal:
            winner = opponent(player_to_move)
            print(f"{label} attempted an illegal move ({result.error}). {agents[winner][0]} wins!")
            break

        print(f"Turn {turn_counter}: {label} moves from {planned.origin} to {planned.target}.")
        if result.captured is not None:
            print(f"  Capture at {result.captured}.")
        if show_board:
            _render_board(state)

        if result.winner is not None:
            print(f"{agents[result.winner][0]} wins the match!")
            break

        if result.must_continue:
            print(f"  Capture chain continues for {label}...")
            continue

        turn_counter += 1

    print("AI vs AI match complete.")
    return 0


def main(argv: list[str] | None = None) -> int:
    while True:
        mode = input("Select mode: 1) Human vs AI  2) AI vs AI : ").strip()
        if mode in {"1", "2"}:
            break
        print("Invalid selection. Please choose 1 or 2.")

    if mode == "1":
        return _run_human_vs_ai()

    return _run_ai_vs_ai()


if __name__ == "__main__":  # pragma: no cover - CLI invocation
    sys.exit(main())


