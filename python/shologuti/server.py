"""Asyncio-powered server for the Shologuti Python port."""

from __future__ import annotations

import argparse
import asyncio
import logging
from typing import Optional

from .lobby import Lobby, PlayerSession
from .protocol import ProtocolError, read_message, write_message


LOG = logging.getLogger("shologuti.server")


class ShologutiServer:
    def __init__(self, host: str = "127.0.0.1", port: int = 11111) -> None:
        self.host = host
        self.port = port
        self.lobby = Lobby()
        self._server: Optional[asyncio.base_events.Server] = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._handle_client, self.host, self.port)
        addr = ", ".join(str(sock.getsockname()) for sock in self._server.sockets)
        LOG.info("Server listening on %s", addr)

    async def serve_forever(self) -> None:
        if self._server is None:
            await self.start()
        assert self._server is not None
        async with self._server:
            await self._server.serve_forever()

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        LOG.info("Connection from %s", peer)

        session: Optional[PlayerSession] = None
        try:
            session = await self._handshake(reader, writer)
            if session is None:
                return
            LOG.info("Client %s identified as %s", peer, session.username)
            await self.lobby.add_session(session)
            await self._session_loop(session)
        except ProtocolError as exc:
            LOG.warning("Protocol error with %s: %s", peer, exc)
        except asyncio.IncompleteReadError:
            LOG.info("Client %s closed connection", peer)
        except Exception:  # pragma: no cover - unexpected failure
            LOG.exception("Unexpected error handling client %s", peer)
        finally:
            if session:
                await self.lobby.remove_session(session)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:  # pragma: no cover
                pass

    async def _handshake(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> Optional[PlayerSession]:
        while True:
            message = await read_message(reader)
            msg_type = message.get("type")

            if msg_type == "hello":
                nickname = message.get("nickname")
                if not isinstance(nickname, str) or not nickname.strip():
                    await write_message(writer, {"type": "error", "code": "invalid_name"})
                    continue

                username = await self.lobby.reserve_username(nickname)
                await write_message(writer, {"type": "welcome", "username": username})
                return PlayerSession(username=username, reader=reader, writer=writer)
            elif msg_type in {"logout", "quit"}:
                await write_message(writer, {"type": "goodbye"})
                return None
            else:
                await write_message(writer, {"type": "error", "code": "handshake_required"})

    async def _session_loop(self, session: PlayerSession) -> None:
        while True:
            message = await read_message(session.reader)
            msg_type = message.get("type")

            if msg_type == "invite":
                target = message.get("target")
                color = message.get("color", "green")
                if not isinstance(target, str):
                    await self.lobby.send_error(session, "invalid_invite")
                    continue
                await self.lobby.start_invite(session, target, color)
            elif msg_type == "invite_response":
                inviter = message.get("from")
                accepted = bool(message.get("accepted"))
                color = message.get("color", "green")
                if not isinstance(inviter, str):
                    await self.lobby.send_error(session, "invalid_invite_response")
                    continue
                await self.lobby.respond_invite(session, inviter, accepted, color)
            elif msg_type == "move":
                await self.lobby.handle_move(session, message)
            elif msg_type == "chat":
                text = message.get("message")
                if isinstance(text, str) and text.strip():
                    await self.lobby.send_chat(session, text)
            elif msg_type == "resign":
                await self.lobby.resign(session)
            elif msg_type == "logout":
                await write_message(session.writer, {"type": "goodbye"})
                break
            else:
                await self.lobby.send_error(session, "unknown_command", {"received": msg_type})


async def amain(args: argparse.Namespace) -> None:
    server = ShologutiServer(host=args.host, port=args.port)
    await server.start()
    await server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Shologuti Python server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=11111)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO))

    try:
        asyncio.run(amain(args))
    except KeyboardInterrupt:
        LOG.info("Server shutting down")


if __name__ == "__main__":
    main()


