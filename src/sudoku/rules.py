from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Set, Tuple

from sudoku.board import Board


Coord = Tuple[int, int]


def _box_start(i: int) -> int:
    return (i // 3) * 3


@dataclass(frozen=True)
class Violation:
    kind: str          # "row" | "col" | "box"
    value: int
    cells: Tuple[Coord, ...]  # all cells involved (2+)


def valid_candidates(board: Board, r: int, c: int) -> Set[int]:
    if not board.is_empty(r, c):
        return set()

    used: Set[int] = set()

    used.update(v for v in board.grid[r] if v != 0)
    used.update(board.grid[rr][c] for rr in range(9) if board.grid[rr][c] != 0)

    br, bc = _box_start(r), _box_start(c)
    for rr in range(br, br + 3):
        for cc in range(bc, bc + 3):
            v = board.grid[rr][cc]
            if v != 0:
                used.add(v)

    return set(range(1, 10)) - used


def is_move_valid(board: Board, r: int, c: int, v: int) -> bool:
    if not (1 <= v <= 9):
        return False
    return v in valid_candidates(board, r, c)


def find_violations(board: Board) -> List[Violation]:
    violations: List[Violation] = []

    # Rows
    for r in range(9):
        seen: Dict[int, List[Coord]] = {}
        for c in range(9):
            v = board.grid[r][c]
            if v == 0:
                continue
            seen.setdefault(v, []).append((r, c))
        for v, cells in seen.items():
            if len(cells) > 1:
                violations.append(Violation("row", v, tuple(cells)))

    # Cols
    for c in range(9):
        seen = {}
        for r in range(9):
            v = board.grid[r][c]
            if v == 0:
                continue
            seen.setdefault(v, []).append((r, c))
        for v, cells in seen.items():
            if len(cells) > 1:
                violations.append(Violation("col", v, tuple(cells)))

    # Boxes
    for br in (0, 3, 6):
        for bc in (0, 3, 6):
            seen = {}
            for r in range(br, br + 3):
                for c in range(bc, bc + 3):
                    v = board.grid[r][c]
                    if v == 0:
                        continue
                    seen.setdefault(v, []).append((r, c))
            for v, cells in seen.items():
                if len(cells) > 1:
                    violations.append(Violation("box", v, tuple(cells)))

    return violations
