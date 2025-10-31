"# Shologuti-16-pieces-Game-by-Java" 
The game is a slightly modified version of below game. It is very popular game in rural areas of Bangladesh. Children loves to play this game in Bangladesh.

https://en.wikipedia.org/wiki/Sixteen_Soldiers

A simple multiplayer checker game build using Java. Here in this game, two player can play against one another and also can chat while playing. 

## Python Rewrite

A cross-platform Python port now lives under `python/`. It provides an
asyncio-based server and a Tkinter desktop client with the original shologuti
rules, matchmaking, chat, and move validation.

Quick start:

```bash
cd python
python -m pip install -e .
python -m shologuti.server
python -m shologuti.client.app
```

Choose any display name when the client starts; the server will handle
duplicates automatically.

See `python/README.md` for more details.