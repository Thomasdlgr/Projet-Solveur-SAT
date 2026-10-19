"""Validation de bout en bout de la question 3."""

from pathlib import Path
import tempfile
import unittest

from grid_convertion import read_meowdoku
from grid_generation import generate_meowdoku
from meowdoku import solve_meowdoku, validate_positions

EXAMPLE_TEXT = """c Grille 1
GRID 6 6
ZONES A B C D E F
A B C B B D
A B B B B D
A A B D D D
A A A E D D
A A A A D D
F A D D D D
"""


class MeowdokuTest(unittest.TestCase):
    def check_output(self, source, output, solution):
        original = source.read_bytes()
        self.assertTrue(output.read_bytes().startswith(original))
        lines = output.read_bytes()[len(original):].decode().split()
        grid = read_meowdoku(source)
        k = len(solution)
        decoded = {lines[t]: (int(lines[t + 1]), int(lines[t + 2]))
                   for t in range(0, 3 * k, 3)}
        self.assertEqual(decoded, solution)
        symbols = lines[3 * k:]
        self.assertEqual(len(symbols), len(grid) * len(grid[0]))
        self.assertTrue(set(symbols) <= {"*", "."})
        positions = [(v // len(grid[0]) + 1, v % len(grid[0]) + 1)
                     for v, symbol in enumerate(symbols) if symbol == "*"]
        self.assertEqual(set(positions), set(solution.values()))
        validate_positions(grid, positions)

    def test_example_and_generated(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "grid.txt", Path(directory) / "out.txt"
            source.write_text(EXAMPLE_TEXT)
            solution = solve_meowdoku(source, output, seed=0)
            self.check_output(source, output, solution)
            for n in (1, 4, 6, 8):
                for seed in range(3):
                    generate_meowdoku(n, source, seed=seed)
                    solution = solve_meowdoku(source, output, seed=seed)
                    self.assertIsNotNone(solution)
                    self.check_output(source, output, solution)

    def test_rectangular_and_original_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "grid.txt", Path(directory) / "out.txt"
            source.write_bytes(b"c Commentaire\r\nGRID 2 3\r\nZONES B A\r\nA A A\r\nB B B")
            solution = solve_meowdoku(source, output, seed=0)
            self.check_output(source, output, solution)
            self.assertTrue(output.read_bytes()[len(source.read_bytes()):].strip().startswith(b"B "))

    def test_unsat(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "grid.txt", Path(directory) / "out.txt"
            source.write_text("GRID 2 2\nZONES A B\nA A\nB B\n")
            self.assertIsNone(solve_meowdoku(source, output, seed=0))
            self.assertFalse(output.exists())

    def test_invalid_positions(self):
        grid = [["A"] * 4, ["B"] * 4, ["C"] * 4, ["D"] * 4]
        for positions in ([(1, 2), (2, 4), (3, 1)],
                          [(1, 2), (1, 4), (3, 1), (4, 3)],
                          [(1, 2), (2, 2), (3, 1), (4, 3)],
                          [(1, 1), (2, 2), (3, 3), (4, 4)],
                          [(0, 2), (2, 4), (3, 1), (4, 3)]):
            with self.assertRaises(ValueError):
                validate_positions(grid, positions)

    def test_do_not_overwrite_input(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "grid.txt"
            source.write_text(EXAMPLE_TEXT)
            with self.assertRaises(ValueError):
                solve_meowdoku(source, source)


if __name__ == "__main__":
    unittest.main()
