from sudoku.board import board_from_string
from sudoku.game import run_cli_game


def main() -> None:
    puzzle = (
        "53..7...."
        "6..195..."
        ".98....6."
        "8...6...3"
        "4..8.3..1"
        "7...2...6"
        ".6....28."
        "...419..5"
        "....8..79"
    )
    run_cli_game(board_from_string(puzzle))


if __name__ == "__main__":
    main()
