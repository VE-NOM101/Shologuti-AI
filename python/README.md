# Python Port Plan

This directory hosts the WIP Python rewrite of the Shologuti 16-piece game.

## Target Feature Set

- Direct nickname-based connections (no registration) with persistent lobby state.
- TCP server that handles the lobby, matchmaking, chat, and game state using a line-oriented JSON protocol.
- Desktop client with graphical board, chat panel, online-player list, and invite flow.
- Same 37-node shologuti board, capture rules, multi-jump logic, and win detection.
- Sound effects and UI assets reused from the Java project where practical.

## Technology Choices

- **Python 3.11+** with `asyncio` for networking.
- **Tkinter** for the desktop UI (standard library, no external deps).
- **Pillow** for image loading; **playsound** (or `winsound` on Windows) for simple audio cues.
- Package layout managed with `pyproject.toml` using Hatchling.

## Project Layout

```
python/
  pyproject.toml          # packaging and dependencies
  README.md               # this document
  shologuti/
    __init__.py
    adjacency.py          # board graph definition and helpers
    protocol.py           # JSON message schema + helpers
    server.py             # asyncio server entry point
    lobby.py              # player registry, invitations, game coordination
    game/
      __init__.py
      board.py            # board state, moves, win conditions
      rules.py            # validation, capture logic
    client/
      __init__.py
      app.py              # Tk application bootstrap
      assets.py           # asset loading utilities
      ui.py               # Tk frames: board canvas, chat, player list
      network.py          # async client connection + message dispatch
```

## Protocol (Draft)

- All messages are newline-delimited JSON objects with field `type` plus payload fields.
- Key message types: `hello`, `welcome`, `player_list`, `invite`, `invite_response`, `match_started`, `move`, `move_accepted`, `opponent_moved`, `chat`, `match_result`, `error`.
- Server assigns session IDs and keeps state in `Lobby` class.
- A `match_id` groups two players. Game state broadcast uses serialized board arrays and turn info.

## Next Steps

1. Implement adjacency helpers mirrored from the Java `Server` class.
2. Build core `BoardState` and move validation with unit tests.
3. Stand up the asyncio server skeleton with login + lobby support.
4. Implement Tkinter client (board canvas, chat, invites, move sending).
5. Connect both sides, iterate on UX, add audio & asset polish.

## Usage

```bash
# optional: create a venv first
python -m pip install -e .

# run the lobby/game server
python -m shologuti.server --host 0.0.0.0 --port 11111 --data-dir ./data

# in a separate terminal, start the desktop client
python -m shologuti.client.app
```

The client and server currently communicate over localhost by default. Choose a
nickname when launching the client; duplicates are automatically de-duplicated
by the server.


