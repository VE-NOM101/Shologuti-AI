"""Lobby and match management for the Shologuti asyncio server."""

from __future__ import annotations

import asyncio
import itertools
from dataclasses import dataclass, field
from typing import Dict, Optional

from .game.rules import GameRules
from .game.board import PlayerId, opponent
from .protocol import write_message


@dataclass
class PlayerSession:
    username: str
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    status: str = "idle"
    match_id: Optional[str] = None
    pending_invite_from: Optional[str] = None

    def is_available(self) -> bool:
        return self.status == "idle"


@dataclass
class Match:
    match_id: str
    rules: GameRules = field(default_factory=GameRules)
    players: Dict[PlayerId, PlayerSession] = field(default_factory=dict)

    def other_player(self, username: str) -> Optional[PlayerSession]:
        for session in self.players.values():
            if session.username != username:
                return session
        return None

    def player_color(self, username: str) -> Optional[PlayerId]:
        for color, session in self.players.items():
            if session.username == username:
                return color
        return None


class Lobby:
    def __init__(self) -> None:
        self.sessions: Dict[str, PlayerSession] = {}
        self.matches: Dict[str, Match] = {}
        self._match_id_seq = itertools.count(1)
        self._lock = asyncio.Lock()
        self._reserved_names: set[str] = set()

    async def reserve_username(self, desired: str) -> str:
        base = desired.strip() or "Player"
        async with self._lock:
            candidate = base
            suffix = 1
            while candidate in self.sessions or candidate in self._reserved_names:
                candidate = f"{base}_{suffix}"
                suffix += 1
            self._reserved_names.add(candidate)
            return candidate

    async def release_username(self, username: str) -> None:
        async with self._lock:
            self._reserved_names.discard(username)

    async def add_session(self, session: PlayerSession) -> None:
        async with self._lock:
            self._reserved_names.discard(session.username)
            self.sessions[session.username] = session
        await self.broadcast_player_list()

    async def remove_session(self, session: PlayerSession) -> None:
        async with self._lock:
            self.sessions.pop(session.username, None)
            self._reserved_names.discard(session.username)
            if session.match_id:
                match = self.matches.get(session.match_id)
                if match:
                    await self._handle_player_disconnect(match, session)
        await self.broadcast_player_list()

    def available_players(self) -> Dict[str, str]:
        return {
            username: sess.status
            for username, sess in self.sessions.items()
            if sess.status == "idle"
        }

    async def broadcast_player_list(self) -> None:
        payload = {
            "type": "player_list",
            "players": [
                {
                    "username": username,
                    "status": session.status,
                }
                for username, session in sorted(self.sessions.items())
            ],
        }
        await asyncio.gather(
            *(
                write_message(session.writer, payload)
                for session in self.sessions.values()
            ),
            return_exceptions=True,
        )

    async def send_error(self, session: PlayerSession, code: str, info: Optional[dict] = None) -> None:
        payload = {"type": "error", "code": code}
        if info:
            payload.update(info)
        await write_message(session.writer, payload)

    async def start_invite(self, inviter: PlayerSession, target_name: str, color: str) -> None:
        target = self.sessions.get(target_name)
        if target is None or target.username == inviter.username:
            await self.send_error(inviter, "target_offline")
            return
        if not target.is_available():
            await self.send_error(inviter, "target_busy")
            return
        inviter.status = "invited"
        target.pending_invite_from = inviter.username
        await write_message(target.writer, {
            "type": "invite",
            "from": inviter.username,
            "color": color,
        })
        await self.broadcast_player_list()

    async def respond_invite(self, target: PlayerSession, inviter_name: str, accepted: bool, color: str) -> None:
        inviter = self.sessions.get(inviter_name)
        target.pending_invite_from = None
        if inviter is None:
            await self.send_error(target, "inviter_offline")
            return

        if not accepted:
            inviter.status = "idle"
            await write_message(inviter.writer, {
                "type": "invite_declined",
                "by": target.username,
            })
            await write_message(target.writer, {"type": "invite_declined_ack"})
            await self.broadcast_player_list()
            return

        if not inviter.is_available():
            await self.send_error(target, "inviter_busy")
            return

        await self._start_match(inviter, target, color)

    async def _start_match(self, inviter: PlayerSession, target: PlayerSession, color: str) -> None:
        match_id = f"match-{next(self._match_id_seq)}"
        match = Match(match_id=match_id)

        color = color.lower()
        if color not in ("red", "green"):
            color = "green"

        inviter_color: PlayerId = 2 if color == "green" else 1
        target_color: PlayerId = opponent(inviter_color)

        match.players[inviter_color] = inviter
        match.players[target_color] = target

        inviter.status = target.status = "playing"
        inviter.match_id = target.match_id = match_id

        self.matches[match_id] = match

        snapshot = match.rules.board.snapshot()
        await asyncio.gather(
            write_message(
                inviter.writer,
                {
                    "type": "match_started",
                    "match_id": match_id,
                    "opponent": target.username,
                    "you_color": color,
                    "your_turn": match.rules.turn.to_move == inviter_color,
                    "board": snapshot,
                },
            ),
            write_message(
                target.writer,
                {
                    "type": "match_started",
                    "match_id": match_id,
                    "opponent": inviter.username,
                    "you_color": "green" if target_color == 2 else "red",
                    "your_turn": match.rules.turn.to_move == target_color,
                    "board": snapshot,
                },
            ),
        )
        await self.broadcast_player_list()

    async def handle_move(self, session: PlayerSession, payload: dict) -> None:
        match = self.matches.get(session.match_id or "")
        if match is None:
            await self.send_error(session, "not_in_match")
            return

        color = match.player_color(session.username)
        if color is None:
            await self.send_error(session, "unknown_color")
            return

        origin = payload.get("origin")
        target = payload.get("target")
        if not isinstance(origin, int) or not isinstance(target, int):
            await self.send_error(session, "invalid_move_payload")
            return

        result = match.rules.apply_player_move(color, origin, target)
        if not result.legal:
            await write_message(session.writer, {
                "type": "move_rejected",
                "reason": result.error,
            })
            return

        other = match.other_player(session.username)
        board_snapshot = match.rules.board.snapshot()

        tasks = [
            write_message(
                session.writer,
                {
                    "type": "move_accepted",
                    "origin": origin,
                    "target": target,
                    "captured": result.captured,
                    "must_continue": result.must_continue,
                    "board": board_snapshot,
                    "your_turn": True if result.must_continue else match.rules.turn.to_move == color,
                },
            )
        ]

        if other is not None:
            other_color = match.player_color(other.username)
            tasks.append(
                write_message(
                    other.writer,
                    {
                        "type": "opponent_moved",
                        "origin": origin,
                        "target": target,
                        "captured": result.captured,
                        "board": board_snapshot,
                        "your_turn": match.rules.turn.to_move == other_color,
                    },
                )
            )

        await asyncio.gather(*tasks)

        if result.winner is not None:
            await self._finish_match(match, winner=result.winner)

    async def resign(self, session: PlayerSession) -> None:
        match = self.matches.get(session.match_id or "")
        if not match:
            return
        winner_color = opponent(match.player_color(session.username) or 1)
        await self._finish_match(match, winner=winner_color, resigned=session.username)

    async def send_chat(self, session: PlayerSession, message: str) -> None:
        match = self.matches.get(session.match_id or "")
        if not match:
            await self.send_error(session, "not_in_match")
            return
        other = match.other_player(session.username)
        if other is None:
            return
        await write_message(other.writer, {
            "type": "chat",
            "from": session.username,
            "message": message,
        })

    async def _finish_match(
        self,
        match: Match,
        *,
        winner: PlayerId,
        resigned: Optional[str] = None,
    ) -> None:
        players = list(match.players.values())
        for session in players:
            session.status = "idle"
            session.match_id = None

        payload_win = {
            "type": "match_result",
            "outcome": "win",
        }
        payload_loss = {
            "type": "match_result",
            "outcome": "loss",
        }

        if resigned:
            payload_loss["reason"] = f"{resigned} resigned"
            payload_win["reason"] = f"{resigned} resigned"

        winners = [match.players[winner]]
        losers = [session for color, session in match.players.items() if color != winner]

        tasks = [write_message(session.writer, payload_win) for session in winners]
        tasks.extend(write_message(session.writer, payload_loss) for session in losers)
        await asyncio.gather(*tasks)

        self.matches.pop(match.match_id, None)
        await self.broadcast_player_list()

    async def _handle_player_disconnect(self, match: Match, session: PlayerSession) -> None:
        other = match.other_player(session.username)
        if other:
            await write_message(other.writer, {
                "type": "opponent_disconnected",
                "opponent": session.username,
            })
            other.status = "idle"
            other.match_id = None
        self.matches.pop(match.match_id, None)


