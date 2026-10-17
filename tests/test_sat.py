"""Tests de l'interface en ligne de commande imposée (sat.py)."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from dimacs import check_model, parse_dimacs, read_dimacs
from tests.test_dimacs import LAMPES

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = ROOT / "public-instances"


def run_sat(text, *options):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "f.cnf"
        path.write_text(text, encoding="utf-8")
        return subprocess.run([sys.executable, str(ROOT / "sat.py"), str(path), *options],
                              capture_output=True, text=True, cwd=ROOT)


class SatCliTest(unittest.TestCase):
    def test_sat_avec_modele(self):
        for mode in ("dpll", "optimized"):
            with self.subTest(mode=mode):
                result = run_sat(LAMPES, "--mode", mode, "--output-model")
                lines = result.stdout.splitlines()
                self.assertEqual(result.returncode, 0)
                self.assertEqual(lines[0], "s SATISFIABLE")
                self.assertEqual(len(lines), 2)
                literals = [int(token) for token in lines[1].split()[1:]]
                self.assertTrue(lines[1].startswith("v "))
                self.assertEqual(literals[-1], 0)
                self.assertEqual(sorted(map(abs, literals[:-1])), [1, 2, 3])
                model = {abs(l): l > 0 for l in literals[:-1]}
                self.assertTrue(check_model(parse_dimacs(LAMPES)[1], model))

    def test_sans_option_pas_de_modele(self):
        result = run_sat(LAMPES)
        self.assertEqual(result.stdout, "s SATISFIABLE\n")

    def test_unsat_sans_modele(self):
        result = run_sat("p cnf 1 2\n1 0\n-1 0\n", "--output-model")
        self.assertEqual(result.stdout, "s UNSATISFIABLE\n")

    @unittest.skipUnless(PUBLIC.is_dir(), "instances publiques absentes")
    def test_instances_publiques_courtes(self):
        """Tests d'interface et cas limites fournis par les enseignants."""
        expected = json.loads((PUBLIC / "expected.json").read_text(encoding="utf-8"))
        files = [path for path in sorted((PUBLIC / "instances").glob("*.cnf"))
                 if not path.name.startswith("public-")]
        self.assertEqual(len(files), 11)
        for path in files:
            for mode in ("dpll", "optimized"):
                with self.subTest(file=path.name, mode=mode):
                    result = run_sat(path.read_text(encoding="utf-8"),
                                     "--mode", mode, "--output-model")
                    lines = result.stdout.splitlines()
                    if expected[path.name] == "UNSAT":
                        self.assertEqual(lines, ["s UNSATISFIABLE"])
                        continue
                    self.assertEqual(lines[0], "s SATISFIABLE")
                    self.assertEqual(len(lines), 2)
                    literals = [int(token) for token in lines[1].split()[1:]]
                    self.assertEqual(literals[-1], 0)
                    model = {abs(l): l > 0 for l in literals[:-1]}
                    self.assertTrue(check_model(read_dimacs(path)[1], model))

    def test_fichier_invalide(self):
        result = run_sat("1 2 0\n")
        self.assertEqual(result.stdout, "")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Erreur", result.stderr)


if __name__ == "__main__":
    unittest.main()
