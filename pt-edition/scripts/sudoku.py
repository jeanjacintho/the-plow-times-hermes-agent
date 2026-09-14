"""sudoku.py -- generates one Easy or Medium 9x9 Sudoku, deterministically
per edition date. No LLM involvement: the puzzle is pure code, generated
and verified the same way every time, so there is no such thing as a
malformed sudoku shipping in an edition -- unlike a headline, there is
nothing here for a language model to get wrong.

Algorithm (standard, not novel -- checked against a reference backtracking
Sudoku solver before writing this):
  1. Fill an empty grid completely via randomized backtracking -- try
     each row's empty cell with digits 1-9 in random order, recurse,
     backtrack on dead ends. This always succeeds for an empty 9x9 grid.
  2. Carve a puzzle out of that full grid by removing cells one at a time,
     in random order, but only when the count_solutions() solver still
     finds EXACTLY one solution after the removal -- if removing a cell
     would make the puzzle ambiguous (more than one valid fill), that
     removal is undone and a different cell is tried. This is what
     guarantees the shipped puzzle always has one, and only one, correct
     answer.
  3. Stop once the target number of givens (clues) for the requested
     difficulty is reached, or no more cells can be safely removed.
  4. Independently verify before return: the key is a valid complete
     Sudoku, every given matches the key, the solver finds exactly one
     solution, and that fill is the key. A failed check retries on a
     derived seed (still deterministic) rather than shipping the grid.
"""
from __future__ import annotations

import random

SIZE = 9
BOX = 3
# A uniquely solvable Sudoku cannot have fewer than 17 givens; Easy/Medium
# sit well above that. Below this, something in generation went wrong.
MIN_UNIQUENESS_GIVENS = 17
MAX_GENERATE_ATTEMPTS = 8
# Never anything harder than Medium -- this is a daily paper for one
# reader over breakfast, not a puzzle-page challenge. Givens counts are
# the standard rule-of-thumb bands (more givens = easier).
DIFFICULTIES = {
    "easy": 38,
    "medium": 32,
}


def _box_start(i):
    return (i // BOX) * BOX


def _is_safe(grid, row, col, value):
    if any(grid[row][c] == value for c in range(SIZE)):
        return False
    if any(grid[r][col] == value for r in range(SIZE)):
        return False
    br, bc = _box_start(row), _box_start(col)
    for r in range(br, br + BOX):
        for c in range(bc, bc + BOX):
            if grid[r][c] == value:
                return False
    return True


def _find_empty(grid):
    for r in range(SIZE):
        for c in range(SIZE):
            if grid[r][c] == 0:
                return r, c
    return None


def _shape_ok(grid):
    return (
        isinstance(grid, list)
        and len(grid) == SIZE
        and all(isinstance(row, list) and len(row) == SIZE for row in grid)
    )


def is_complete_valid(grid):
    """True only for a finished 9x9 with 1-9 once per row, column and box."""
    if not _shape_ok(grid):
        return False
    want = list(range(1, SIZE + 1))
    for i in range(SIZE):
        row = [grid[i][c] for c in range(SIZE)]
        col = [grid[r][i] for r in range(SIZE)]
        if sorted(row) != want or sorted(col) != want:
            return False
    for br in range(0, SIZE, BOX):
        for bc in range(0, SIZE, BOX):
            box = [
                grid[r][c]
                for r in range(br, br + BOX)
                for c in range(bc, bc + BOX)
            ]
            if sorted(box) != want:
                return False
    return True


def _fill_grid(grid, rng):
    """Randomized backtracking fill -- produces one shuffled complete
    solution per call (given a fresh rng)."""
    spot = _find_empty(grid)
    if spot is None:
        return True
    row, col = spot
    digits = list(range(1, SIZE + 1))
    rng.shuffle(digits)
    for value in digits:
        if _is_safe(grid, row, col, value):
            grid[row][col] = value
            if _fill_grid(grid, rng):
                return True
            grid[row][col] = 0
    return False


def _complete(grid):
    """Deterministic fill of empties, digits 1-9 in order -- the solver
    used to check the key, not the generator's shuffled fill."""
    spot = _find_empty(grid)
    if spot is None:
        return True
    row, col = spot
    for value in range(1, SIZE + 1):
        if _is_safe(grid, row, col, value):
            grid[row][col] = value
            if _complete(grid):
                return True
            grid[row][col] = 0
    return False


def count_solutions(grid, limit=2):
    """Counts solutions to `grid`, stopping as soon as `limit` is hit --
    a puzzle generator only ever needs to know "is it exactly one?", never
    the true count, so this never explores more of the tree than that."""
    spot = _find_empty(grid)
    if spot is None:
        return 1
    row, col = spot
    found = 0
    for value in range(1, SIZE + 1):
        if _is_safe(grid, row, col, value):
            grid[row][col] = value
            found += count_solutions(grid, limit - found)
            grid[row][col] = 0
            if found >= limit:
                break
    return found


def verify_puzzle(puzzle, solution):
    """Raise ValueError unless `puzzle` is uniquely solved by `solution`.

    Returns the given-count on success. Called on every generate_puzzle
    return so a logic bug cannot ship an ambiguous or contradictory grid.
    """
    if not _shape_ok(puzzle) or not _shape_ok(solution):
        raise ValueError("not a 9x9 grid")
    if not is_complete_valid(solution):
        raise ValueError("solution is not a valid Sudoku")
    givens = 0
    for r in range(SIZE):
        for c in range(SIZE):
            given = puzzle[r][c]
            key = solution[r][c]
            if key not in range(1, SIZE + 1):
                raise ValueError("solution cell out of range")
            if given not in range(0, SIZE + 1):
                raise ValueError("puzzle cell out of range")
            if given:
                if given != key:
                    raise ValueError("given contradicts the solution")
                givens += 1
    if givens < MIN_UNIQUENESS_GIVENS:
        raise ValueError("too few givens for a unique Sudoku")
    trial = [row[:] for row in puzzle]
    if count_solutions(trial, limit=2) != 1:
        raise ValueError("puzzle is not uniquely solvable")
    filled = [row[:] for row in puzzle]
    if not _complete(filled) or filled != solution:
        raise ValueError("solver disagrees with the key")
    return givens


def generate_full_grid(rng):
    grid = [[0] * SIZE for _ in range(SIZE)]
    if not _fill_grid(grid, rng):
        raise RuntimeError("could not fill a complete Sudoku grid")
    if not is_complete_valid(grid):
        raise RuntimeError("filled grid is not a valid Sudoku")
    return grid


def _carve(solution, rng, target_givens):
    puzzle = [row[:] for row in solution]
    cells = [(r, c) for r in range(SIZE) for c in range(SIZE)]
    rng.shuffle(cells)
    givens = SIZE * SIZE
    for row, col in cells:
        if givens <= target_givens:
            break
        removed = puzzle[row][col]
        puzzle[row][col] = 0
        trial = [r[:] for r in puzzle]
        if count_solutions(trial, limit=2) == 1:
            givens -= 1
        else:
            puzzle[row][col] = removed
    return puzzle


def generate_puzzle(difficulty, seed):
    """Returns (puzzle, solution, givens). `difficulty` is "easy" or
    "medium". `seed` determines the day's puzzle -- the same seed always
    reproduces the same puzzle, so re-rendering an edition never changes
    its Sudoku. The grid is verified before this returns; a failed check
    retries on a derived seed instead of shipping."""
    if difficulty not in DIFFICULTIES:
        raise ValueError(f"difficulty must be one of {tuple(DIFFICULTIES)}")
    target_givens = DIFFICULTIES[difficulty]
    last_error = None
    for attempt in range(MAX_GENERATE_ATTEMPTS):
        attempt_seed = seed if attempt == 0 else f"{seed}#{attempt}"
        try:
            rng = random.Random(attempt_seed)
            solution = generate_full_grid(rng)
            puzzle = _carve(solution, rng, target_givens)
            givens = verify_puzzle(puzzle, solution)
            return puzzle, solution, givens
        except (RuntimeError, ValueError) as exc:
            last_error = exc
    raise RuntimeError(
        f"could not generate a unique Sudoku after {MAX_GENERATE_ATTEMPTS} "
        f"attempts: {last_error}"
    )


def pick_difficulty(date_str):
    """Alternates Easy/Medium by day so the puzzle isn't identical in
    shape every single day, while never going past Medium."""
    day_num = int(date_str[-2:]) if date_str[-2:].isdigit() else 0
    return "medium" if day_num % 2 == 0 else "easy"
