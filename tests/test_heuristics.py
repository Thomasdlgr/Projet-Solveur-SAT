"""Tests des heuristiques de branchement et de DPLL_H (question 4)."""

import random
import tempfile
import unittest
from pathlib import Path

from dimacs import check_model, parse_dimacs, read_dimacs
from dpll import SAT, UNSAT, Stats, complete, dpll, simplify
from grid_convertion import meowdoku_to_dimacs
from grid_generation import generate_meowdoku
from heuristics import (HEURISTICS, dpll_h, literal_scores, make_heuristic,
                        weight_jeroslow_wang, weight_one)
from tests.test_dimacs import LAMPES
from tests.test_dpll import brute_force, random_formula

# Formule d'exemple de l'énoncé :
# (x1 ∨ x2 ∨ ¬x4) ∧ (x2 ∨ x3) ∧ (x1 ∨ ¬x2 ∨ x4 ∨ ¬x5)
EXEMPLE = [frozenset({1, 2, -4}), frozenset({2, 3}), frozenset({1, -2, 4, -5})]


class ScoresTest(unittest.TestCase):
    def test_comptages_de_l_enonce(self):
        scores = literal_scores(EXEMPLE, weight_one)
        self.assertEqual(scores[2] + scores[-2], 3)   # #(x2, F)
        self.assertEqual(scores[2], 2)                # #+(x2, F)
        self.assertEqual(scores[-2], 1)               # #-(x2, F)
        self.assertEqual(scores[4], 1)                # occ(x4, F)

    def test_poids_jeroslow_wang_de_l_enonce(self):
        scores = literal_scores(EXEMPLE, weight_jeroslow_wang)
        self.assertEqual(scores[2] + scores[-2], 7 / 16)

    def test_choix_sur_l_exemple(self):
        # Calculés à la main (voir le rapport de la question 4).
        attendus = {"H1": 1, "H2": 2, "H3": 1, "H4": 2, "H5": 2, "H6": 2, "H7": 2, "H8": 2}
        for base, literal in attendus.items():
            for name in ([base] if base == "H1" else [base + "s", base + "d"]):
                with self.subTest(heuristique=name):
                    self.assertEqual(make_heuristic(name, EXEMPLE)(EXEMPLE), literal)

    def test_polarite_minoritaire_jamais_choisie(self):
        # x1 apparaît surtout négativement : VPPM doit renvoyer -1.
        clauses = [frozenset({-1, 2}), frozenset({-1, 3}), frozenset({1, 2, 3})]
        self.assertEqual(make_heuristic("H2d", clauses)(clauses), -1)

    def test_statique_egale_dynamique_sur_la_formule_initiale(self):
        rng = random.Random(4)
        for _ in range(200):
            clauses = random_formula(rng, 8, 20)
            clauses = [c for c in clauses if len(c) >= 2]
            if not clauses:
                continue
            for base in ("H2", "H3", "H4", "H5", "H6", "H7", "H8"):
                static = make_heuristic(base + "s", clauses)(clauses)
                dynamic = make_heuristic(base + "d", clauses)(clauses)
                self.assertEqual(static, dynamic)

    def test_statique_et_dynamique_divergent_apres_simplification(self):
        initial = [frozenset({2, -3, -1}), frozenset({3, -4}), frozenset({1, -5, -4}),
                   frozenset({-3, 3, 5}), frozenset({2, 3, 5}), frozenset({3, 4, 5})]
        current = simplify(initial, 5)
        # Sur la formule initiale x3 est la plus fréquente (5 occurrences) ;
        # une fois x5 fixé à 1, il ne reste plus qu'une occurrence de x3.
        self.assertEqual(make_heuristic("H2s", initial)(current), 3)
        self.assertEqual(make_heuristic("H2d", initial)(current), 1)

    def test_variable_choisie_toujours_libre(self):
        # Les versions statiques ne doivent pas renvoyer une variable déjà
        # sortie de la formule courante.
        current = simplify(EXEMPLE, 2)  # reste (x1 ∨ x4 ∨ ¬x5)
        for name in HEURISTICS:
            literal = make_heuristic(name, EXEMPLE, random.Random(0))(current)
            self.assertIn(abs(literal), {1, 4, 5})

    def test_h8_prefere_les_litteraux_positifs(self):
        # -1 a le meilleur poids, mais H8 choisit le meilleur littéral positif.
        clauses = [frozenset({-1, 2}), frozenset({-1, 3}), frozenset({1, 2, 3})]
        self.assertEqual(make_heuristic("H7d", clauses)(clauses), -1)
        self.assertEqual(make_heuristic("H8d", clauses)(clauses), 2)
        # Sans littéral positif, H8 se comporte comme H7.
        negatives = [frozenset({-1, -2}), frozenset({-2, -3})]
        self.assertEqual(make_heuristic("H8d", negatives)(negatives), -2)

    def test_nom_inconnu(self):
        with self.assertRaises(ValueError):
            make_heuristic("H9d", EXEMPLE)


class DpllHTest(unittest.TestCase):
    def assert_result(self, nb_vars, clauses, expected, name):
        status, valuation = dpll_h(clauses, name, random.Random(0))
        self.assertEqual(status, SAT if expected else UNSAT)
        if expected:
            self.assertTrue(check_model(clauses, complete(valuation, nb_vars)))
        else:
            self.assertIsNone(valuation)

    def test_cas_limites(self):
        for name in HEURISTICS:
            with self.subTest(heuristique=name):
                self.assert_result(0, [], True, name)
                self.assert_result(1, [frozenset()], False, name)
                self.assert_result(1, [frozenset({1, -1})], True, name)
                self.assert_result(LAMPES_VARS, LAMPES_CLAUSES, True, name)

    def test_oracle_force_brute(self):
        # Mêmes formules aléatoires qu'à la question 2 : chaque heuristique
        # doit donner le statut de la force brute et un modèle correct.
        rng = random.Random(2027)
        formulas = []
        for _ in range(400):
            nb_vars = rng.randint(1, 10)
            clauses = random_formula(rng, nb_vars, rng.randint(0, 5 * nb_vars))
            formulas.append((nb_vars, clauses, brute_force(nb_vars, clauses)))
        for name in HEURISTICS:
            for nb_vars, clauses, expected in formulas:
                with self.subTest(heuristique=name, clauses=clauses):
                    self.assert_result(nb_vars, clauses, expected, name)

    def test_meowdoku(self):
        with tempfile.TemporaryDirectory() as directory:
            grid, cnf = Path(directory) / "g.txt", Path(directory) / "g.cnf"
            for n in range(4, 9):
                generate_meowdoku(n, grid, seed=n)
                meowdoku_to_dimacs(grid, cnf)
                nb_vars, clauses = read_dimacs(cnf)
                for name in HEURISTICS:
                    with self.subTest(n=n, heuristique=name):
                        self.assert_result(nb_vars, clauses, True, name)
            grid.write_text("GRID 3 3\nZONES A B C\nA A B\nA B B\nC C C\n", encoding="utf-8")
            meowdoku_to_dimacs(grid, cnf)
            nb_vars, clauses = read_dimacs(cnf)
            for name in HEURISTICS:
                with self.subTest(grille="3x3 UNSAT", heuristique=name):
                    self.assert_result(nb_vars, clauses, False, name)

    def test_h0_identique_a_l_algorithme_2(self):
        # Avec la même graine, H0 doit reproduire exactement l'algorithme 2.
        rng = random.Random(7)
        for _ in range(100):
            clauses = random_formula(rng, 10, 40)
            seed = rng.random()
            stats_2, stats_h0 = Stats(), Stats()
            result_2 = dpll(clauses, random.Random(seed), stats_2)
            result_h0 = dpll_h(clauses, "H0", random.Random(seed), stats_h0)
            self.assertEqual(result_2, result_h0)
            self.assertEqual(stats_2.decisions, stats_h0.decisions)

    def test_temps_heuristique_mesure(self):
        stats = Stats()
        dpll_h([frozenset({i, -i}) for i in range(1, 50)], "H6d", stats=stats)
        self.assertEqual(stats.decisions, 49)
        self.assertGreater(stats.heuristic_time, 0)


LAMPES_VARS, LAMPES_CLAUSES = parse_dimacs(LAMPES)

if __name__ == "__main__":
    unittest.main()
