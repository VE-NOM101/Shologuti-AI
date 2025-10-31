"""JSON-based wire protocol helpers for the Shologuti server/client."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional


Message = Dict[str, Any]
ENCODING = "utf-8"


class ProtocolError(RuntimeError):
    pass


def encode(message: Message) -> bytes:
    """Serialize a message to bytes with a trailing newline."""

    return (json.dumps(message, separators=(",", ":")) + "\n").encode(ENCODING)


def decode(payload: bytes) -> Message:
    """Parse bytes into a Python dictionary."""

    try:
        return json.loads(payload.decode(ENCODING))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("Malformed payload") from exc


async def read_message(reader) -> Message:
    """Read a newline-delimited JSON message from an asyncio StreamReader."""

    line = await reader.readline()
    if not line:
        raise ProtocolError("Connection closed by peer")
    return decode(line.rstrip(b"\r\n"))


async def write_message(writer, message: Message) -> None:
    """Write a JSON message to an asyncio StreamWriter."""

    writer.write(encode(message))
    await writer.drain()


