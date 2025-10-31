"""Command-line interface for playing Shologuti against an AI opponent."""

from __future__ import annotations

import sys
from typing import Optional

from .ai import MinimaxAgent
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


def main(argv: list[str] | None = None) -> int:
    mode = input("Select mode: 1) Human vs AI  2) AI vs AI : ").strip()
    if mode != "1":
        print("AI vs AI mode is not implemented yet. Please restart and choose option 1.")
        return 0

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


if __name__ == "__main__":  # pragma: no cover - CLI invocation
    sys.exit(main())


