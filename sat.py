"""Point d'entrée imposé du solveur SAT.

Usage :
    python sat.py instance.cnf [--mode dpll|optimized] [--output-model]

La sortie standard ne contient que le résultat (``s SATISFIABLE`` ou
``s UNSATISFIABLE``, puis ``v ... 0`` si le modèle est demandé). Les
éventuels messages de diagnostic vont sur la sortie d'erreur.
"""

import argparse
import sys

from dimacs import read_dimacs
from dpll import SAT, complete, dpll


def solve(nb_vars, clauses, mode):
    """Renvoie ``(statut, modèle complet ou None)`` selon le mode choisi."""
    if mode == "dpll":
        status, valuation = dpll(clauses)
    else:
        # TODO question 6 : solveur optimisé. En attendant, DPLL de la question 2.
        status, valuation = dpll(clauses)
    if status != SAT:
        return status, None
    return status, complete(valuation, nb_vars)


def format_model(model):
    """Ligne ``v`` : littéral positif si la variable est vraie, négatif sinon."""
    literals = [str(var if value else -var) for var, value in sorted(model.items())]
    return "v " + " ".join(literals + ["0"])


def main(argv=None):
    parser = argparse.ArgumentParser(description="Solveur SAT DPLL (projet MLSF).")
    parser.add_argument("instance", help="Fichier DIMACS CNF")
    parser.add_argument("--mode", choices=("dpll", "optimized"), default="optimized")
    parser.add_argument("--output-model", action="store_true",
                        help="Affiche un modèle si la formule est satisfiable")
    args = parser.parse_args(argv)

    try:
        nb_vars, clauses = read_dimacs(args.instance)
    except (OSError, ValueError) as error:
        print(f"Erreur de lecture : {error}", file=sys.stderr)
        return 1

    status, model = solve(nb_vars, clauses, args.mode)
    if status == SAT:
        print("s SATISFIABLE")
        if args.output_model:
            print(format_model(model))
    else:
        print("s UNSATISFIABLE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
