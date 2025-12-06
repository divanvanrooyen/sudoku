from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Set, Tuple

from sudoku.board import Board, board_from_string
from sudoku.rules import find_violations, is_move_valid, valid_candidates
from sudoku.solver import solve

import json
from pathlib import Path


Coord = Tuple[int, int]


@dataclass(frozen=True)
class GameState:
    puzzle: Board
    current: Board
    notes: dict[Coord, set[int]]


def _givens_mask(puzzle: Board) -> Set[Coord]:
    givens: Set[Coord] = set()
    for r in range(9):
        for c in range(9):
            if puzzle.value(r, c) != 0:
                givens.add((r, c))
    return givens

def _print_candidates_map(board: Board) -> None:
    def cell_text(r: int, c: int) -> str:
        v = board.value(r, c)
        if v != 0:
            return f"   {v}   ".center(9)  # show given/filled value
        cand = "".join(str(x) for x in sorted(valid_candidates(board, r, c)))
        return cand.center(9)

    for r in range(9):
        if r in (3, 6):
            print("-" * (9 * 9 + 8 + 2 * 2))  # rough separator width
        row = []
        for c in range(9):
            row.append(cell_text(r, c))
        # add box separators
        print(
            " ".join(row[0:3]) + "  |  " +
            " ".join(row[3:6]) + "  |  " +
            " ".join(row[6:9])
        )

def _best_hint_cell(board: Board) -> Optional[tuple[int, int, list[int]]]:
    best = None
    best_len = 10
    for r in range(9):
        for c in range(9):
            if board.is_empty(r, c):
                cand = sorted(valid_candidates(board, r, c))
                if not cand:
                    return (r, c, cand)
                if len(cand) < best_len:
                    best_len = len(cand)
                    best = (r, c, cand)
                    if best_len == 1:
                        return best
    return best

def _board_to_rows(board: Board) -> list[list[int]]:
    return [row[:] for row in board.grid]

def _rows_to_board(rows: list[list[int]]) -> Board:
    return Board.from_rows(rows)

def _save_game(path: Path, state: GameState) -> None:
    data = {
        "givens": _givens_fingerprint(state.puzzle),
        "puzzle": _board_to_rows(state.puzzle),
        "current": _board_to_rows(state.current),
        "notes": {
            f"{r},{c}": sorted(list(digs))
            for (r, c), digs in state.notes.items()
        },
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")

def _load_game(path: Path) -> GameState:
    data = json.loads(path.read_text(encoding="utf-8"))
    puzzle = _rows_to_board(data["puzzle"])
    current = _rows_to_board(data["current"])

    expected = data.get("givens")
    if expected is not None and expected != _givens_fingerprint(puzzle):
        raise ValueError("Save file puzzle givens do not match (corrupt or wrong file).")

    notes_raw = data.get("notes", {})
    notes: dict[Coord, set[int]] = {}
    for k, v in notes_raw.items():
        r_s, c_s = k.split(",", 1)
        r, c = int(r_s), int(c_s)
        notes[(r, c)] = set(int(x) for x in v)

    return GameState(puzzle=puzzle, current=current, notes=notes)

def _givens_fingerprint(puzzle: Board) -> str:
    # 81-char string, digits for givens, '.' for empty
    out = []
    for r in range(9):
        for c in range(9):
            v = puzzle.value(r, c)
            out.append(str(v) if v != 0 else ".")
    return "".join(out)

def _print_board_with_notes(board: Board, notes: dict[Coord, set[int]]) -> None:
    # prints a compact 2-line-per-row view: values row + notes row
    print("    1 2 3   4 5 6   7 8 9")
    for r in range(9):
        if r in (3, 6):
            print("  " + "------+-------+------")
        row_label = "ABCDEFGHI"[r]

        # value row
        parts = []
        for c in range(9):
            if c in (3, 6):
                parts.append("|")
            v = board.value(r, c)
            parts.append(str(v) if v != 0 else ".")
        print(f"{row_label}  " + " ".join(parts))

        # notes row (only for empties with notes)
        note_parts = []
        for c in range(9):
            if c in (3, 6):
                note_parts.append("|")
            if board.value(r, c) != 0:
                note_parts.append(" ")
            else:
                digs = notes.get((r, c), set())
                s = "".join(str(d) for d in sorted(digs))
                note_parts.append(s if s else " ")
        print("   " + " ".join(note_parts))


def _is_complete(board: Board) -> bool:
    return all(board.value(r, c) != 0 for r in range(9) for c in range(9))


def _parse_move(cmd: str) -> Optional[tuple[int, int, int]]:
    """
    Supported inputs:
      - set r c v      (1-based r,c)
      - r c v          (1-based r,c)
      - A1 v           (A-I, 1-9)
      - set A1 v
    v can be 1-9, 0, or '.' (clear)
    """
    parts = cmd.strip().split()
    if not parts:
        return None

    if parts[0].lower() == "set":
        parts = parts[1:]

    # A1 v  (or set A1 v)
    if len(parts) == 2 and len(parts[0]) == 2:
        rc = parts[0].upper()
        row_ch, col_ch = rc[0], rc[1]
        if row_ch in "ABCDEFGHI" and col_ch in "123456789":
            r = "ABCDEFGHI".index(row_ch)
            c = int(col_ch) - 1
            v_raw = parts[1]
            if v_raw == ".":
                v = 0
            else:
                try:
                    v = int(v_raw)
                except ValueError:
                    return None
            if 0 <= v <= 9:
                return r, c, v
        # fall through if not valid

    # r c v (or set r c v)
    if len(parts) != 3:
        return None

    try:
        r_user = int(parts[0])
        c_user = int(parts[1])
    except ValueError:
        return None

    v_raw = parts[2]
    if v_raw == ".":
        v = 0
    else:
        try:
            v = int(v_raw)
        except ValueError:
            return None

    if not (1 <= r_user <= 9 and 1 <= c_user <= 9 and 0 <= v <= 9):
        return None

    return r_user - 1, c_user - 1, v


def run_cli_game(puzzle: Board) -> None:
    givens = _givens_mask(puzzle)
    state = GameState(puzzle=puzzle, current=puzzle, notes={})


    help_text = """
Commands:
  show                 - print board
  cand r c             - show candidates for cell (1-9, 1-9)
  set r c v            - set value v (1-9) at (r,c). Use v=0 to clear.
  check                - show any rule violations
  help                 - show this help
  quit                 - exit
  cands                - show candidates for every empty cell
  hint                 - show a good cell to try next (fewest candidates)
  hint!                - auto-fill the best forced move (only if 1 candidate)
  save <file>          - save game to a json file
  load <file>          - load game from a json file
  new <puzzle>         - start a new puzzle (81 chars of digits/. or 0/.)
  status               - show whether puzzle is complete/valid
  solve                - print the solved board (spoiler)
  note <cell> <digits> - toggle notes for a cell, e.g. note A3 124
  notes                - show all notes
  show notes           - show board plus your notes
Notes:
  - Rows/cols are 1..9 (top-left is r=1 c=1)
  - You cannot change original givens.
  - You can also type: A1 9 (rows A-I, cols 1-9)
"""

    print("Welcome to Sudoku CLI 🧩")
    print(help_text)
    print(state.current)

    while True:
        cmd = input("\n> ").strip()
        if not cmd:
            continue

        low = cmd.lower()

        if low in ("q", "quit", "exit"):
            print("Bye 👋")
            return

        if low in ("h", "help"):
            print(help_text)
            continue

        if low.startswith("new "):
            _, puzzle_str = cmd.split(maxsplit=1)
            try:
                puzzle = board_from_string(puzzle_str)
            except Exception as e:
                print(f"Invalid puzzle: {e}")
                continue

            state = GameState(puzzle=puzzle, current=puzzle, notes={})
            givens = _givens_mask(state.puzzle)
            print("Started new puzzle:")
            print(state.current)
            continue

        if low == "status":
            if find_violations(state.current):
                print("Current board has violations ❌ (try: check)")
                continue
            if _is_complete(state.current):
                print("Filled with no violations ✅ (looks solved!)")
            else:
                print("No violations ✅ but not complete yet.")
            continue

        if low == "solve":
            res = solve(state.puzzle)
            if not res.solved:
                print("This puzzle could not be solved by the solver.")
                continue
            print("Solution (spoiler):")
            print(res.board)
            continue

        if low == "show":
            print(state.current)
            continue

        if low == "show notes":
            _print_board_with_notes(state.current, state.notes)
            continue

        if low == "cands":
            _print_candidates_map(state.current)
            continue

        if low == "hint":
            h = _best_hint_cell(state.current)
            if h is None:
                print("No empty cells left.")
                continue
            r, c, cand = h
            # display 1-based coords to user
            if not cand:
                print(f"Dead-end at (r={r+1}, c={c+1}) — no valid candidates!")
            else:
                print(f"Try (r={r+1}, c={c+1}) candidates: {cand}")
            continue
        
        if low in ("hint!", "hint-fill"):
            h = _best_hint_cell(state.current)
            if h is None:
                print("No empty cells left.")
                continue
            r, c, cand = h
            if (r, c) in givens:
                print("Hint landed on a given (shouldn't happen).")
                continue
            if len(cand) != 1:
                print(f"Not a forced move. Try (r={r+1}, c={c+1}) candidates: {cand}")
                continue

            v = cand[0]
            state = GameState(state.puzzle, state.current.with_value(r, c, v), notes={})
            print(f"Filled (r={r+1}, c={c+1}) = {v}")
            print(state.current)

            if _is_complete(state.current) and not find_violations(state.current):
                print("\nYou solved it! 🎉")
                return
            continue

        if low.startswith("save "):
            _, file = cmd.split(maxsplit=1)
            path = Path(file).expanduser()
            _save_game(path, state)
            print(f"Saved to {path}")
            continue

        if low.startswith("load "):
            _, file = cmd.split(maxsplit=1)
            path = Path(file).expanduser()
            try:
                state = _load_game(path)
            except Exception as e:
                print(f"Load failed: {e}")
                continue
            givens = _givens_mask(state.puzzle)
            print(f"Loaded from {path}")
            print(state.current)
            continue


        if low.startswith("cand "):
            parts = cmd.split()
            if len(parts) != 3:
                print("Usage: cand r c")
                continue
            try:
                r_user, c_user = int(parts[1]), int(parts[2])
            except ValueError:
                print("r and c must be integers 1..9")
                continue

            if not (1 <= r_user <= 9 and 1 <= c_user <= 9):
                print("r and c must be in 1..9")
                continue

            r, c = r_user - 1, c_user - 1

            if not state.current.is_empty(r, c):
                print("Cell is not empty.")
                continue

            print(sorted(valid_candidates(state.current, r, c)))
            continue

        if low == "check":
            vios = find_violations(state.current)
            if not vios:
                print("No violations ✅")
            else:
                print("Violations:")
                for v in vios:
                    pretty = ", ".join(f"({chr(65+r)}{c+1})" for r, c in v.cells)
                    print(f" - {v.kind} duplicate {v.value} at {pretty}")

            continue

        if low.startswith("note "):
            parts = cmd.split()
            if len(parts) != 3:
                print("Usage: note A3 124")
                continue
            cell = parts[1].upper()
            digits = parts[2]

            if len(cell) != 2 or cell[0] not in "ABCDEFGHI" or cell[1] not in "123456789":
                print("Cell must look like A1..I9")
                continue

            r = "ABCDEFGHI".index(cell[0])
            c = int(cell[1]) - 1

            if (r, c) in givens:
                print("That cell is a given — no notes needed.")
                continue

            toggle = {int(ch) for ch in digits if ch.isdigit() and ch != "0"}
            if not toggle:
                print("Provide digits 1-9 to toggle, e.g. 124")
                continue

            new_notes = {k: set(v) for k, v in state.notes.items()}
            cur = new_notes.get((r, c), set())
            for d in toggle:
                if d in cur:
                    cur.remove(d)
                else:
                    cur.add(d)
            if cur:
                new_notes[(r, c)] = cur
            else:
                new_notes.pop((r, c), None)

            state = GameState(state.puzzle, state.current, new_notes)
            print(f"Notes at {cell}: {sorted(state.notes.get((r, c), set()))}")
            continue

        if low == "notes":
            if not state.notes:
                print("No notes.")
                continue
            for (r, c), digs in sorted(state.notes.items()):
                cell = f"{'ABCDEFGHI'[r]}{c+1}"
                print(f"{cell}: {''.join(str(d) for d in sorted(digs))}")
            continue


        move = _parse_move(cmd)
        if move is None:
            print("Unknown command. Type 'help'.")
            continue

        r, c, v = move

        if (r, c) in givens:
            print("That cell is a given — you can't change it.")
            continue

        if v == 0:
            state = GameState(state.puzzle, state.current.with_value(r, c, 0), notes={})
            print(f"Cleared (r={r+1}, c={c+1})  (type 'show' to view board)")
            continue

        # If the cell already has a value (and it's not a given), temporarily clear it
        # so "replacing" values feels natural.
        temp_board = state.current
        if not temp_board.is_empty(r, c):
            temp_board = temp_board.with_value(r, c, 0)

        if not is_move_valid(temp_board, r, c, v):
            cand = sorted(valid_candidates(temp_board, r, c))
            print(f"Invalid move for (r={r+1}, c={c+1}). Candidates: {cand}")
            continue

        new_notes = {k: set(vs) for k, vs in state.notes.items()}
        new_notes.pop((r, c), None)
        state = GameState(state.puzzle, temp_board.with_value(r, c, v), new_notes)
        print(f"Set (r={r+1}, c={c+1}) = {v}  (type 'show' to view board)")



        # state = GameState(state.puzzle, state.current.with_value(r, c, v))
        # print(state.current)

        if _is_complete(state.current) and not find_violations(state.current):
            print("\nYou solved it! 🎉")
            return
