"""Pygame front-end for Sixteen - A Game of Tradition."""

from __future__ import annotations

import copy
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple

try:
    import pygame
except ImportError as exc:  # pragma: no cover - handled at runtime
    raise SystemExit(
        "Pygame is required for the graphical client. Install it with 'pip install pygame'."
    ) from exc

from ..adjacency import RAW_ADJACENCY
from ..ai import MCTSAgent, MinimaxAgent
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

MIN_RAW_X = min(RAW_GUTI_X[1:])
MAX_RAW_X = max(RAW_GUTI_X[1:])
MIN_RAW_Y = min(RAW_GUTI_Y[1:])
MAX_RAW_Y = max(RAW_GUTI_Y[1:])

SIDEBAR_PADDING = 40
SIDEBAR_WIDTH = 220
SIDEBAR_BG = (236, 239, 241)
BOARD_PADDING = 30
BOARD_TOP = 40

OFFSET_X = SIDEBAR_PADDING + SIDEBAR_WIDTH + BOARD_PADDING - MIN_RAW_X
OFFSET_Y = BOARD_TOP + BOARD_PADDING - MIN_RAW_Y

NODE_COORDS: Dict[int, Tuple[int, int]] = {
    idx: (RAW_GUTI_X[idx] + OFFSET_X, RAW_GUTI_Y[idx] + OFFSET_Y)
    for idx in range(1, len(RAW_GUTI_X))
}

MIN_X = min(coord[0] for coord in NODE_COORDS.values())
MAX_X = max(coord[0] for coord in NODE_COORDS.values())
MIN_Y = min(coord[1] for coord in NODE_COORDS.values())
MAX_Y = max(coord[1] for coord in NODE_COORDS.values())

BOARD_RECT = pygame.Rect(
    MIN_X - BOARD_PADDING,
    MIN_Y - BOARD_PADDING,
    (MAX_X - MIN_X) + 2 * BOARD_PADDING,
    (MAX_Y - MIN_Y) + 2 * BOARD_PADDING,
)


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
    key: str
    label: str
    rect: pygame.Rect
    base_color: Tuple[int, int, int] = (33, 150, 243)

    def draw(self, surface: pygame.Surface, font: pygame.font.Font, hovered: bool) -> None:
        highlight = tuple(min(c + 40, 255) for c in self.base_color)
        color = highlight if hovered else self.base_color
        pygame.draw.rect(surface, color, self.rect, border_radius=6)
        pygame.draw.rect(surface, (13, 71, 161), self.rect, width=2, border_radius=6)
        text_surf = font.render(self.label, True, (255, 255, 255))
        surface.blit(text_surf, text_surf.get_rect(center=self.rect.center))

    def contains(self, pos: Tuple[int, int]) -> bool:
        return self.rect.collidepoint(pos)


class GameMode(Enum):
    HUMAN_VS_AI = "human_vs_ai"
    AI_VS_AI = "ai_vs_ai"


class SixteenPygameApp:
    def __init__(self) -> None:
        pygame.init()
        pygame.display.set_caption("Sixteen - A Game of Tradition")
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        self.clock = pygame.time.Clock()

        self.font_small = pygame.font.Font(None, 24)
        self.font_medium = pygame.font.Font(None, 32)
        self.font_large = pygame.font.Font(None, 48)
        self.menu_buttons = self._build_menu_buttons()
        self.sidebar_buttons: List[Button] = []
        self.button_lookup: Dict[str, Button] = {}

        self.mode: Optional[GameMode] = None

        self.game = GameRules()
        self.human_player: PlayerId = 2  # Green traditionally starts
        self.ai_player: PlayerId = opponent(self.human_player)
        self.minimax_depth: int = 3
        self.agent = MinimaxAgent(self.ai_player, depth=self.minimax_depth)

        self.ai_vs_ai_depth: int = 3
        self.mcts_iterations: int = 500
        self.ai_vs_ai_pause: bool = False
        self.ai_move_delay_ms: int = 800
        self.last_ai_tick: int = pygame.time.get_ticks()
        self.ai_agent_map: Dict[PlayerId, Tuple[str, MinimaxAgent | MCTSAgent]] = {}

        self.selected_origin: Optional[int] = None
        self.highlight_moves: List[MoveOption] = []
        self.message: Optional[str] = None

        self.history: List[GameRules] = [copy.deepcopy(self.game)]
        self.pending_ai: bool = False

    def _build_menu_buttons(self) -> List[Button]:
        button_width = 320
        button_height = 70
        button_spacing = 20
        total_height = 2 * button_height + button_spacing
        start_y = WINDOW_HEIGHT // 2 - total_height // 2
        start_x = WINDOW_WIDTH // 2 - button_width // 2

        return [
            Button(
                key="menu_human",
                label="Human vs AI",
                rect=pygame.Rect(start_x, start_y, button_width, button_height),
                base_color=(56, 142, 60),
            ),
            Button(
                key="menu_ai",
                label="AI vs AI",
                rect=pygame.Rect(start_x, start_y + button_height + button_spacing, button_width, button_height),
                base_color=(30, 136, 229),
            ),
        ]

    def _set_sidebar_buttons(self, specs: List[Tuple[str, str, Tuple[int, int, int]]]) -> None:
        button_height = 46
        button_spacing = 12
        if not specs:
            self.sidebar_buttons = []
            self.button_lookup = {}
            return

        total_height = len(specs) * button_height + (len(specs) - 1) * button_spacing
        start_y = WINDOW_HEIGHT - SIDEBAR_PADDING - total_height

        self.sidebar_buttons = []
        self.button_lookup = {}

        for index, (key, label, color) in enumerate(specs):
            rect = pygame.Rect(
                SIDEBAR_PADDING,
                start_y + index * (button_height + button_spacing),
                SIDEBAR_WIDTH,
                button_height,
            )
            button = Button(key=key, label=label, rect=rect, base_color=color)
            self.sidebar_buttons.append(button)
            self.button_lookup[key] = button

    # ------------------------------------------------------------------
    # Game flow helpers
    # ------------------------------------------------------------------
    def start_human_mode(self) -> None:
        self.mode = GameMode.HUMAN_VS_AI
        pygame.display.set_caption("Sixteen - A Game of Tradition: Human vs AI")
        self._set_sidebar_buttons(
            [
                ("new", "New Game", (56, 142, 60)),
                ("undo", "Undo", (255, 112, 67)),
                ("depth", f"Depth: {self.minimax_depth}", (30, 136, 229)),
                ("switch", "", (142, 36, 170)),
                ("menu", "Back to Menu", (96, 125, 139)),
            ]
        )
        self.ai_player = opponent(self.human_player)
        self.agent = MinimaxAgent(self.ai_player, depth=self.minimax_depth)
        self._refresh_human_sidebar_labels()
        self._reset_human_game()

    def _reset_human_game(self) -> None:
        self.game = GameRules()
        if self.human_player == 1:
            self.game.turn.to_move = 1
        self.ai_player = opponent(self.human_player)
        self.agent = MinimaxAgent(self.ai_player, depth=self.minimax_depth)
        self.selected_origin = None
        self.highlight_moves = []
        self.history = [copy.deepcopy(self.game)]
        self.pending_ai = self.game.turn.to_move == self.ai_player
        self.message = "AI to move first..." if self.pending_ai else "Your turn."

    def _refresh_human_sidebar_labels(self) -> None:
        if "depth" in self.button_lookup:
            self.button_lookup["depth"].label = f"Depth: {self.minimax_depth}"
        if "switch" in self.button_lookup:
            color_desc = "Green (2)" if self.human_player == 2 else "Red (1)"
            self.button_lookup["switch"].label = f"Play as: {color_desc}"

    def start_ai_vs_ai_mode(self) -> None:
        self.mode = GameMode.AI_VS_AI
        pygame.display.set_caption("Sixteen - A Game of Tradition: AI vs AI")
        self._set_sidebar_buttons(
            [
                ("new", "New Battle", (56, 142, 60)),
                ("depth", f"Minimax Depth: {self.ai_vs_ai_depth}", (30, 136, 229)),
                ("iter", f"MCTS Iter: {self.mcts_iterations}", (0, 151, 167)),
                ("pause", "Pause", (230, 81, 0)),
                ("menu", "Back to Menu", (96, 125, 139)),
            ]
        )
        self._reset_ai_battle()

    def _reset_ai_battle(self) -> None:
        self.game = GameRules()
        self.selected_origin = None
        self.highlight_moves = []
        self.history = [copy.deepcopy(self.game)]
        self.pending_ai = False
        self.ai_vs_ai_pause = False
        self.last_ai_tick = pygame.time.get_ticks()
        self.ai_agent_map = {
            2: ("AI 1 (Minimax)", MinimaxAgent(player=2, depth=self.ai_vs_ai_depth)),
            1: ("AI 2 (MCTS)", MCTSAgent(player=1, iterations=self.mcts_iterations)),
        }
        self.message = "AI battle started."
        self._refresh_ai_vs_ai_sidebar_labels()

    def _refresh_ai_vs_ai_sidebar_labels(self) -> None:
        if "depth" in self.button_lookup:
            self.button_lookup["depth"].label = f"Minimax Depth: {self.ai_vs_ai_depth}"
        if "iter" in self.button_lookup:
            self.button_lookup["iter"].label = f"MCTS Iter: {self.mcts_iterations}"
        if "pause" in self.button_lookup:
            self.button_lookup["pause"].label = "Resume" if self.ai_vs_ai_pause else "Pause"

    def toggle_player_color(self) -> None:
        if self.mode != GameMode.HUMAN_VS_AI:
            return
        self.human_player = opponent(self.human_player)
        self.ai_player = opponent(self.human_player)
        self._refresh_human_sidebar_labels()
        self._reset_human_game()
        color_desc = "Green (2)" if self.human_player == 2 else "Red (1)"
        self.message = f"You now play as {color_desc}."

    def set_ai_depth(self, depth: int) -> None:
        self.minimax_depth = depth
        if self.mode == GameMode.HUMAN_VS_AI:
            self.agent = MinimaxAgent(self.ai_player, depth=depth)
            self._refresh_human_sidebar_labels()
            self.message = f"AI depth set to {depth}."
        else:
            self._refresh_human_sidebar_labels()

    def undo(self) -> None:
        if self.mode != GameMode.HUMAN_VS_AI:
            return
        if len(self.history) <= 1:
            return
        self.history.pop()
        restored = copy.deepcopy(self.history[-1])
        self.game = restored
        self.message = "Undid last move."
        self.selected_origin = None
        self.highlight_moves = []
        self.pending_ai = False

    def _cycle_human_depth(self) -> None:
        options = [1, 3, 5]
        try:
            idx = options.index(self.minimax_depth)
        except ValueError:
            idx = 0
        next_depth = options[(idx + 1) % len(options)]
        self.set_ai_depth(next_depth)

    def _cycle_ai_depth(self) -> None:
        options = [1, 3, 5, 7]
        try:
            idx = options.index(self.ai_vs_ai_depth)
        except ValueError:
            idx = 0
        self.ai_vs_ai_depth = options[(idx + 1) % len(options)]
        if 2 in self.ai_agent_map:
            self.ai_agent_map[2] = ("AI 1 (Minimax)", MinimaxAgent(player=2, depth=self.ai_vs_ai_depth))
        self._refresh_ai_vs_ai_sidebar_labels()
        self.message = f"Minimax depth now {self.ai_vs_ai_depth}."

    def _cycle_mcts_iterations(self) -> None:
        options = [200, 500, 800, 1200]
        try:
            idx = options.index(self.mcts_iterations)
        except ValueError:
            idx = 0
        self.mcts_iterations = options[(idx + 1) % len(options)]
        if 1 in self.ai_agent_map:
            self.ai_agent_map[1] = ("AI 2 (MCTS)", MCTSAgent(player=1, iterations=self.mcts_iterations))
        self._refresh_ai_vs_ai_sidebar_labels()
        self.message = f"MCTS iterations now {self.mcts_iterations}."

    def _toggle_ai_pause(self) -> None:
        self.ai_vs_ai_pause = not self.ai_vs_ai_pause
        self._refresh_ai_vs_ai_sidebar_labels()
        self.message = "Simulation paused." if self.ai_vs_ai_pause else "Simulation resumed."
        self.last_ai_tick = pygame.time.get_ticks()

    def _return_to_menu(self) -> None:
        self.mode = None
        pygame.display.set_caption("Sixteen - A Game of Tradition")
        self._set_sidebar_buttons([])
        self.selected_origin = None
        self.highlight_moves = []
        self.message = None
        self.pending_ai = False
        self.ai_vs_ai_pause = False

    def _push_history(self) -> None:
        self.history.append(copy.deepcopy(self.game))
        if len(self.history) > 40:
            self.history = self.history[-40:]

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------
    def handle_click(self, pos: Tuple[int, int]) -> None:
        if self.mode is None:
            for button in self.menu_buttons:
                if button.contains(pos):
                    self._handle_menu_button(button)
                    return
            return

        for button in self.sidebar_buttons:
            if button.contains(pos):
                self._handle_button(button)
                return

        if self.mode == GameMode.AI_VS_AI:
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
            self.highlight_moves = self.game.board.legal_moves(
                clicked, self.human_player, require_capture=self._must_continue()
            )
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
            self.pending_ai = False
            return

        if result.must_continue:
            self.selected_origin = move.target
            self.highlight_moves = self.game.board.capture_moves(move.target, self.human_player)
            self.message = "Continue capture with the same piece."
        else:
            self.selected_origin = None
            self.highlight_moves = []
            self.pending_ai = True

    def _handle_button(self, button: Button) -> None:
        if button.key == "menu":
            self._return_to_menu()
            return

        if self.mode == GameMode.HUMAN_VS_AI:
            if button.key == "new":
                self._reset_human_game()
            elif button.key == "undo":
                self.undo()
            elif button.key == "depth":
                self._cycle_human_depth()
            elif button.key == "switch":
                self.toggle_player_color()
            return

        if self.mode == GameMode.AI_VS_AI:
            if button.key == "new":
                self._reset_ai_battle()
            elif button.key == "depth":
                self._cycle_ai_depth()
            elif button.key == "iter":
                self._cycle_mcts_iterations()
            elif button.key == "pause":
                self._toggle_ai_pause()

    def _handle_menu_button(self, button: Button) -> None:
        if button.key == "menu_human":
            self.start_human_mode()
        elif button.key == "menu_ai":
            self.start_ai_vs_ai_mode()

    def _must_continue(self) -> bool:
        return self.game.turn.pending_capture_from is not None and self.game.turn.to_move == self.human_player

    # ------------------------------------------------------------------
    # AI turn
    # ------------------------------------------------------------------
    def update_ai(self) -> None:
        if self.mode == GameMode.HUMAN_VS_AI:
            self._update_human_ai()
        elif self.mode == GameMode.AI_VS_AI:
            self._update_ai_battle()

    def _update_human_ai(self) -> None:
        if not self.pending_ai:
            return
        if self.game.turn.to_move != self.ai_player:
            self.pending_ai = False
            return

        if not self.message or "thinking" not in self.message.lower():
            self.message = "AI thinking..."

        planned = self.agent.choose_move(self.game)
        if planned is None:
            self.message = "AI has no legal moves. You win!"
            self.pending_ai = False
            return

        self._push_history()
        result = self.game.apply_player_move(self.ai_player, planned.origin, planned.target)
        if not result.legal:
            self.message = "AI attempted an illegal move."
            self.pending_ai = False
            return

        self.selected_origin = None
        self.highlight_moves = []
        self.message = self._format_move_message("AI", planned.origin, planned.target, result.captured)

        if result.winner is not None:
            self.message = "AI wins!" if result.winner == self.ai_player else "You win!"
            self.pending_ai = False
            return

        if result.must_continue:
            self.message += " | AI continues capture..."
            self.pending_ai = True
        else:
            self.pending_ai = False
            if self.game.turn.to_move == self.human_player:
                self.message += " | Your turn."

    def _update_ai_battle(self) -> None:
        if self.ai_vs_ai_pause:
            return

        now = pygame.time.get_ticks()
        delay = self.ai_move_delay_ms
        if self.game.turn.pending_capture_from is not None:
            delay = max(200, self.ai_move_delay_ms // 2)
        if now - self.last_ai_tick < delay:
            return

        player = self.game.turn.to_move
        agent_info = self.ai_agent_map.get(player)
        if agent_info is None:
            return

        label, agent = agent_info
        planned = agent.choose_move(self.game)
        if planned is None:
            winner = opponent(player)
            winner_label = self.ai_agent_map.get(winner, (f"Player {winner}", None))[0]
            self.message = f"{label} has no legal moves. {winner_label} wins!"
            self.ai_vs_ai_pause = True
            return

        self._push_history()
        result = self.game.apply_player_move(player, planned.origin, planned.target)
        if not result.legal:
            winner = opponent(player)
            winner_label = self.ai_agent_map.get(winner, (f"Player {winner}", None))[0]
            self.message = f"{label} attempted illegal move ({result.error}). {winner_label} wins!"
            self.ai_vs_ai_pause = True
            return

        self.selected_origin = None
        self.highlight_moves = []
        self.message = self._format_move_message(label, planned.origin, planned.target, result.captured)

        if result.winner is not None:
            winner_label = self.ai_agent_map.get(result.winner, (f"Player {result.winner}", None))[0]
            self.message = f"{winner_label} wins the match!"
            self.ai_vs_ai_pause = True
            return

        if result.must_continue:
            self.message += " | Continuing capture..."
            self.last_ai_tick = pygame.time.get_ticks() - self.ai_move_delay_ms // 2
        else:
            self.last_ai_tick = pygame.time.get_ticks()

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def draw(self) -> None:
        if self.mode is None:
            self._draw_menu()
            return

        self.screen.fill((250, 250, 250))

        sidebar_rect = pygame.Rect(
            SIDEBAR_PADDING,
            SIDEBAR_PADDING,
            SIDEBAR_WIDTH,
            WINDOW_HEIGHT - 2 * SIDEBAR_PADDING,
        )
        pygame.draw.rect(self.screen, SIDEBAR_BG, sidebar_rect, border_radius=12)
        pygame.draw.rect(self.screen, (189, 189, 189), sidebar_rect, width=2, border_radius=12)

        pygame.draw.rect(self.screen, BOARD_BG, BOARD_RECT, border_radius=12)
        pygame.draw.rect(self.screen, (189, 189, 189), BOARD_RECT, width=2, border_radius=12)

        self._draw_edges()
        self._draw_nodes()
        self._draw_pieces()
        self._draw_highlights()
        self._draw_ui()

    def _draw_menu(self) -> None:
        self.screen.fill((21, 34, 45))
        title_surface = self.font_large.render("Sixteen - A Game of Tradition", True, (236, 239, 241))
        title_rect = title_surface.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 3))
        self.screen.blit(title_surface, title_rect)

        subtitle_surface = self.font_medium.render("Choose a mode to begin", True, (176, 190, 197))
        subtitle_rect = subtitle_surface.get_rect(center=(WINDOW_WIDTH // 2, title_rect.bottom + 40))
        self.screen.blit(subtitle_surface, subtitle_rect)

        mouse_pos = pygame.mouse.get_pos()
        for button in self.menu_buttons:
            button.draw(self.screen, self.font_medium, button.contains(mouse_pos))

        footer_text = self.font_small.render("Press Esc to quit", True, (144, 164, 174))
        footer_rect = footer_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 60))
        self.screen.blit(footer_text, footer_rect)

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

        text_x = SIDEBAR_PADDING + 16
        cursor_y = SIDEBAR_PADDING + 16
        max_text_width = SIDEBAR_WIDTH - 32

        def draw_wrapped(text: str, font: pygame.font.Font, color: Tuple[int, int, int], top: int) -> int:
            if not text:
                return top
            words = text.split()
            if not words:
                return top

            lines: List[str] = []
            current = words[0]
            for word in words[1:]:
                extended = f"{current} {word}"
                if font.size(extended)[0] <= max_text_width:
                    current = extended
                else:
                    lines.append(current)
                    current = word
            lines.append(current)

            y_pos = top
            for line_text in lines:
                surface = font.render(line_text, True, color)
                self.screen.blit(surface, (text_x, y_pos))
                y_pos += surface.get_height() + 4
            return y_pos

        if self.mode == GameMode.HUMAN_VS_AI:
            status_lines = [
                "Mode: Human vs AI",
                f"Playing as {'Green (2)' if self.human_player == 2 else 'Red (1)'}",
                f"Turn: {'You' if self.game.turn.to_move == self.human_player else 'AI'}",
                f"AI depth: {self.minimax_depth}",
            ]
        else:
            current_label = self.ai_agent_map.get(
                self.game.turn.to_move, (f"Player {self.game.turn.to_move}", None)
            )[0]
            status_lines = [
                "Mode: AI vs AI",
                f"Turn: {current_label}",
                f"Minimax depth: {self.ai_vs_ai_depth}",
                f"MCTS iterations: {self.mcts_iterations}",
                f"Paused: {'Yes' if self.ai_vs_ai_pause else 'No'}",
            ]

        for line in status_lines:
            cursor_y = draw_wrapped(line, self.font_medium, TEXT_COLOR, cursor_y)
            cursor_y += 4

        cursor_y += 8

        if self.message:
            cursor_y = draw_wrapped(self.message, self.font_small, (94, 53, 177), cursor_y)
            cursor_y += 8
        else:
            cursor_y += 12

        if self.mode == GameMode.HUMAN_VS_AI:
            remaining_you = self.game.remaining(self.human_player)
            remaining_ai = self.game.remaining(self.ai_player)
            counts_text = f"Pieces - You: {remaining_you}  |  AI: {remaining_ai}"
        else:
            counts_text = (
                f"Pieces - Green (AI 1): {self.game.remaining(2)}  |  Red (AI 2): {self.game.remaining(1)}"
            )
        draw_wrapped(counts_text, self.font_small, TEXT_COLOR, cursor_y)

        for button in self.sidebar_buttons:
            button.draw(self.screen, self.font_small, button.contains(mouse_pos))

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
                elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if self.mode is None:
                        running = False
                    else:
                        self._return_to_menu()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    self.handle_click(event.pos)

            self.update_ai()
            self.draw()
            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()
        sys.exit(0)


def main() -> int:
    app = SixteenPygameApp()
    app.run()
    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution
    main()


