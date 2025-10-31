"""Tkinter client UI."""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Dict, Optional

from ..adjacency import RAW_ADJACENCY
from ..game.board import PlayerId
from .network import NetworkClient


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

OFFSET_X = 40
OFFSET_Y = 40
NODE_COORDS = {
    idx: (RAW_GUTI_X[idx] + OFFSET_X, RAW_GUTI_Y[idx] + OFFSET_Y)
    for idx in range(1, len(RAW_GUTI_X))
}

CANVAS_WIDTH = 600
CANVAS_HEIGHT = 720
PIECE_RADIUS = 16
BASE_RADIUS = 6

PIECE_COLORS = {
    1: "#d32f2f",  # red
    2: "#2e7d32",  # green
}

COLOR_NAMES = {
    1: "red",
    2: "green",
}


class BoardCanvas(tk.Canvas):
    def __init__(self, master, on_select, **kwargs) -> None:
        super().__init__(
            master,
            width=CANVAS_WIDTH,
            height=CANVAS_HEIGHT,
            background="#f3f3f3",
            highlightthickness=0,
            **kwargs,
        )
        self._on_select = on_select
        self._board: Dict[int, Optional[PlayerId]] = {i: None for i in NODE_COORDS}
        self._selected: Optional[int] = None
        self._last_move: Optional[tuple[int, int]] = None
        self._message_id: Optional[int] = None

        self.bind("<Button-1>", self._handle_click)
        self._draw_static()

    def _draw_static(self) -> None:
        for node, edges in RAW_ADJACENCY.items():
            x1, y1 = NODE_COORDS[node]
            for neighbor, _ in edges:
                if neighbor <= node:
                    continue
                x2, y2 = NODE_COORDS[neighbor]
                self.create_line(x1, y1, x2, y2, fill="#b0bec5", width=2, tags="grid")

        for node, (x, y) in NODE_COORDS.items():
            self.create_oval(
                x - BASE_RADIUS,
                y - BASE_RADIUS,
                x + BASE_RADIUS,
                y + BASE_RADIUS,
                fill="#cfd8dc",
                outline="",
                tags="grid",
            )

    def _handle_click(self, event) -> None:
        node = self._locate_node(event.x, event.y)
        if node is not None:
            self._on_select(node)

    def _locate_node(self, x: float, y: float) -> Optional[int]:
        for node, (nx, ny) in NODE_COORDS.items():
            if (nx - x) ** 2 + (ny - y) ** 2 <= (PIECE_RADIUS + 4) ** 2:
                return node
        return None

    def update_board(self, board: Dict[int, Optional[PlayerId]]) -> None:
        self.delete("piece")
        self._board = board
        for node, occupant in board.items():
            if occupant is None:
                continue
            x, y = NODE_COORDS[node]
            self.create_oval(
                x - PIECE_RADIUS,
                y - PIECE_RADIUS,
                x + PIECE_RADIUS,
                y + PIECE_RADIUS,
                fill=PIECE_COLORS.get(occupant, "#78909c"),
                outline="#263238",
                width=2,
                tags=("piece", f"node-{node}"),
            )
        self._draw_selection()
        self._draw_last_move()

    def set_selection(self, node: Optional[int]) -> None:
        self._selected = node
        self._draw_selection()

    def set_last_move(self, origin: Optional[int], target: Optional[int]) -> None:
        if origin is None or target is None:
            self._last_move = None
        else:
            self._last_move = (origin, target)
        self._draw_last_move()

    def _draw_selection(self) -> None:
        self.delete("selection")
        if self._selected is None:
            return
        x, y = NODE_COORDS[self._selected]
        self.create_oval(
            x - PIECE_RADIUS - 4,
            y - PIECE_RADIUS - 4,
            x + PIECE_RADIUS + 4,
            y + PIECE_RADIUS + 4,
            outline="#ff9800",
            width=3,
            tags="selection",
        )

    def _draw_last_move(self) -> None:
        self.delete("last-move")
        if not self._last_move:
            return
        origin, target = self._last_move
        x1, y1 = NODE_COORDS[origin]
        x2, y2 = NODE_COORDS[target]
        self.create_line(x1, y1, x2, y2, fill="#ff5722", width=3, tags="last-move", arrow=tk.LAST)

    def show_message(self, text: str) -> None:
        self.clear_message()
        self._message_id = self.create_text(
            CANVAS_WIDTH // 2,
            CANVAS_HEIGHT // 2,
            text=text,
            fill="#37474f",
            font=("Segoe UI", 18, "bold"),
            tags="overlay",
        )

    def clear_message(self) -> None:
        if self._message_id is not None:
            self.delete(self._message_id)
            self._message_id = None
        self.delete("overlay")


class ClientApp:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("Shologuti Python")
        self.root.geometry("1024x760")
        self.root.minsize(960, 720)

        self.network = NetworkClient()
        self.username: Optional[str] = None

        self.state = "login"
        self.in_match = False
        self.match_id: Optional[str] = None
        self.you_color: Optional[PlayerId] = None
        self.opponent_name: Optional[str] = None
        self.my_turn = False
        self.must_continue_from: Optional[int] = None
        self.board_state: Dict[int, Optional[PlayerId]] = {i: None for i in NODE_COORDS}

        self._player_entries: list[dict] = []

        self.host_var = tk.StringVar(value="127.0.0.1")
        self.port_var = tk.StringVar(value="11111")
        self.user_var = tk.StringVar()

        self.login_frame: Optional[ttk.Frame] = None
        self.main_frame: Optional[ttk.Frame] = None
        self.board_canvas: Optional[BoardCanvas] = None

        self.status_var = tk.StringVar(value="Not connected")
        self.turn_var = tk.StringVar(value="")
        self.invite_color_var = tk.StringVar(value="green")

        self.players_var = tk.StringVar(value=[])

        self.chat_text: Optional[tk.Text] = None
        self.chat_entry: Optional[ttk.Entry] = None
        self.players_list: Optional[tk.Listbox] = None
        self.selected_origin: Optional[int] = None

        self._build_login_view()

        self.root.after(100, self._poll_messages)
        self.root.protocol("WM_DELETE_WINDOW", self.on_quit)

    def _build_login_view(self) -> None:
        if self.main_frame:
            self.main_frame.destroy()
            self.main_frame = None

        self.login_frame = ttk.Frame(self.root, padding=40)
        self.login_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(self.login_frame, text="Shologuti Python", font=("Segoe UI", 24, "bold")).pack(pady=(0, 30))

        form = ttk.Frame(self.login_frame)
        form.pack(pady=10)

        ttk.Label(form, text="Server host:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(form, textvariable=self.host_var, width=20).grid(row=0, column=1, pady=5, sticky=tk.EW)

        ttk.Label(form, text="Server port:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(form, textvariable=self.port_var, width=20).grid(row=1, column=1, pady=5, sticky=tk.EW)

        ttk.Label(form, text="Username:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(form, textvariable=self.user_var, width=20).grid(row=2, column=1, pady=5, sticky=tk.EW)

        buttons = ttk.Frame(self.login_frame)
        buttons.pack(pady=20)

        ttk.Button(buttons, text="Connect", command=self._on_connect).grid(row=0, column=0, padx=10)

        ttk.Label(self.login_frame, textvariable=self.status_var, foreground="#546e7a").pack(pady=10)

    def _build_main_view(self) -> None:
        if self.login_frame:
            self.login_frame.destroy()
            self.login_frame = None

        self.main_frame = ttk.Frame(self.root, padding=10)
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        left = ttk.Frame(self.main_frame)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.board_canvas = BoardCanvas(left, self._on_board_click)
        self.board_canvas.pack(fill=tk.BOTH, expand=True)
        self.board_canvas.show_message("Invite a player to start a match")

        bottom = ttk.Frame(left)
        bottom.pack(fill=tk.X, pady=5)
        ttk.Label(bottom, textvariable=self.turn_var, font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)
        ttk.Button(bottom, text="Resign", command=self._on_resign).pack(side=tk.RIGHT)

        right = ttk.Frame(self.main_frame, width=280)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(15, 0))

        ttk.Label(right, text=f"Logged in as {self.username}", font=("Segoe UI", 12, "bold")).pack(anchor=tk.W)
        ttk.Button(right, text="Logout", command=self._on_logout).pack(anchor=tk.E, pady=(0, 10))

        ttk.Label(right, text="Online players").pack(anchor=tk.W)
        self.players_list = tk.Listbox(right, listvariable=self.players_var, height=10)
        self.players_list.pack(fill=tk.X, pady=5)

        color_frame = ttk.Frame(right)
        color_frame.pack(pady=5)
        ttk.Label(color_frame, text="Invite color:").grid(row=0, column=0, padx=5)
        ttk.Radiobutton(color_frame, text="Green", value="green", variable=self.invite_color_var).grid(row=0, column=1)
        ttk.Radiobutton(color_frame, text="Red", value="red", variable=self.invite_color_var).grid(row=0, column=2)

        ttk.Button(right, text="Invite Selected", command=self._on_invite_selected).pack(fill=tk.X, pady=5)

        ttk.Label(right, text="Chat").pack(anchor=tk.W, pady=(15, 5))
        self.chat_text = tk.Text(right, height=12, wrap=tk.WORD, state="disabled")
        self.chat_text.pack(fill=tk.BOTH, expand=True)

        chat_entry_frame = ttk.Frame(right)
        chat_entry_frame.pack(fill=tk.X, pady=5)
        self.chat_entry = ttk.Entry(chat_entry_frame)
        self.chat_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.chat_entry.bind("<Return>", lambda event: self._on_send_chat())
        ttk.Button(chat_entry_frame, text="Send", command=self._on_send_chat).pack(side=tk.RIGHT, padx=(5, 0))

        ttk.Label(right, textvariable=self.status_var, wraplength=250, justify=tk.LEFT).pack(anchor=tk.W, pady=5)

    # Event handlers -----------------------------------------------------

    def _ensure_connection(self) -> bool:
        if self.network.is_connected():
            return True
        try:
            host = self.host_var.get().strip()
            port = int(self.port_var.get())
            if not host:
                raise ValueError("Missing host")
            self.network.connect(host, port)
            self.status_var.set(f"Connected to {host}:{port}")
            return True
        except Exception as exc:  # pylint: disable=broad-except
            self.status_var.set(f"Connection failed: {exc}")
            messagebox.showerror("Connection failed", str(exc))
            return False

    def _on_connect(self) -> None:
        if self.username:
            messagebox.showinfo("Already connected", f"You are connected as {self.username}")
            return
        if self.state == "connecting":
            self.status_var.set("Still waiting for server response...")
            return
        if not self._ensure_connection():
            return
        nickname = self.user_var.get().strip()
        if not nickname:
            messagebox.showwarning("Missing info", "Please enter a nickname")
            return
        self.state = "connecting"
        self.network.send({"type": "hello", "nickname": nickname})
        self.status_var.set("Requesting seat...")

    def _on_invite_selected(self) -> None:
        if self.players_list is None:
            return
        if not self.in_match and self.players_list.curselection():
            idx = self.players_list.curselection()[0]
            target = self._player_entries[idx]
            self.network.send({"type": "invite", "target": target["username"], "color": self.invite_color_var.get()})
            self.status_var.set(f"Invite sent to {target['username']}")

    def _on_resign(self) -> None:
        if self.in_match:
            if messagebox.askyesno("Resign", "Are you sure you want to resign?"):
                self.network.send({"type": "resign"})

    def _on_logout(self) -> None:
        if messagebox.askyesno("Logout", "Log out from the server?"):
            try:
                self.network.send({"type": "logout"})
            except RuntimeError:
                pass
            self._reset_state()
            self._build_login_view()

    def _on_send_chat(self) -> None:
        if not self.in_match:
            return
        assert self.chat_entry is not None
        message = self.chat_entry.get().strip()
        if not message:
            return
        self.chat_entry.delete(0, tk.END)
        self._append_chat(f"Me: {message}")
        self.network.send({"type": "chat", "message": message})

    def _on_board_click(self, node: int) -> None:
        if not self.in_match or not self.my_turn:
            return
        if self.must_continue_from is not None and node != self.must_continue_from:
            return

        occupant = self.board_state.get(node)
        if self.selected_origin is None:
            if occupant == self.you_color:
                self.selected_origin = node
                if self.board_canvas:
                    self.board_canvas.set_selection(node)
        else:
            if node == self.selected_origin:
                self.selected_origin = None
                if self.board_canvas:
                    self.board_canvas.set_selection(None)
                return
            if occupant == self.you_color:
                # Switch selection to another of our pieces
                self.selected_origin = node
                if self.board_canvas:
                    self.board_canvas.set_selection(node)
                return

            if self.board_canvas:
                self.board_canvas.set_selection(None)
            origin = self.selected_origin
            self.selected_origin = None
            self.my_turn = False
            self.network.send({"type": "move", "origin": origin, "target": node})
            self.status_var.set("Move submitted")

    def on_quit(self) -> None:
        try:
            self.network.send({"type": "logout"})
        except Exception:
            pass
        self.network.close()
        self.root.destroy()

    # Message processing -------------------------------------------------

    def _poll_messages(self) -> None:
        while True:
            message = self.network.get_message()
            if message is None:
                break
            self._handle_message(message)
        self.root.after(100, self._poll_messages)

    def _handle_message(self, message: dict) -> None:
        msg_type = message.get("type")
        if msg_type == "welcome":
            assigned = message.get("username")
            if not assigned:
                self.status_var.set("Server sent invalid welcome message")
                return
            self.username = assigned
            self.user_var.set(assigned)
            self.status_var.set(f"Connected as {self.username}")
            self.state = "lobby"
            self._build_main_view()
        elif msg_type == "player_list":
            self._update_player_list(message.get("players", []))
        elif msg_type == "invite":
            inviter = message.get("from")
            color = message.get("color", "green")
            if inviter:
                accept = messagebox.askyesno("Game invite", f"{inviter} invites you to play as {('red' if color == 'green' else 'green')}. Accept?")
                self.network.send({
                    "type": "invite_response",
                    "from": inviter,
                    "accepted": accept,
                    "color": color,
                })
        elif msg_type == "invite_declined":
            opponent = message.get("by", "Opponent")
            messagebox.showinfo("Invite declined", f"{opponent} declined your invite")
            self.status_var.set("Invite declined")
        elif msg_type == "match_started":
            self._start_match(message)
        elif msg_type == "move_accepted":
            self._on_move_accepted(message)
        elif msg_type == "opponent_moved":
            self._on_opponent_moved(message)
        elif msg_type == "move_rejected":
            reason = message.get("reason", "Illegal move")
            messagebox.showwarning("Move rejected", reason)
            self.my_turn = True
        elif msg_type == "chat":
            sender = message.get("from", "Opponent")
            text = message.get("message", "")
            if text:
                self._append_chat(f"{sender}: {text}")
        elif msg_type == "match_result":
            outcome = message.get("outcome")
            reason = message.get("reason", "")
            title = "Match result"
            body = f"You {outcome}!\n{reason}" if reason else f"You {outcome}!"
            messagebox.showinfo(title, body)
            self._end_match()
        elif msg_type == "opponent_disconnected":
            messagebox.showinfo("Opponent disconnected", "Opponent left the match")
            self._end_match()
        elif msg_type == "error":
            code = message.get("code")
            self.status_var.set(f"Error: {code}")
            if self.state == "connecting" and code in {"invalid_name", "handshake_required", "name_in_use"}:
                messagebox.showerror("Connection failed", code.replace("_", " "))
                self.network.close()
                self.network = NetworkClient()
                self.state = "login"
        elif msg_type == "connection_closed":
            messagebox.showwarning("Connection", "Server connection closed")
            self._reset_state()
            self.network = NetworkClient()
            self._build_login_view()

    def _start_match(self, message: dict) -> None:
        self.in_match = True
        self.match_id = message.get("match_id")
        self.opponent_name = message.get("opponent")
        color_str = message.get("you_color", "green")
        self.you_color = 2 if color_str == "green" else 1
        self.board_state = self._decode_board(message.get("board", {}))
        if self.board_canvas:
            self.board_canvas.clear_message()
            self.board_canvas.update_board(self.board_state)
        self.my_turn = bool(message.get("your_turn", False))
        self.turn_var.set("Your turn" if self.my_turn else "Opponent's turn")
        self.status_var.set(f"Playing against {self.opponent_name}")
        self.must_continue_from = None
        self._append_chat(f"Match with {self.opponent_name} started")

    def _on_move_accepted(self, message: dict) -> None:
        self.board_state = self._decode_board(message.get("board", {}))
        if self.board_canvas:
            self.board_canvas.update_board(self.board_state)
            self.board_canvas.set_last_move(message.get("origin"), message.get("target"))
        self.my_turn = bool(message.get("your_turn", False))
        if message.get("must_continue"):
            self.must_continue_from = message.get("target")
            self.my_turn = True
            self.status_var.set("Capture again with the same piece")
        else:
            self.must_continue_from = None
        self.turn_var.set("Your turn" if self.my_turn else "Opponent's turn")

    def _on_opponent_moved(self, message: dict) -> None:
        self.board_state = self._decode_board(message.get("board", {}))
        if self.board_canvas:
            self.board_canvas.update_board(self.board_state)
            self.board_canvas.set_last_move(message.get("origin"), message.get("target"))
            self.board_canvas.set_selection(None)
        self.my_turn = bool(message.get("your_turn", False))
        self.must_continue_from = None
        self.turn_var.set("Your turn" if self.my_turn else "Opponent's turn")
        self.status_var.set("Your move" if self.my_turn else "Waiting for opponent")

    def _append_chat(self, text: str) -> None:
        if not self.chat_text:
            return
        self.chat_text.configure(state="normal")
        self.chat_text.insert(tk.END, text + "\n")
        self.chat_text.configure(state="disabled")
        self.chat_text.see(tk.END)

    def _update_player_list(self, players: list[dict]) -> None:
        display = []
        entries: list[dict] = []
        for entry in players:
            if entry.get("username") == self.username:
                continue
            display.append(f"{entry['username']} ({entry['status']})")
            entries.append(entry)
        self._player_entries = entries
        self.players_var.set(display)

    def _end_match(self) -> None:
        self.in_match = False
        self.match_id = None
        self.opponent_name = None
        self.my_turn = False
        self.must_continue_from = None
        self.turn_var.set("Match finished")
        if self.board_canvas:
            self.board_canvas.show_message("Invite a player to start a match")
        self.status_var.set("Match finished")

    def _reset_state(self) -> None:
        self.state = "login"
        self.username = None
        self.in_match = False
        self.match_id = None
        self.opponent_name = None
        self.you_color = None
        self.my_turn = False
        self.must_continue_from = None
        self.board_state = {i: None for i in NODE_COORDS}
        self.status_var.set("Not connected")
        self.players_var.set([])
        self.selected_origin = None

    @staticmethod
    def _decode_board(payload: dict) -> Dict[int, Optional[PlayerId]]:
        board = {i: None for i in NODE_COORDS}
        for key, value in payload.items():
            try:
                board[int(key)] = value
            except (ValueError, TypeError):
                continue
        return board

    def run(self) -> None:
        self.root.mainloop()


