from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from sudoku.board import Board
from sudoku.rules import valid_candidates


Coord = Tuple[int, int]


@dataclass(frozen=True)
class SolveResult:
    solved: bool
    board: Board
    steps: int  # how many assignments were attempted


def _find_next_cell(board: Board) -> Optional[Coord]:
    """
    Choose the next empty cell using MRV (minimum remaining values):
    pick the empty cell with the fewest candidates.
    """
    best: Optional[Coord] = None
    best_count = 10

    for r in range(9):
        for c in range(9):
            if board.is_empty(r, c):
                cand = valid_candidates(board, r, c)
                n = len(cand)
                if n == 0:
                    return (r, c)  # dead-end quickly
                if n < best_count:
                    best_count = n
                    best = (r, c)
                    if best_count == 1:
                        return best
    return best


def solve(board: Board, max_steps: int = 2_000_000) -> SolveResult:
    steps = 0

    def backtrack(b: Board) -> Optional[Board]:
        nonlocal steps
        if steps >= max_steps:
            return None

        nxt = _find_next_cell(b)
        if nxt is None:
            return b  # solved (no empties)

        r, c = nxt
        cand = sorted(valid_candidates(b, r, c))
        if not cand:
            return None

        for v in cand:
            steps += 1
            solved_board = backtrack(b.with_value(r, c, v))
            if solved_board is not None:
                return solved_board

        return None

    solved_board = backtrack(board)
    if solved_board is None:
        return SolveResult(False, board, steps)
    return SolveResult(True, solved_board, steps)
