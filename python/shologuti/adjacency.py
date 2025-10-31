"""Board adjacency definitions for the Shologuti game graph.

The original Java implementation enumerates, for each node, the immediate
neighbor and (optionally) the landing spot when capturing over that neighbor.
We mirror the data here so the rest of the Python code can share a single
source of truth for move validation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Tuple


@dataclass(frozen=True)
class Edge:
    """Represents a directed neighbor relationship on the board.

    Attributes
    ----------
    neighbor:
        The adjacent node index that can be reached with a simple move.
    landing:
        The landing node index when jumping over ``neighbor`` to capture a
        piece. ``None`` indicates that no capture move exists for that
        neighbor.
    """

    neighbor: int
    landing: int | None


# fmt: off
RAW_ADJACENCY: Dict[int, List[Tuple[int, int | None]]] = {
    1:  [(2, 3), (4, 9)],
    2:  [(1, None), (5, 9), (3, None)],
    3:  [(2, 1), (6, 9)],
    4:  [(1, None), (5, 6), (9, 15)],
    5:  [(2, None), (4, None), (6, None), (9, 14)],
    6:  [(3, None), (9, 13), (5, 4)],
    7:  [(8, 9), (13, 19), (12, 17)],
    8:  [(7, None), (13, 18), (9, 10)],
    9:  [(4, 1), (5, 2), (6, 3), (8, 7), (13, 17), (14, 19), (15, 21), (10, 11)],
    10: [(9, 8), (15, 20), (11, None)],
    11: [(10, 9), (15, 19), (16, 21)],
    12: [(7, None), (13, 14), (17, 22)],
    13: [(7, None), (8, None), (9, 6), (14, 15), (19, 25), (18, 23), (17, None), (12, None)],
    14: [(9, 5), (15, 16), (19, 24), (13, 12)],
    15: [(9, 4), (10, None), (11, None), (16, None), (21, None), (20, 25), (19, 23), (14, 13)],
    16: [(11, None), (15, 14), (21, 26)],
    17: [(12, 7), (13, 9), (18, 19), (23, 29), (22, 27)],
    18: [(13, 8), (19, 20), (23, 28), (17, None)],
    19: [(13, 7), (14, 9), (15, 11), (20, 21), (25, 31), (24, 29), (23, 27), (18, 17)],
    20: [(15, 10), (21, None), (25, 30), (19, 18)],
    21: [(16, 11), (15, 9), (20, 19), (25, 29), (26, 31)],
    22: [(17, 12), (23, 24), (27, None)],
    23: [(17, None), (18, 13), (19, 15), (24, 25), (29, 34), (28, None), (27, None), (22, None)],
    24: [(19, 14), (25, 26), (29, 33), (23, 22)],
    25: [(19, 13), (20, 15), (21, None), (26, None), (31, None), (30, None), (29, 32), (24, 23)],
    26: [(21, 16), (25, 24), (31, None)],
    27: [(22, 17), (23, 19), (28, 29)],
    28: [(23, 18), (29, 30), (27, None)],
    29: [(28, 27), (23, 17), (24, 19), (25, 21), (30, 31), (32, 35), (33, 36), (34, 37)],
    30: [(29, 28), (25, 20), (31, None)],
    31: [(30, 29), (25, 19), (26, 21)],
    32: [(29, 25), (33, 34), (35, None)],
    33: [(32, None), (29, 24), (34, None), (36, None)],
    34: [(29, 23), (33, 32), (37, None)],
    35: [(32, 29), (36, 37)],
    36: [(35, None), (33, 29), (37, None)],
    37: [(36, 35), (34, 29)],
}
# fmt: on


def neighbors(node: int) -> List[Edge]:
    """Return all outgoing edges from ``node`` as :class:`Edge` objects."""

    try:
        return [Edge(neighbor=nb, landing=landing) for nb, landing in RAW_ADJACENCY[node]]
    except KeyError as exc:  # pragma: no cover - defensive guard
        raise ValueError(f"Unknown node index: {node}") from exc


def all_edges() -> Iterator[tuple[int, Edge]]:
    """Iterate over every ``(node, edge)`` pair on the board."""

    for node, edges in RAW_ADJACENCY.items():
        for nb, landing in edges:
            yield node, Edge(neighbor=nb, landing=landing)


