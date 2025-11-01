# Sixteen – A Game of Tradition (Python Edition)

Welcome to the Python/Pygame implementation of **Sixteen – A Game of Tradition** (“Shologuti”).
This README is intended to be the single source of truth for the repository: it
captures the vision, architecture, setup, and operational details so you can go
from cloning the repo to shipping releases without hunting for extra context.

---

## 1. Project Overview

- **Goal**: deliver a faithful, modern playable version of the Sixteen board
  game with both human and AI opponents.
- **Stack**: Python 3.11, Pygame for rendering and input, REST-based Firebase
  Authentication for optional sign-in, packaged with Hatchling.
- **Notable capabilities**
  - Accurate 37-node graph representation and capture rules
  - Human vs AI mode with a configurable depth-limited minimax engine.
  - AI vs AI showcase where minimax (Green) battles an MCTS agent (Red).
  - In-game controls for undo, AI tuning, player color swap, and pausing AI
    simulations.
  - Email/password login backed by Firebase’s Identity Toolkit REST API.

The playable client lives in `python/shologuti/client/pygame_app.py`. Distribution
artifacts for `pip` are generated into `python/dist/`.

---

## 2. Repository Layout

```
python/
  pyproject.toml        # Packaging metadata (Hatchling / PEP 621)
  README.md             # Thin README kept for PyPI consumption
  dist/                 # Wheel and sdist built via Hatchling
  shologuti/
    __init__.py         # Package marker
    adjacency.py        # Board graph (neighbors + capture landing nodes)
    ai.py               # Minimax & MCTS agents + evaluation helpers
    auth/
      firebase_auth.py  # Firebase Identity Toolkit REST client
    game/
      board.py          # Board state, move validation, capture chaining
      rules.py          # Turn enforcement, forced captures, match lifecycle
    client/
      pygame_app.py     # UI, menu flow, AI orchestration, main game loop
README.md               # ← You are here (full project guide)
```

---

## 3. Quick Start (Players)

1. **Install Python 3.11+** (Windows/macOS/Linux). On Windows 10+, enable the
   “Add Python to PATH” option during setup.
2. **Clone the repo** and switch to the Python project directory:
   ```bash
   git clone <your-fork-or-origin>
   cd "AI Project\python"
   ```
3. **Create an isolated environment** (recommended):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows PowerShell
   # source .venv/bin/activate  # macOS/Linux
   ```
4. **Install the package** (editable mode for convenience):
   ```bash
   python -m pip install --upgrade pip
   python -m pip install -e .
   ```
5. **Provide your Firebase Web API key** (only needed if you want to log in):
   ```powershell
   setx FIREBASE_WEB_API_KEY "<your-api-key>"
   ```
   Restart the shell so the environment variable is picked up.
6. **Launch the game**:
   ```bash
   python -m shologuti.client.pygame_app
   ```

If the Firebase key is omitted or invalid, the client still runs but login will
be disabled and you’ll stay on the authentication screen.

---

## 4. Gameplay Walkthrough

- **Authentication**: An optional email/password gateway powered by Firebase. A
  valid `FIREBASE_WEB_API_KEY` environment variable enables registration and
  sign-in. Without it, the UI displays an error banner and remains in offline
  mode.
- **Main menu** (once signed in): choose between `Human vs AI`, `AI vs AI`, or
  `Logout`. Escape returns to the menu; Escape again exits the app.
- **Human vs AI**
  - Select which color you control (Green “2” goes first). Green plays bottom,
    Red plays top.
  - Sidebar buttons: start a new game, undo, adjust minimax depth (1/3/5/7),
    toggle your color, return to the menu.
  - The AI respects forced-capture chains and automatically continues them.
- **AI vs AI**
  - Watch two agents duel. Green is a minimax player (depth 1/3/5/7), Red is an
    MCTS agent (50/100/200/300 iterations).
  - Controls: start a fresh match, tweak each AI’s difficulty, pause/resume the
    simulation, or return to the menu.
- **Board interactions**
  - Click your own pieces to reveal legal moves; capture options highlight in
    red, quiet moves in green.
  - Forced capture chains lock selection to the capturing piece until the chain
    ends.
  - Move history (last 40 states) supports single-step undo in Human vs AI
    matches.

---

## 5. Architecture & Key Modules

- `shologuti.adjacency`
  - Stores the canonical directed graph for every node, adjacent neighbor, and
    optional capture landing square as `Edge` dataclasses. Shared by both the
    rule engine and UI for rendering.
- `shologuti.game.board`
  - Maintains board occupancy in a 1-indexed dictionary mirroring the Java
    reference implementation.
  - Generates legal moves, applies them, tracks captures, enforces forced
    continuation, and computes winners.
- `shologuti.game.rules`
  - Wraps `BoardState` with `TurnState` metadata (whose turn, capture lock-in).
  - Owns the player-facing `apply_player_move` API that enforces turn order and
    resets capture state when appropriate.
- `shologuti.ai`
  - **MinimaxAgent**: depth-limited search with alpha-beta pruning. Evaluation
    function combines material, mobility, and a bonus for forced capture chains.
  - **MCTSAgent**: Monte Carlo Tree Search with configurable iteration count and
    exploration constant. Simulation ends on victory or a 200-ply cap.
- `shologuti.client.pygame_app`
  - Initializes fonts, surfaces, and event handlers.
  - Implements the authentication UI, main menu, game screens, input handling,
    AI scheduling, and rendering (board, pieces, highlights, sidebar widgets).
  - Stores undo history snapshots and orchestrates AI turns.
- `shologuti.auth.firebase_auth`
  - Minimal REST wrapper around Firebase Identity Toolkit (`requests` based).
  - Provides `register_user`, `login_user`, and graceful error translation for
    common Firebase error codes.

---

## 6. Configuration & Environment

| Variable                | Purpose                                                | Required |
|-------------------------|--------------------------------------------------------|----------|
| `FIREBASE_WEB_API_KEY`  | Firebase web API key for Identity Toolkit requests.    | Optional |
| `PYGAME_HIDE_SUPPORT_PROMPT` | Set to `1` to silence Pygame’s startup banner. | Optional |

No other secrets or config files are needed. The game does not persist user
data locally beyond in-memory state.

---

## 7. Development Guide

### Installing dev tooling

```bash
cd python
python -m pip install -e .[dev]
```

### Scripts & helpful commands

- Run the game locally: `python -m shologuti.client.pygame_app`
- Format code with Black: `python -m black shologuti`
- Lint with Ruff: `python -m ruff check shologuti`
- (Future) Unit tests: `python -m pytest` *(no tests currently shipped)*

### Conventions

- The board data is defined once in `adjacency.py`; avoid duplicating graph
  knowledge elsewhere.
- Keep UI assets procedural—no external images are required.
- Authentication remains optional; guard network calls and surface readable
  error banners when the key is missing or incorrect.

---

## 8. Packaging & Release

`pyproject.toml` uses Hatchling. To build distributable artifacts:

```bash
cd python
python -m pip install build
python -m build
```

Outputs:

- Wheel → `dist/shologuti-<version>-py3-none-any.whl`
- Source tarball → `dist/shologuti-<version>.tar.gz`

Publish the wheel/SDist to PyPI or a private index as needed.

---

## 9. Troubleshooting

- **App exits immediately with “Pygame is required”** → Ensure `pip install -e .`
  ran successfully and you’re invoking the game from the same environment.
- **Authentication screen never advances** → Check that
  `FIREBASE_WEB_API_KEY` is set and valid. Inspect console/log output for a more
  specific Firebase error message.
- **Graphics glitch or blank window** → Pygame sometimes needs SDL video
  drivers. On Linux, install `libsdl2-dev` (apt) or the equivalent packages.
- **AI turn feels instant** → Increase the minimax depth or MCTS iterations via
  the sidebar buttons to increase thinking time.
- **Performance drops at high depths** → Depth 7 yields heavy branching. Consider
  depth 5 for balance, or optimize the evaluation function before raising it.

---

## 10. Roadmap Ideas

- Add automated tests (unit coverage for move generation and AI heuristics).
- Persist user preferences (depth, color, window size) across sessions.
- Support hot-seat local multiplayer by bypassing AI turns.
- Introduce analytics hooks or match logs to observe AI behaviour.
- Package a standalone executable via PyInstaller or Briefcase for players who
  lack Python.

---


