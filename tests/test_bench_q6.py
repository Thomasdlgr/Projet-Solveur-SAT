"""Un résultat faux ou un modèle mal formé ne doit pas être crédité."""

import unittest

from bench_q6 import parse_output
from dpll import SAT, UNSAT


class CompetitionOutputTest(unittest.TestCase):
    def test_valid_results(self):
        self.assertEqual(parse_output("s SATISFIABLE\nv 1 -2 0\n", 2,
                                      [frozenset({1}), frozenset({-2})]), SAT)
        self.assertEqual(parse_output("s SATISFIABLE\nv 0\n", 0, []), SAT)
        self.assertEqual(parse_output("s UNSATISFIABLE\n", 1, [frozenset()]), UNSAT)

    def test_reject_wrong_or_incomplete_model_and_extra_stdout(self):
        for output in ("s SATISFIABLE\nv -1 2 0\n", "s SATISFIABLE\nv 1 0\n",
                       "s SATISFIABLE\nv 1 1 -2 0\n", "s SATISFIABLE\nv 1 -2\n",
                       "s SATISFIABLE\nv 1 -3 0\n", "temps: 1\ns SATISFIABLE\nv 1 -2 0\n",
                       "s UNSATISFIABLE\nv 1 -2 0\n"):
            with self.subTest(output=output), self.assertRaises(ValueError):
                parse_output(output, 2, [frozenset({1}), frozenset({-2})])


if __name__ == "__main__":
    unittest.main()
