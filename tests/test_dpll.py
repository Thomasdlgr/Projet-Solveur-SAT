"""Tests des algorithmes DPLL 1 et 2."""

import itertools
import random
import tempfile
import unittest
from pathlib import Path

from dimacs import check_model, parse_dimacs, read_dimacs
from dpll import SAT, UNSAT, Stats, complete, dpll, dpll_sat, find_pure, simplify
from grid_convertion import meowdoku_to_dimacs
from grid_generation import generate_meowdoku
from tests.test_dimacs import LAMPES


def brute_force(nb_vars, clauses):
    """Oracle : essaie les 2^nb_vars valuations."""
    for values in itertools.product((False, True), repeat=nb_vars):
        model = dict(enumerate(values, start=1))
        if check_model(clauses, model):
            return True
    return False


def random_formula(rng, nb_vars, nb_clauses, max_size=4):
    clauses = []
    for _ in range(nb_clauses):
        size = rng.randint(1, max_size)
        clauses.append(frozenset(
            rng.choice((1, -1)) * rng.randint(1, nb_vars) for _ in range(size)
        ))
    return clauses


def solve_both(nb_vars, clauses, seed):
    """Lance les deux versions et vérifie leur cohérence interne."""
    satisfiable = dpll_sat(clauses, random.Random(seed))
    status, valuation = dpll(clauses, random.Random(seed))
    return satisfiable, status, valuation


class BriquesTest(unittest.TestCase):
    def test_simplify(self):
        clauses = [frozenset({1, 2}), frozenset({-1, 3}), frozenset({2, 3})]
        self.assertEqual(simplify(clauses, 1), [frozenset({3}), frozenset({2, 3})])
        self.assertEqual(simplify(clauses, -1), [frozenset({2}), frozenset({2, 3})])
        # La formule d'origine n'est pas modifiée.
        self.assertEqual(clauses[1], frozenset({-1, 3}))

    def test_find_pure(self):
        self.assertEqual(find_pure([frozenset({1, -2}), frozenset({-1, -2})]), -2)
        self.assertIsNone(find_pure([frozenset({1, 2}), frozenset({-1, -2})]))

    def test_complete(self):
        self.assertEqual(complete({2: True}, 3), {1: False, 2: True, 3: False})


class DpllTest(unittest.TestCase):
    def assert_result(self, nb_vars, clauses, expected, seed=0):
        satisfiable, status, valuation = solve_both(nb_vars, clauses, seed)
        self.assertEqual(satisfiable, expected)
        self.assertEqual(status, SAT if expected else UNSAT)
        if expected:
            self.assertTrue(check_model(clauses, complete(valuation, nb_vars)))
        else:
            self.assertIsNone(valuation)

    def test_cas_limites(self):
        self.assert_result(0, [], True)
        self.assert_result(1, [frozenset()], False)
        self.assert_result(1, [frozenset({1}), frozenset({-1})], False)
        self.assert_result(1, [frozenset({1, -1})], True)

    def test_lampes(self):
        nb_vars, clauses = parse_dimacs(LAMPES)
        self.assert_result(nb_vars, clauses, True)

    def test_oracle_force_brute(self):
        rng = random.Random(2026)
        counts = {True: 0, False: 0}
        for _ in range(1500):
            nb_vars = rng.randint(1, 10)
            clauses = random_formula(rng, nb_vars, rng.randint(0, 5 * nb_vars))
            expected = brute_force(nb_vars, clauses)
            counts[expected] += 1
            with self.subTest(clauses=clauses):
                self.assert_result(nb_vars, clauses, expected, seed=rng.random())
        # Le jeu de test doit contenir des deux statuts en quantité.
        self.assertGreater(min(counts.values()), 300)

    def test_meowdoku_sat(self):
        with tempfile.TemporaryDirectory() as directory:
            for n in range(4, 10):
                grid, cnf = Path(directory) / "g.txt", Path(directory) / "g.cnf"
                generate_meowdoku(n, grid, seed=n)
                meowdoku_to_dimacs(grid, cnf)
                with self.subTest(n=n):
                    self.assert_result(*read_dimacs(cnf), True, seed=n)

    def test_meowdoku_unsat(self):
        grids = [
            # Deux régions verticales : les deux chats sont forcément voisins.
            "GRID 2 2\nZONES A B\nA B\nA B\n",
            # Aucune grille 3x3 à 3 régions n'a de solution.
            "GRID 3 3\nZONES A B C\nA A B\nA B B\nC C C\n",
            # Les régions B et C, réduites à une case, sont adjacentes.
            "GRID 4 4\nZONES A B C D\nA B C D\nA A D D\nA A D D\nA A D D\n",
        ]
        with tempfile.TemporaryDirectory() as directory:
            for text in grids:
                grid, cnf = Path(directory) / "g.txt", Path(directory) / "g.cnf"
                grid.write_text(text, encoding="utf-8")
                meowdoku_to_dimacs(grid, cnf)
                with self.subTest(grid=text):
                    self.assert_result(*read_dimacs(cnf), False)

    def test_recursion_profonde(self):
        # Des tautologies : ni clause unitaire ni littéral pur, donc une
        # décision par variable et une profondeur de 3000 appels.
        n = 3000
        self.assert_result(n, [frozenset({i, -i}) for i in range(1, n + 1)], True)
        # Une chaîne d'implications : uniquement de la propagation unitaire.
        chain = [frozenset({1})] + [frozenset({-i, i + 1}) for i in range(1, n)]
        self.assert_result(n, chain + [frozenset({-n})], False)

    def test_compteurs(self):
        stats = Stats()
        dpll([frozenset({1}), frozenset({-1, 2})], stats=stats)
        self.assertEqual(stats.unit_propagations, 2)
        self.assertEqual(stats.decisions, 0)


if __name__ == "__main__":
    unittest.main()
