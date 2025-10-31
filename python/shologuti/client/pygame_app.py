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
from ..auth.firebase_auth import FirebaseAuthClient, FirebaseAuthError, FirebaseUser
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


# ---------------------------------------------------------------------------
# Auth screen layout configuration
# ---------------------------------------------------------------------------

AUTH_PANEL_WIDTH = 520
AUTH_FIELD_WIDTH = 360
AUTH_FIELD_HEIGHT = 56
AUTH_FIELD_SPACING = 40
AUTH_PANEL_TOP_PADDING = 64
AUTH_PANEL_BOTTOM_PADDING = 56
AUTH_TITLE_GAP = 16
AUTH_SUBTITLE_GAP = 28
AUTH_FIELDS_GAP = 44
AUTH_SUBMIT_GAP = 80
AUTH_MESSAGE_GAP = 24
AUTH_MESSAGE_HEIGHT = 52
AUTH_SUBMIT_HEIGHT = 58
AUTH_TOGGLE_HEIGHT = 46
AUTH_TOGGLE_GAP = 16

MENU_BUTTON_ANCHOR_Y = int(WINDOW_HEIGHT * 0.6)


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


@dataclass
class TextInput:
    key: str
    label: str
    rect: pygame.Rect
    placeholder: str
    value: str = ""
    is_password: bool = False
    active: bool = False
    max_length: int = 120

    def draw(self, surface: pygame.Surface, label_font: pygame.font.Font, input_font: pygame.font.Font) -> None:
        label_surface = label_font.render(self.label, True, (55, 71, 79))
        label_rect = label_surface.get_rect()
        label_rect.topleft = (self.rect.x, self.rect.y - label_surface.get_height() - 6)
        surface.blit(label_surface, label_rect)

        fill_color = (250, 250, 250)
        border_color = (25, 118, 210) if self.active else (144, 164, 174)
        pygame.draw.rect(surface, fill_color, self.rect, border_radius=8)
        pygame.draw.rect(surface, border_color, self.rect, width=2, border_radius=8)

        if self.value:
            rendered_value = self.value
            if self.is_password:
                rendered_value = "*" * len(self.value)
            text_color = (38, 50, 56)
        else:
            rendered_value = self.placeholder
            text_color = (120, 144, 156)

        max_width = self.rect.width - 24
        text_to_render = rendered_value
        while input_font.size(text_to_render)[0] > max_width and len(text_to_render) > 1:
            text_to_render = text_to_render[1:]

        text_surface = input_font.render(text_to_render, True, text_color)
        text_rect = text_surface.get_rect()
        text_rect.topleft = (self.rect.x + 12, self.rect.y + (self.rect.height - text_surface.get_height()) // 2)
        surface.blit(text_surface, text_rect)


class AuthMode(Enum):
    LOGIN = "login"
    REGISTER = "register"


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
        self.sidebar_buttons: List[Button] = []
        self.button_lookup: Dict[str, Button] = {}

        self.auth_mode = AuthMode.LOGIN
        self.auth_inputs = self._create_auth_inputs()
        self.active_input_key: Optional[str] = None
        self.auth_error_message: Optional[str] = None
        self.auth_status_message: Optional[str] = None
        self.auth_loading: bool = False
        self.auth_submit_button = Button(
            key="auth_submit",
            label="Sign In",
            rect=pygame.Rect(0, 0, 0, 0),
            base_color=(30, 136, 229),
        )
        self.auth_toggle_button = Button(
            key="auth_toggle",
            label="Need an account? Register",
            rect=pygame.Rect(0, 0, 0, 0),
            base_color=(96, 125, 139),
        )
        self.auth_panel_rect = pygame.Rect(0, 0, AUTH_PANEL_WIDTH, 0)
        self.auth_message_rect = pygame.Rect(0, 0, 0, 0)
        try:
            self.auth_client: Optional[FirebaseAuthClient] = FirebaseAuthClient()
        except FirebaseAuthError as exc:
            self.auth_client = None
            self.auth_error_message = str(exc)
        self.current_user: Optional[FirebaseUser] = None
        self._configure_auth_inputs()
        self.menu_buttons: List[Button] = []
        self._refresh_menu_buttons()

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
        specs: List[Tuple[str, str, Tuple[int, int, int]]] = [
            ("menu_human", "Human vs AI", (56, 142, 60)),
            ("menu_ai", "AI vs AI", (30, 136, 229)),
        ]
        if self.current_user is not None:
            specs.append(("menu_logout", "Logout", (229, 57, 53)))
        total_height = len(specs) * button_height + max(len(specs) - 1, 0) * button_spacing
        start_y = MENU_BUTTON_ANCHOR_Y - total_height // 2
        start_x = WINDOW_WIDTH // 2 - button_width // 2
        buttons: List[Button] = []
        for index, (key, label, color) in enumerate(specs):
            rect = pygame.Rect(
                start_x,
                start_y + index * (button_height + button_spacing),
                button_width,
                button_height,
            )
            buttons.append(Button(key=key, label=label, rect=rect, base_color=color))
        return buttons

    def _refresh_menu_buttons(self) -> None:
        self.menu_buttons = self._build_menu_buttons()

    # ------------------------------------------------------------------
    # Authentication helpers
    # ------------------------------------------------------------------
    def _create_auth_inputs(self) -> Dict[str, TextInput]:
        return {
            "name": TextInput(
                key="name",
                label="Name",
                rect=pygame.Rect(0, 0, 0, 0),
                placeholder="Display name",
                max_length=60,
            ),
            "email": TextInput(
                key="email",
                label="Email",
                rect=pygame.Rect(0, 0, 0, 0),
                placeholder="you@example.com",
                max_length=120,
            ),
            "password": TextInput(
                key="password",
                label="Password",
                rect=pygame.Rect(0, 0, 0, 0),
                placeholder="Enter password",
                is_password=True,
                max_length=80,
            ),
        }

    def _visible_auth_fields(self) -> List[str]:
        if self.auth_mode == AuthMode.LOGIN:
            return ["email", "password"]
        return ["name", "email", "password"]

    def _configure_auth_inputs(self) -> None:
        fields = self._visible_auth_fields()

        for key, field in self.auth_inputs.items():
            if key not in fields:
                field.active = False

        if self.auth_mode == AuthMode.LOGIN:
            self.auth_submit_button.label = "Sign In"
            self.auth_submit_button.base_color = (30, 136, 229)
            self.auth_toggle_button.label = "Create a new account"
        else:
            self.auth_submit_button.label = "Sign Up & Play"
            self.auth_submit_button.base_color = (67, 160, 71)
            self.auth_toggle_button.label = "Back to Sign In"
        self.auth_toggle_button.base_color = (96, 125, 139)

        first_field = fields[0] if fields else None
        self._set_active_input(first_field)
        self._layout_auth_controls()

    def _layout_auth_controls(self) -> None:
        fields = self._visible_auth_fields()

        field_width = AUTH_FIELD_WIDTH
        field_height = AUTH_FIELD_HEIGHT
        spacing = AUTH_FIELD_SPACING
        panel_width = AUTH_PANEL_WIDTH

        title_height = self.font_large.get_height()
        subtitle_height = self.font_small.get_height()
        label_gap = self.font_small.get_height() + 10
        fields_area = len(fields) * field_height + max(len(fields) - 1, 0) * spacing

        content_height = (
            AUTH_PANEL_TOP_PADDING
            + title_height
            + AUTH_TITLE_GAP
            + subtitle_height
            + AUTH_FIELDS_GAP
            + label_gap
            + fields_area
            + AUTH_SUBMIT_GAP
            + AUTH_SUBMIT_HEIGHT
            + AUTH_TOGGLE_GAP
            + AUTH_TOGGLE_HEIGHT
            + AUTH_PANEL_BOTTOM_PADDING
        )

        panel_height = int(content_height)
        panel_left = WINDOW_WIDTH // 2 - panel_width // 2
        panel_top = WINDOW_HEIGHT // 2 - panel_height // 2
        self.auth_panel_rect = pygame.Rect(panel_left, panel_top, panel_width, panel_height)

        start_x = WINDOW_WIDTH // 2 - field_width // 2
        fields_top = (
            panel_top
            + AUTH_PANEL_TOP_PADDING
            + title_height
            + AUTH_TITLE_GAP
            + subtitle_height
            + AUTH_FIELDS_GAP
            + label_gap
        )

        for index, key in enumerate(fields):
            rect = self.auth_inputs[key].rect
            rect.update(
                start_x,
                int(fields_top + index * (field_height + spacing)),
                field_width,
                field_height,
            )

        offscreen_x = -9000
        offscreen_y = -9000
        for key, field in self.auth_inputs.items():
            if key not in fields:
                field.rect.update(offscreen_x, offscreen_y, 0, 0)

        submit_top = fields_top + fields_area + AUTH_SUBMIT_GAP
        self.auth_submit_button.rect.update(
            start_x,
            int(submit_top),
            field_width,
            AUTH_SUBMIT_HEIGHT,
        )

        toggle_top = self.auth_submit_button.rect.bottom + AUTH_TOGGLE_GAP
        self.auth_toggle_button.rect.update(
            start_x,
            int(toggle_top),
            field_width,
            AUTH_TOGGLE_HEIGHT,
        )

        desired_message_top = self.auth_submit_button.rect.top - (AUTH_MESSAGE_GAP + AUTH_MESSAGE_HEIGHT)
        minimum_message_top = fields_top + fields_area + 12
        message_top = max(minimum_message_top, desired_message_top)
        max_message_bottom = self.auth_submit_button.rect.top - 12
        message_height = max(0, int(max_message_bottom - message_top))
        if message_height > AUTH_MESSAGE_HEIGHT:
            message_height = AUTH_MESSAGE_HEIGHT
        self.auth_message_rect = pygame.Rect(
            start_x,
            int(message_top),
            field_width,
            message_height,
        )

        panel_bottom = self.auth_toggle_button.rect.bottom + AUTH_PANEL_BOTTOM_PADDING
        new_height = int(panel_bottom - panel_top)
        if new_height > self.auth_panel_rect.height:
            self.auth_panel_rect.height = new_height

    def _set_active_input(self, key: Optional[str]) -> None:
        self.active_input_key = key
        for field in self.auth_inputs.values():
            field.active = field.key == key

    def _focus_next_input(self, backwards: bool = False) -> None:
        fields = self._visible_auth_fields()
        if not fields:
            self._set_active_input(None)
            return

        if self.active_input_key not in fields or self.active_input_key is None:
            target = fields[-1] if backwards else fields[0]
            self._set_active_input(target)
            return

        current_index = fields.index(self.active_input_key)
        if backwards:
            next_index = (current_index - 1) % len(fields)
        else:
            next_index = (current_index + 1) % len(fields)
        self._set_active_input(fields[next_index])

    def _handle_auth_click(self, pos: Tuple[int, int]) -> None:
        if self.auth_submit_button.contains(pos):
            if self.auth_loading:
                return
            self._submit_auth()
            return
        if self.auth_toggle_button.contains(pos):
            if self.auth_loading:
                return
            self._toggle_auth_mode()
            return

        for key in self._visible_auth_fields():
            field = self.auth_inputs[key]
            if field.rect.collidepoint(pos):
                self._set_active_input(key)
                return

        self._set_active_input(None)

    def _handle_auth_keydown(self, event: pygame.event.Event) -> bool:
        if event.key == pygame.K_TAB:
            self._focus_next_input(backwards=bool(event.mod & pygame.KMOD_SHIFT))
            return True
        if event.key in (pygame.K_UP, pygame.K_DOWN):
            self._focus_next_input(backwards=event.key == pygame.K_UP)
            return True
        if event.key == pygame.K_RETURN:
            self._submit_auth()
            return True
        if event.key == pygame.K_ESCAPE:
            return False

        if self.active_input_key is None:
            return False

        field = self.auth_inputs[self.active_input_key]

        if event.key == pygame.K_BACKSPACE:
            field.value = field.value[:-1]
            return True
        if event.key == pygame.K_DELETE:
            field.value = ""
            return True

        if event.unicode and event.unicode.isprintable():
            if len(field.value) < field.max_length:
                field.value += event.unicode
            return True

        return False

    def _toggle_auth_mode(self) -> None:
        self.auth_mode = AuthMode.REGISTER if self.auth_mode == AuthMode.LOGIN else AuthMode.LOGIN
        if self.auth_mode == AuthMode.LOGIN:
            self.auth_inputs["name"].value = ""
        self.auth_error_message = None
        self.auth_status_message = None
        self.auth_loading = False
        self._configure_auth_inputs()

    def _submit_auth(self) -> None:
        if self.auth_loading:
            return
        if self.auth_client is None:
            self.auth_error_message = "Firebase is not configured. Set FIREBASE_WEB_API_KEY."
            return

        name = self.auth_inputs["name"].value.strip()
        email = self.auth_inputs["email"].value.strip()
        password = self.auth_inputs["password"].value

        self.auth_inputs["name"].value = name
        self.auth_inputs["email"].value = email

        if self.auth_mode == AuthMode.REGISTER and not name:
            self.auth_error_message = "Name is required."
            return
        if not email:
            self.auth_error_message = "Email is required."
            return
        if not password:
            self.auth_error_message = "Password is required."
            return
        if len(password) < 6:
            self.auth_error_message = "Password must be at least 6 characters."
            return

        self.auth_error_message = None
        self.auth_status_message = "Signing in..." if self.auth_mode == AuthMode.LOGIN else "Creating account..."
        self.auth_loading = True

        try:
            if self.auth_mode == AuthMode.LOGIN:
                user = self.auth_client.login_user(email=email, password=password)
            else:
                user = self.auth_client.register_user(name=name, email=email, password=password)
        except FirebaseAuthError as exc:
            self.auth_error_message = str(exc)
            self.auth_status_message = None
            self.auth_loading = False
            self.auth_inputs["password"].value = ""
            return
        except Exception as exc:  # pragma: no cover - defensive
            self.auth_error_message = f"Unexpected error: {exc}"
            self.auth_status_message = None
            self.auth_loading = False
            self.auth_inputs["password"].value = ""
            return

        self.current_user = user
        self.auth_status_message = None
        self.auth_loading = False
        self.auth_inputs["password"].value = ""
        if self.auth_mode == AuthMode.REGISTER:
            self.auth_inputs["name"].value = ""
        self._refresh_menu_buttons()
        self._return_to_menu()

    def logout(self) -> None:
        self._return_to_menu()
        self.current_user = None
        if self.auth_client is not None:
            self.auth_error_message = None
        self.auth_status_message = None
        self.auth_loading = False
        for field in self.auth_inputs.values():
            field.value = ""
        self.auth_mode = AuthMode.LOGIN
        self._configure_auth_inputs()
        self._refresh_menu_buttons()

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
        specs = [
                ("new", "New Game", (56, 142, 60)),
                ("undo", "Undo", (255, 112, 67)),
                ("depth", f"Depth: {self.minimax_depth}", (30, 136, 229)),
                ("switch", "", (142, 36, 170)),
                ("menu", "Back to Menu", (96, 125, 139)),
            ]
        if self.current_user is not None:
            specs.append(("logout", "Logout", (229, 57, 53)))
        self._set_sidebar_buttons(specs)
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
        specs = [
                ("new", "New Battle", (56, 142, 60)),
                ("depth", f"Minimax Depth: {self.ai_vs_ai_depth}", (30, 136, 229)),
                ("iter", f"MCTS Iter: {self.mcts_iterations}", (0, 151, 167)),
                ("pause", "Pause", (230, 81, 0)),
                ("menu", "Back to Menu", (96, 125, 139)),
            ]
        if self.current_user is not None:
            specs.append(("logout", "Logout", (229, 57, 53)))
        self._set_sidebar_buttons(specs)
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
        if self.current_user is None:
            return
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
        if button.key == "logout":
            self.logout()
            return
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
        elif button.key == "menu_logout":
            self.logout()

    def _must_continue(self) -> bool:
        return self.game.turn.pending_capture_from is not None and self.game.turn.to_move == self.human_player

    # ------------------------------------------------------------------
    # AI turn
    # ------------------------------------------------------------------
    def update_ai(self) -> None:
        if self.current_user is None:
            return
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
        if self.current_user is None:
            self._draw_auth_screen()
            return
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

    def _render_wrapped_text(
        self,
        text: str,
        font: pygame.font.Font,
        color: Tuple[int, int, int],
        rect: pygame.Rect,
        align: str = "left",
        line_spacing: int = 4,
        valign: str = "top",
    ) -> int:
        if not text or rect.height <= 0:
            return rect.top

        words = text.split()
        if not words:
            return rect.top

        lines: List[str] = []
        current_line = words[0]
        max_width = rect.width

        for word in words[1:]:
            candidate = f"{current_line} {word}"
            if font.size(candidate)[0] <= max_width:
                current_line = candidate
            else:
                lines.append(current_line)
                current_line = word
        lines.append(current_line)

        line_heights = [font.size(line)[1] for line in lines]
        total_height = sum(line_heights) + line_spacing * (len(lines) - 1)

        if valign == "center":
            y = rect.centery - total_height // 2
        elif valign == "bottom":
            y = rect.bottom - total_height
        else:
            y = rect.top

        y = max(rect.top, y)

        for line in lines:
            rendered = font.render(line, True, color)
            if align == "center":
                line_rect = rendered.get_rect(centerx=rect.centerx, top=y)
            elif align == "right":
                line_rect = rendered.get_rect(right=rect.right, top=y)
            else:
                line_rect = rendered.get_rect(left=rect.left, top=y)

            if line_rect.bottom > rect.bottom:
                break

            self.screen.blit(rendered, line_rect)
            y = line_rect.bottom + line_spacing

        return y

    def _draw_menu(self) -> None:
        self.screen.fill((21, 34, 45))
        title_surface = self.font_large.render("Sixteen - A Game of Tradition", True, (236, 239, 241))
        title_rect = title_surface.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 3))
        self.screen.blit(title_surface, title_rect)

        subtitle_surface = self.font_medium.render("Choose a mode to begin", True, (176, 190, 197))
        subtitle_rect = subtitle_surface.get_rect(center=(WINDOW_WIDTH // 2, title_rect.bottom + 40))
        self.screen.blit(subtitle_surface, subtitle_rect)

        if self.current_user is not None:
            display_name = self.current_user.display_name or self.current_user.email
            user_surface = self.font_small.render(f"Signed in as {display_name}", True, (144, 164, 174))
            user_rect = user_surface.get_rect()
            user_rect.topright = (WINDOW_WIDTH - 50, 50)
            self.screen.blit(user_surface, user_rect)

        mouse_pos = pygame.mouse.get_pos()
        for button in self.menu_buttons:
            button.draw(self.screen, self.font_medium, button.contains(mouse_pos))

        footer_text = self.font_small.render("Press Esc to quit", True, (144, 164, 174))
        footer_rect = footer_text.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT - 60))
        self.screen.blit(footer_text, footer_rect)

    def _draw_auth_screen(self) -> None:
        self.screen.fill((21, 34, 45))

        panel_rect = self.auth_panel_rect
        if panel_rect.height <= 0:
            return

        shadow_surface = pygame.Surface((panel_rect.width, panel_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(shadow_surface, (0, 0, 0, 70), shadow_surface.get_rect(), border_radius=28)
        self.screen.blit(shadow_surface, (panel_rect.x + 6, panel_rect.y + 8))

        pygame.draw.rect(self.screen, (244, 245, 248), panel_rect, border_radius=24)
        pygame.draw.rect(self.screen, (176, 190, 197), panel_rect, width=2, border_radius=24)

        accent_rect = pygame.Rect(panel_rect.x + 28, panel_rect.y + 24, panel_rect.width - 56, 6)
        pygame.draw.rect(self.screen, (30, 136, 229), accent_rect, border_radius=3)

        title_text = "Sign in to play" if self.auth_mode == AuthMode.LOGIN else "Create your account"
        title_surface = self.font_large.render(title_text, True, (38, 50, 56))
        title_rect = title_surface.get_rect(midtop=(panel_rect.centerx, panel_rect.top + AUTH_PANEL_TOP_PADDING))
        self.screen.blit(title_surface, title_rect)

        if self.auth_mode == AuthMode.LOGIN:
            subtitle_text = "Use your email and password to continue"
        else:
            subtitle_text = "Just name, email, and password to get started"
        subtitle_surface = self.font_small.render(subtitle_text, True, (84, 110, 122))
        subtitle_rect = subtitle_surface.get_rect(midtop=(panel_rect.centerx, title_rect.bottom + AUTH_TITLE_GAP))
        self.screen.blit(subtitle_surface, subtitle_rect)

        mouse_pos = pygame.mouse.get_pos()
        for key in self._visible_auth_fields():
            self.auth_inputs[key].draw(self.screen, self.font_small, self.font_medium)

        message_text = None
        message_color = (46, 125, 50)
        message_bg: Optional[Tuple[int, int, int]] = None
        border_color = (205, 220, 227, 220)
        if self.auth_error_message:
            message_text = self.auth_error_message
            message_color = (198, 40, 40)
            message_bg = (255, 235, 238)
            border_color = (239, 154, 154, 220)
        elif self.auth_loading:
            message_text = "Please wait..."
            message_color = (30, 70, 90)
            message_bg = (227, 242, 253)
            border_color = (144, 202, 249, 220)
        elif self.auth_status_message:
            message_text = self.auth_status_message
            message_bg = (232, 245, 233)
            border_color = (165, 214, 167, 220)

        if message_text and self.auth_message_rect.height > 0:
            bubble_rect = self.auth_message_rect.inflate(0, 12)
            bubble_surface = pygame.Surface(bubble_rect.size, pygame.SRCALPHA)
            bubble_color = (*message_bg, 220) if message_bg else (255, 255, 255, 220)
            pygame.draw.rect(bubble_surface, bubble_color, bubble_surface.get_rect(), border_radius=14)
            pygame.draw.rect(bubble_surface, border_color, bubble_surface.get_rect(), width=1, border_radius=14)
            self.screen.blit(bubble_surface, bubble_rect.topleft)

            self._render_wrapped_text(
                message_text,
                self.font_small,
                message_color,
                self.auth_message_rect,
                align="center",
                line_spacing=2,
                valign="center",
            )

        self.auth_submit_button.draw(self.screen, self.font_medium, self.auth_submit_button.contains(mouse_pos))
        self.auth_toggle_button.draw(self.screen, self.font_small, self.auth_toggle_button.contains(mouse_pos))

        footer_y = self.auth_panel_rect.bottom + 36
        footer_text = self.font_small.render("Press Esc to quit", True, (144, 164, 174))
        footer_rect = footer_text.get_rect(center=(WINDOW_WIDTH // 2, footer_y))
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

        button_top = self.sidebar_buttons[0].rect.top if self.sidebar_buttons else WINDOW_HEIGHT - SIDEBAR_PADDING

        if self.message:
            available_height = button_top - cursor_y - 72
            if available_height > 40:
                message_rect = pygame.Rect(text_x, cursor_y, max_text_width, available_height)
                cursor_y = self._render_wrapped_text(
                    self.message,
                    self.font_small,
                    (94, 53, 177),
                    message_rect,
                    line_spacing=4,
                )
                cursor_y += 12
            else:
                cursor_y = button_top - 60
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
        counts_top = max(cursor_y, SIDEBAR_PADDING + 16)
        counts_available = button_top - counts_top - 20
        if counts_available > 0:
            counts_rect = pygame.Rect(text_x, counts_top, max_text_width, counts_available)
            self._render_wrapped_text(counts_text, self.font_small, TEXT_COLOR, counts_rect, line_spacing=4)

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
            if self.current_user is None:
                self._layout_auth_controls()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    continue
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    if self.current_user is None or self.mode is None:
                        running = False
                    else:
                        self._return_to_menu()
                    continue

                if self.current_user is None:
                    if event.type == pygame.KEYDOWN:
                        self._handle_auth_keydown(event)
                    elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                        self._handle_auth_click(event.pos)
                    continue

                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
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


