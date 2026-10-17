"""Tests du lecteur DIMACS et de la vérification de modèles."""

import tempfile
import unittest
from pathlib import Path

from dimacs import check_model, parse_dimacs, read_dimacs

LAMPES = """c --- Exemple : Enigme des 3 lampes ---
c Variables : 1 = L1, 2 = L2, 3 = L3
p cnf 3 4
1 2 3 0
-1 -2 0
-2 -3 0
2 3 0
"""


class ParseDimacsTest(unittest.TestCase):
    def test_exemple_des_lampes(self):
        nb_vars, clauses = parse_dimacs(LAMPES)
        self.assertEqual(nb_vars, 3)
        self.assertEqual(
            clauses,
            [frozenset({1, 2, 3}), frozenset({-1, -2}), frozenset({-2, -3}), frozenset({2, 3})],
        )

    def test_clause_sur_plusieurs_lignes_et_espaces(self):
        _, clauses = parse_dimacs("p cnf 3 2\n1  -2\n 3 0 -1\n0\n")
        self.assertEqual(clauses, [frozenset({1, -2, 3}), frozenset({-1})])

    def test_fin_satlib_avec_pourcentage(self):
        _, clauses = parse_dimacs("p cnf 2 1\n1 2 0\n%\n0\n\n")
        self.assertEqual(clauses, [frozenset({1, 2})])

    def test_litteral_repete(self):
        _, clauses = parse_dimacs("p cnf 2 1\n1 1 -2 0\n")
        self.assertEqual(clauses, [frozenset({1, -2})])

    def test_clause_vide_et_formule_vide(self):
        self.assertEqual(parse_dimacs("p cnf 1 1\n0\n"), (1, [frozenset()]))
        self.assertEqual(parse_dimacs("p cnf 0 0\n"), (0, []))

    def test_derniere_clause_sans_zero(self):
        _, clauses = parse_dimacs("p cnf 2 1\n1 -2")
        self.assertEqual(clauses, [frozenset({1, -2})])

    def test_erreurs(self):
        mal_formes = [
            "1 2 0\n",                   # pas d'en-tête
            "p cnf 2\n1 0\n",            # en-tête incomplet
            "p sat 2 1\n1 0\n",          # mauvais format
            "p cnf 2 1\np cnf 2 1\n",    # en-tête répété
            "p cnf 2 1\n1 x 0\n",        # littéral non entier
            "p cnf 2 1\n1 -3 0\n",       # variable hors limites
        ]
        for text in mal_formes:
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_dimacs(text)

    def test_lecture_fichier(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lampes.cnf"
            path.write_text(LAMPES, encoding="utf-8")
            self.assertEqual(read_dimacs(path), parse_dimacs(LAMPES))


class CheckModelTest(unittest.TestCase):
    def test_modele_des_lampes(self):
        _, clauses = parse_dimacs(LAMPES)
        self.assertTrue(check_model(clauses, {1: True, 2: False, 3: True}))
        self.assertFalse(check_model(clauses, {1: True, 2: True, 3: False}))

    def test_variable_non_affectee(self):
        self.assertFalse(check_model([frozenset({1})], {}))

    def test_cas_limites(self):
        self.assertTrue(check_model([], {}))
        self.assertFalse(check_model([frozenset()], {1: True}))


if __name__ == "__main__":
    unittest.main()
