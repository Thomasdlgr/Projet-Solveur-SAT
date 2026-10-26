"""Point d'entrée imposé du solveur SAT.

Usage :
    python sat.py instance.cnf [--mode dpll|optimized] [--output-model]

La sortie standard ne contient que le résultat (``s SATISFIABLE`` ou
``s UNSATISFIABLE``, puis ``v ... 0`` si le modèle est demandé). Les
éventuels messages de diagnostic vont sur la sortie d'erreur.
"""

import argparse
import json
import random
import sys
import time
from dataclasses import asdict

from dimacs import read_dimacs
from dpll import SAT, Stats, complete, dpll
from optimized import optimized


def solve(nb_vars, clauses, mode, stats=None, seed=None):
    """Renvoie ``(statut, modèle complet ou None)`` selon le mode choisi."""
    if mode == "dpll":
        status, valuation = dpll(clauses, rng=random.Random(seed), stats=stats)
    else:
        status, valuation = optimized(nb_vars, clauses, stats=stats)
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
    parser.add_argument("--stats", action="store_true",
                        help="Écrit les temps et compteurs en JSON sur stderr")
    parser.add_argument("--seed", type=int, default=None,
                        help="Graine reproductible pour le mode dpll")
    args = parser.parse_args(argv)

    total_start = time.perf_counter()
    try:
        nb_vars, clauses = read_dimacs(args.instance)
    except (OSError, ValueError) as error:
        print(f"Erreur de lecture : {error}", file=sys.stderr)
        return 1

    stats = Stats()
    cpu_start, wall_start = time.process_time(), time.perf_counter()
    status, model = solve(nb_vars, clauses, args.mode, stats, args.seed)
    cpu, wall = time.process_time() - cpu_start, time.perf_counter() - wall_start
    if status == SAT:
        print("s SATISFIABLE")
        if args.output_model:
            print(format_model(model))
    else:
        print("s UNSATISFIABLE")
    if args.stats:
        print(json.dumps({"mode": args.mode, "status": status,
                          "solve_cpu_s": cpu, "solve_wall_s": wall,
                          "total_wall_s": time.perf_counter() - total_start,
                          **asdict(stats)}), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
