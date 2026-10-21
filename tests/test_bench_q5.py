"""Tests du générateur de grilles à régions aléatoires (question 5)."""

import random
import unittest

from bench_q5 import random_regions_grid


def parse(text):
    lines = text.splitlines()
    return lines[1].split()[1:], [line.split() for line in lines[2:]]


class RandomRegionsTest(unittest.TestCase):
    def test_regions_connexes(self):
        rng = random.Random(0)
        for n in range(4, 12):
            names, grid = parse(random_regions_grid(n, rng))
            with self.subTest(n=n):
                self.assertEqual(len(grid), n)
                self.assertTrue(all(len(row) == n for row in grid))
                self.assertEqual({cell for row in grid for cell in row}, set(names))
                self.assertEqual(len(names), n)
                for name in names:
                    cells = {(i, j) for i in range(n) for j in range(n) if grid[i][j] == name}
                    # Parcours depuis une case : on doit atteindre toute la région.
                    start = next(iter(cells))
                    seen, stack = {start}, [start]
                    while stack:
                        i, j = stack.pop()
                        for cell in ((i + 1, j), (i - 1, j), (i, j + 1), (i, j - 1)):
                            if cell in cells and cell not in seen:
                                seen.add(cell)
                                stack.append(cell)
                    self.assertEqual(seen, cells)

    def test_reproductible(self):
        self.assertEqual(random_regions_grid(8, random.Random(3)),
                         random_regions_grid(8, random.Random(3)))


if __name__ == "__main__":
    unittest.main()
