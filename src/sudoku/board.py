from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence


Grid = List[List[int]]  # 9x9, 0 means empty


def _validate_values(grid: Sequence[Sequence[int]]) -> None:
    if len(grid) != 9 or any(len(row) != 9 for row in grid):
        raise ValueError("Grid must be 9x9.")
    for r in range(9):
        for c in range(9):
            v = grid[r][c]
            if not isinstance(v, int) or not (0 <= v <= 9):
                raise ValueError("Grid values must be integers in range 0..9.")


@dataclass(frozen=True)
class Board:
    """
    Sudoku board.
    - Stored as 9x9 ints.
    - 0 means empty.
    """
    grid: Grid

    @staticmethod
    def from_rows(rows: Sequence[Sequence[int]]) -> "Board":
        _validate_values(rows)
        return Board(grid=[list(row) for row in rows])

    def value(self, r: int, c: int) -> int:
        return self.grid[r][c]

    def is_empty(self, r: int, c: int) -> bool:
        return self.value(r, c) == 0

    def with_value(self, r: int, c: int, v: int) -> "Board":
        if not (0 <= v <= 9):
            raise ValueError("Value must be in range 0..9.")
        new_grid = [row[:] for row in self.grid]
        new_grid[r][c] = v
        return Board(new_grid)

    def __str__(self) -> str:
        col_header = "    1 2 3   4 5 6   7 8 9"
        lines = [col_header]
        for r in range(9):
            if r in (3, 6):
                lines.append("  " + "------+-------+------")
            row_label = "ABCDEFGHI"[r]
            row = []
            for c in range(9):
                if c in (3, 6):
                    row.append("|")
                v = self.grid[r][c]
                row.append(str(v) if v != 0 else ".")
            lines.append(f"{row_label}  " + " ".join(row))
        return "\n".join(lines)



def board_from_string(s: str) -> Board:
    """
    Parse a board from a string with 81 chars:
    - digits 1-9 represent values
    - '.' or '0' represent empty
    Whitespace is ignored.
    """
    chars = [ch for ch in s if not ch.isspace()]
    if len(chars) != 81:
        raise ValueError("Expected 81 non-whitespace characters.")
    rows: List[List[int]] = []
    for i in range(0, 81, 9):
        row: List[int] = []
        for ch in chars[i : i + 9]:
            if ch in (".", "0"):
                row.append(0)
            elif ch.isdigit() and ch != "0":
                row.append(int(ch))
            else:
                raise ValueError(f"Invalid character in board string: {ch!r}")
        rows.append(row)
    return Board.from_rows(rows)