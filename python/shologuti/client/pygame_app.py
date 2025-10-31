"""Pygame front-end for the Shologuti 16-piece game."""

from __future__ import annotations

import copy
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

try:
    import pygame
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise SystemExit(
        "Pygame is required for the graphical client. Install it with 'pip install pygame'."
    ) from exc

from ..adjacency import RAW_ADJACENCY
from ..ai import MinimaxAgent
from ..game.board import MoveOption, PlayerId, opponent
from ..game.rules import GameRules


# ---------------------------------------------------------------------------
# Board layout (shares the same coordinates as the Tkinter UI)
# ---------------------------------------------------------------------------

RAW_GUTI_X = [
    0,
    127,
    276,
    420,
    186,
    277,
    366,
    69,
    169,
    277,
    390,
    494,
    68,
    171,
    279,
    387,
    495,
    66,
    170,
    278,
    389,
    493,
    66,
    168,
    278,
    391,
    494,
    67,
    170,
    276,
    388,
    495,
    187,
    277,
    359,
    125,
    276,
    420,
]

RAW_GUTI_Y = [
    0,
    66,
    65,
    65,
    111,
    109,
    109,
    179,
    179,
    178,
    177,
    178,
    262,
    262,
    260,
    261,
    261,
    346,
    345,
    346,
    345,
    345,
    432,
    430,
    431,
    430,
    432,
    521,
    517,
    518,
    518,
    519,
    586,
    586,
    586,
    635,
    635,
    634,
]

OFFSET_X = 60
OFFSET_Y = 80

NODE_COORDS: Dict[int, Tuple[int, int]] = {
    idx: (RAW_GUTI_X[idx] + OFFSET_X, RAW_GUTI_Y[idx] + OFFSET_Y)
    for idx in range(1, len(RAW_GUTI_X))
}


# ---------------------------------------------------------------------------
# Rendering configuration
# ---------------------------------------------------------------------------

WINDOW_WIDTH = 1020
WINDOW_HEIGHT = 760
FPS = 30

BOARD_BG = (243, 243, 243)
LINE_COLOR = (120, 144, 156)
PIECE_COLORS = {1: (211, 47, 47), 2: (46, 125, 50)}
PIECE_OUTLINE = (38, 50, 56)
EMPTY_NODE_FILL = (207, 216, 220)
SELECTION_COLOR = (255, 152, 0)
HIGHLIGHT_MOVE = (129, 199, 132, 140)
HIGHLIGHT_CAPTURE = (239, 83, 80, 160)
TEXT_COLOR = (33, 33, 33)

PIECE_RADIUS = 18
BASE_RADIUS = 6


@dataclass
class Button:
    label: str
    rect: pygame.Rect

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, hovered: bool) -> None:
        base_color = (76, 175, 80) if "Depth" in self.label else (33, 150, 243)
        color = tuple(min(c + 40, 255) for c in base_color) if hovered else base_color
        pygame.draw.rect(surface, color, self.rect, border_radius=6)
        pygame.draw.rect(surface, (13, 71, 161), self.rect, width=2, border_radius=6)
        text_surf = font.render(self.label, True, (255, 255, 255))
        surface.blit(text_surf, text_surf.get_rect(center=self.rect.center))

    def contains(self, pos: Tuple[int, int]) -> bool:
        return self.rect.collidepoint(pos)


class ShologutiPygameApp:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Shologuti - Human vs AI (Pygame)")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()

        self.font_small = pygame.font.Font(None, 24)
        self.font_medium = pygame.font.Font(None, 32)
        self.font_large = pygame.font.Font(None, 48)

        self.buttons = [
            Button("New Game", pygame.Rect(40, WINDOW_HEIGHT - 70, 140, 45)),
            Button("Undo", pygame.Rect(200, WINDOW_HEIGHT - 70, 100, 45)),
            Button("Depth: 3", pygame.Rect(320, WINDOW_HEIGHT - 70, 140, 45)),
            Button("Switch Color", pygame.Rect(480, WINDOW_HEIGHT - 70, 160, 45)),
        ]

        self.game = GameRules()
        self.human_player: PlayerId = 2  # Green traditionally starts
        self.ai_player: PlayerId = opponent(self.human_player)
        self.agent = MinimaxAgent(self.ai_player, depth=3)

        self.selected_origin: Optional[int] = None
        self.highlight_moves: List[MoveOption] = []
        self.message: Optional[str] = None

        self.history: List[GameRules] = [copy.deepcopy(self.game)]
        self.pending_ai: bool = False

    # ------------------------------------------------------------------
    # Game flow helpers
    # ------------------------------------------------------------------
    def reset(self) -> None:
        self.game = GameRules()
        if self.human_player == 1:
            self.game.turn.to_move = 1
        self.agent = MinimaxAgent(self.ai_player, depth=self.agent.depth)
        self.selected_origin = None
        self.highlight_moves = []
        self.message = None
        self.history = [copy.deepcopy(self.game)]
        self.pending_ai = False

    def toggle_player_color(self) -> None:
        self.human_player = opponent(self.human_player)
        self.ai_player = opponent(self.human_player)
        self.reset()

    def set_ai_depth(self, depth: int) -> None:
        self.agent = MinimaxAgent(self.ai_player, depth=depth)
        self.buttons[2].label = f"Depth: {depth}"

    def undo(self) -> None:
        if len(self.history) <= 1:
            return
        # Pop current state
        self.history.pop()
        restored = copy.deepcopy(self.history[-1])
        self.game = restored
        self.message = "Undid last move"
        self.selected_origin = None
        self.highlight_moves = []
        self.pending_ai = False

    def _push_history(self) -> None:
        self.history.append(copy.deepcopy(self.game))
        if len(self.history) > 40:
            self.history = self.history[-40:]

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------
    def handle_click(self, pos: Tuple[int, int]) -> None:
        for button in self.buttons:
            if button.contains(pos):
                self._handle_button(button)
                return

        if self.game.turn.to_move != self.human_player:
            return

        clicked = self._node_at(pos)
        if clicked is None:
            self.selected_origin = None
            self.highlight_moves = []
            return

        occupant = self.game.board.occupant(clicked)
        if occupant == self.human_player:
            self.selected_origin = clicked
            self.highlight_moves = self.game.board.legal_moves(clicked, self.human_player, require_capture=self._must_continue())
            return

        if self.selected_origin is None:
            return

        move = next((m for m in self.highlight_moves if m.target == clicked), None)
        if move is None:
            return

        self._push_history()
        result = self.game.apply_player_move(self.human_player, self.selected_origin, move.target)
        if not result.legal:
            self.message = f"Illegal move: {result.error}"
            return

        self.message = self._format_move_message("You", self.selected_origin, move.target, result.captured)

        if result.winner is not None:
            self.message = "You win!" if result.winner == self.human_player else "AI wins!"
            self.selected_origin = None
            self.highlight_moves = []
            return

        if result.must_continue:
            self.selected_origin = move.target
            self.highlight_moves = self.game.board.capture_moves(move.target, self.human_player)
            self.message = "Continue capture with the same piece"
        else:
            self.selected_origin = None
            self.highlight_moves = []
            self.pending_ai = True

    def _handle_button(self, button: Button) -> None:
        if button.label.startswith("New"):
            self.reset()
        elif button.label.startswith("Undo"):
            self.undo()
        elif button.label.startswith("Depth"):
            next_depth = {1: 3, 3: 5, 5: 1}[self.agent.depth if self.agent.depth in {1, 3, 5} else 3]
            self.set_ai_depth(next_depth)
        elif button.label.startswith("Switch"):
            self.toggle_player_color()

    def _must_continue(self) -> bool:
        return self.game.turn.pending_capture_from is not None and self.game.turn.to_move == self.human_player

    # ------------------------------------------------------------------
    # AI turn
    # ------------------------------------------------------------------
    def update_ai(self) -> None:
        if self.pending_ai and self.game.turn.to_move == self.ai_player:
            planned = self.agent.choose_move(self.game)
            if planned is None:
                self.message = "AI has no moves. You win!"
                self.pending_ai = False
                return

            self._push_history()
            result = self.game.apply_player_move(self.ai_player, planned.origin, planned.target)
            if not result.legal:
                self.message = "AI attempted illegal move"
                self.pending_ai = False
                return

            self.message = self._format_move_message("AI", planned.origin, planned.target, result.captured)

            if result.winner is not None:
                self.message = "AI wins!" if result.winner == self.ai_player else "You win!"
                self.pending_ai = False
                self.selected_origin = None
                self.highlight_moves = []
                return

            if result.must_continue:
                # Let AI continue immediately.
                self.pending_ai = True
            else:
                self.pending_ai = False

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def draw(self) -> None:
        self.screen.fill((250, 250, 250))
        board_rect = pygame.Rect(280, 20, 700, 700)
        pygame.draw.rect(self.screen, BOARD_BG, board_rect, border_radius=12)

        self._draw_edges()
        self._draw_nodes()
        self._draw_pieces()
        self._draw_highlights()
        self._draw_ui()

    def _draw_edges(self) -> None:
        for node, edges in RAW_ADJACENCY.items():
            x1, y1 = NODE_COORDS[node]
            for neighbor in edges:
                nb = neighbor[0]
                if nb <= node:
                    continue
                x2, y2 = NODE_COORDS[nb]
                pygame.draw.line(self.screen, LINE_COLOR, (x1, y1), (x2, y2), 3)

    def _draw_nodes(self) -> None:
        for node, (x, y) in NODE_COORDS.items():
            pygame.draw.circle(self.screen, EMPTY_NODE_FILL, (x, y), BASE_RADIUS)
            pygame.draw.circle(self.screen, (84, 110, 122), (x, y), BASE_RADIUS, 1)

    def _draw_pieces(self) -> None:
        snapshot = self.game.board.snapshot()
        for node, occupant in snapshot.items():
            if occupant is None:
                continue
            x, y = NODE_COORDS[node]
            color = PIECE_COLORS.get(occupant, (120, 120, 120))
            pygame.draw.circle(self.screen, color, (x, y), PIECE_RADIUS)
            pygame.draw.circle(self.screen, PIECE_OUTLINE, (x, y), PIECE_RADIUS, 3)

        if self.selected_origin is not None:
            x, y = NODE_COORDS[self.selected_origin]
            pygame.draw.circle(self.screen, SELECTION_COLOR, (x, y), PIECE_RADIUS + 5, width=3)

    def _draw_highlights(self) -> None:
        for option in self.highlight_moves:
            target = option.target
            x, y = NODE_COORDS[target]
            surf = pygame.Surface((PIECE_RADIUS * 3, PIECE_RADIUS * 3), pygame.SRCALPHA)
            color = HIGHLIGHT_CAPTURE if option.captured is not None else HIGHLIGHT_MOVE
            pygame.draw.circle(
                surf,
                color,
                (PIECE_RADIUS * 1.5, PIECE_RADIUS * 1.5),
                PIECE_RADIUS - 2,
            )
            self.screen.blit(surf, (x - PIECE_RADIUS * 1.5, y - PIECE_RADIUS * 1.5))

    def _draw_ui(self) -> None:
        mouse_pos = pygame.mouse.get_pos()
        for button in self.buttons:
            button.draw(self.screen, self.font_small, button.contains(mouse_pos))

        status_lines = [
            f"You are playing as {'Green (2)' if self.human_player == 2 else 'Red (1)'}",
            f"Turn: {'You' if self.game.turn.to_move == self.human_player else 'AI'}",
            f"Depth: {self.agent.depth} (toggle button to change)",
        ]

        for idx, line in enumerate(status_lines):
            text = self.font_medium.render(line, True, TEXT_COLOR)
            self.screen.blit(text, (40, 40 + idx * 32))

        if self.message:
            msg = self.font_small.render(self.message, True, (94, 53, 177))
            self.screen.blit(msg, (40, 140))

        remaining_you = self.game.remaining(self.human_player)
        remaining_ai = self.game.remaining(self.ai_player)
        counts = self.font_small.render(
            f"Pieces — You: {remaining_you}  |  AI: {remaining_ai}", True, TEXT_COLOR
        )
        self.screen.blit(counts, (40, 180))

    # ------------------------------------------------------------------
    # Utility helpers
    # ------------------------------------------------------------------
    def _node_at(self, pos: Tuple[int, int]) -> Optional[int]:
        mx, my = pos
        for node, (x, y) in NODE_COORDS.items():
            if (mx - x) ** 2 + (my - y) ** 2 <= (PIECE_RADIUS + 6) ** 2:
                return node
        return None

    @staticmethod
    def _format_move_message(actor: str, origin: int, target: int, captured: Optional[int]) -> str:
        if captured is None:
            return f"{actor} moved {origin} → {target}"
        return f"{actor} captured at {captured} ( {origin} → {target} )"

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------
    def run(self) -> None:
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.handle_click(event.pos)

            self.update_ai()
            self.draw()
            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()
        sys.exit(0)


def main() -> int:
    app = ShologutiPygameApp()
    app.run()
    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()


