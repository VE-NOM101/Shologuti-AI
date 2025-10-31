"""Networking helper that bridges asyncio with Tkinter."""

from __future__ import annotations

import asyncio
import queue
import threading
from typing import Optional

from ..protocol import ProtocolError, read_message, write_message


class NetworkClient:
    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._incoming: "queue.Queue[dict]" = queue.Queue()
        self._connected = threading.Event()
        self._closed = threading.Event()

    def start(self) -> None:
        if not self._thread.is_alive():
            self._thread.start()

    def connect(self, host: str, port: int) -> None:
        self.start()
        fut = asyncio.run_coroutine_threadsafe(self._connect(host, port), self._loop)
        fut.result()

    async def _connect(self, host: str, port: int) -> None:
        self._reader, self._writer = await asyncio.open_connection(host, port)
        self._connected.set()
        asyncio.create_task(self._read_loop())

    async def _read_loop(self) -> None:
        if self._reader is None:
            return
        try:
            while not self._closed.is_set():
                message = await read_message(self._reader)
                self._incoming.put(message)
        except (asyncio.IncompleteReadError, ProtocolError):
            self._incoming.put({"type": "connection_closed"})
        finally:
            self._connected.clear()

    def send(self, message: dict) -> None:
        if self._writer is None:
            raise RuntimeError("client not connected")
        asyncio.run_coroutine_threadsafe(write_message(self._writer, message), self._loop)

    def get_message(self, block: bool = False, timeout: Optional[float] = None) -> Optional[dict]:
        try:
            return self._incoming.get(block, timeout)
        except queue.Empty:
            return None

    def is_connected(self) -> bool:
        return self._connected.is_set()

    def close(self) -> None:
        self._closed.set()
        if self._writer:
            asyncio.run_coroutine_threadsafe(self._close_writer(), self._loop)

    async def _close_writer(self) -> None:
        assert self._writer is not None
        self._writer.close()
        try:
            await self._writer.wait_closed()
        except Exception:
            pass


