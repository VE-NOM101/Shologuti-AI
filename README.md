# Shologuti Pygame Client

This directory now contains a focused, standalone Pygame version of the
Shologuti (Sixteen Soldiers) board game. The codebase provides:

- Accurate implementation of the 37-node board, capture rules, and win logic.
- A **Human vs AI** mode powered by a minimax agent with alpha-beta pruning.
- An **AI vs AI** mode where the minimax agent (Green) faces an MCTS agent (Red).

## Requirements

- Python 3.11 or newer.
- `pygame` 2.5 or newer (installed automatically when you `pip install -e .`).

## Project Layout

```
python/
  pyproject.toml        # packaging and dependency metadata
  README.md             # this document
  shologuti/
    __init__.py
    adjacency.py        # board graph definition and helpers
    ai.py               # minimax and MCTS agents
    game/
      __init__.py
      board.py          # board state, legal move generation
      rules.py          # capture chaining and turn handling
    client/
      __init__.py
      pygame_app.py     # Pygame user interface (menu + game loop)
```

## Usage

```bash
# optional: create and activate a virtual environment first
python -m pip install -e .

# launch the graphical client
python -m shologuti.client.pygame_app
```

At startup you are greeted with a mode selector. Pick **Human vs AI** to play as
Red or Green, or **AI vs AI** to watch the two agents compete. The sidebar lets
you adjust minimax depth, MCTS simulations, toggle player color, pause/resume
AI battles, and return to the main menu without restarting the program.
