"""Correction du moteur optimisé, indépendamment des choix heuristiques."""

import random
import unittest

from dimacs import check_model
from dpll import SAT, UNSAT, Stats
from optimized import optimized
from tests.test_dpll import brute_force, random_formula


class OptimizedTest(unittest.TestCase):
    def assert_formula(self, n, clauses):
        original = [list(c) for c in clauses]
        status, model = optimized(n, clauses)
        expected = brute_force(n, [frozenset(c) for c in clauses])
        self.assertEqual(status, SAT if expected else UNSAT)
        if expected:
            self.assertEqual(set(model), set(range(1, n + 1)))
            self.assertTrue(check_model(clauses, model))
        else:
            self.assertIsNone(model)
        self.assertEqual([list(c) for c in clauses], original)

    def test_edge_cases(self):
        for n, clauses in [(0, []), (0, [[]]), (3, []), (2, [[1, -1], [-2]]),
                           (2, [[1, 1], [-1, -1]]), (3, [[-1, -2], [-2, -3]]),
                           (3, [[1, 2, 3], [-1], [-2], [-3]])]:
            with self.subTest(n=n, clauses=clauses):
                self.assert_formula(n, clauses)

    def test_random_against_exhaustive_oracle(self):
        rng = random.Random(606)
        for i in range(2000):
            n = rng.randint(1, 9)
            clauses = random_formula(rng, n, rng.randint(0, 6 * n), max_size=6)
            # Inclut les formules de placement, même avec régions qui se recouvrent.
            if i % 3 == 0:
                clauses = [frozenset(abs(lit) for lit in c) if len(c) > 2
                           else frozenset(-abs(lit) for lit in c) for c in clauses]
            with self.subTest(i=i):
                self.assert_formula(n, clauses)

    def test_watches_survive_backtracking(self):
        # Toute affectation est interdite : plusieurs conflits et retours
        # arrière, avec déplacements de surveillance entre les branches.
        import itertools
        for n in range(3, 7):
            clauses = [list(lits) for lits in itertools.product(*[(v, -v) for v in range(1, n + 1)])]
            stats = Stats()
            self.assertEqual(optimized(n, clauses, stats), (UNSAT, None))
            self.assertGreater(stats.backtracks, 1)
            self.assert_formula(n, clauses[1:])

    def test_deep_search_and_propagation(self):
        n = 2500
        clauses = [[2 * v + 1, 2 * v + 2] for v in range(n)]
        status, model = optimized(2 * n, clauses)
        self.assertEqual(status, SAT)
        self.assertTrue(check_model(clauses, model))
        chain = [[1]] + [[-v, v + 1] for v in range(1, n)] + [[-n]]
        self.assertEqual(optimized(n, chain), (UNSAT, None))


if __name__ == "__main__":
    unittest.main()
