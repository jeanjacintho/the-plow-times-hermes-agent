"""sudoku.py -- one Easy/Medium puzzle per edition date, unique and solvable."""
from __future__ import annotations

import pytest

from conftest import load_module

sudoku = load_module("sudoku", "pt-edition/scripts/sudoku.py")


def test_full_grid_is_a_valid_sudoku():
    grid = sudoku.generate_full_grid(sudoku.random.Random(7))
    assert sudoku.is_complete_valid(grid)


def test_puzzle_has_exactly_one_solution_and_matches_the_key():
    puzzle, solution, givens = sudoku.generate_puzzle("easy", seed="2026-09-11")
    assert givens >= sudoku.DIFFICULTIES["easy"]
    assert sudoku.verify_puzzle(puzzle, solution) == givens


def test_same_seed_reproduces_the_same_puzzle():
    a = sudoku.generate_puzzle("medium", seed="2026-09-12")
    b = sudoku.generate_puzzle("medium", seed="2026-09-12")
    assert a[0] == b[0]
    assert a[1] == b[1]


def test_different_seeds_are_not_the_same_grid():
    a, _, _ = sudoku.generate_puzzle("easy", seed="2026-09-11")
    b, _, _ = sudoku.generate_puzzle("easy", seed="2026-09-13")
    assert a != b


def test_unknown_difficulty_is_refused():
    with pytest.raises(ValueError, match="difficulty"):
        sudoku.generate_puzzle("hard", seed="2026-09-11")


def test_difficulty_alternates_easy_medium_by_day():
    assert sudoku.pick_difficulty("2026-09-11") == "easy"
    assert sudoku.pick_difficulty("2026-09-12") == "medium"


def test_verify_rejects_a_given_that_contradicts_the_key():
    puzzle, solution, _ = sudoku.generate_puzzle("easy", seed="2026-09-11")
    for r in range(9):
        for c in range(9):
            if puzzle[r][c]:
                puzzle[r][c] = (puzzle[r][c] % 9) + 1
                with pytest.raises(ValueError, match="contradict"):
                    sudoku.verify_puzzle(puzzle, solution)
                return
    raise AssertionError("expected at least one given")


def test_verify_rejects_an_ambiguous_grid():
    empty = [[0] * 9 for _ in range(9)]
    solution = sudoku.generate_full_grid(sudoku.random.Random(1))
    with pytest.raises(ValueError, match="too few givens|not uniquely"):
        sudoku.verify_puzzle(empty, solution)


def test_verify_rejects_an_invalid_solution():
    puzzle, solution, _ = sudoku.generate_puzzle("easy", seed="2026-09-11")
    solution[0][0] = solution[0][1]
    with pytest.raises(ValueError, match="not a valid Sudoku"):
        sudoku.verify_puzzle(puzzle, solution)


def test_a_month_of_dates_is_uniquely_solvable_for_both_bands():
    # Every breakfast paper in a month, both difficulties: each grid is
    # verified independently of generate_puzzle's own check.
    for day in range(1, 32):
        seed = f"2026-01-{day:02d}"
        for difficulty in ("easy", "medium"):
            puzzle, solution, givens = sudoku.generate_puzzle(difficulty, seed=seed)
            assert sudoku.verify_puzzle(puzzle, solution) == givens
            assert givens >= sudoku.DIFFICULTIES[difficulty]
            assert sudoku.is_complete_valid(solution)
