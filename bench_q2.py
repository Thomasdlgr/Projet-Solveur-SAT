"""Mesures de performance des DPLL de la question 2.

Expériences (choisies par leur nom, toutes par défaut) :
  satlib   instances SATLIB uf/uuf, algorithmes 1 et 2, plusieurs graines ;
  phase    3-SAT aléatoire, n fixé, ratio clauses/variables variable ;
  scaling  3-SAT aléatoire au ratio 4,26, n croissant ;
  meowdoku grilles générées à la question 1, taille croissante ;
  variance une même instance résolue avec de nombreuses graines.

Chaque résolution est écrite dans ``results/q2_<expérience>.csv`` et un
résumé (médianes) est affiché. Une résolution qui dépasse le délai est
comptée comme « timeout ».

Usage :
    python bench_q2.py [satlib phase ...] [--timeout 30]
"""

import argparse
import csv
import random
import signal
import statistics
import tempfile
import time
from dataclasses import asdict
from pathlib import Path

from dimacs import read_dimacs
from dpll import SAT, Stats, dpll, dpll_sat
from grid_convertion import meowdoku_to_dimacs
from grid_generation import generate_meowdoku

RESULTS = Path("results")
SATLIB = Path("data/satlib")
FIELDS = ["family", "instance", "algo", "seed", "status", "time",
          "decisions", "backtracks", "unit_propagations", "pure_literals",
          "heuristic_time"]


class Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise Timeout


def run(clauses, algo, seed, timeout):
    """Résout une formule et renvoie (statut, durée, compteurs)."""
    stats = Stats()
    rng = random.Random(seed)
    signal.signal(signal.SIGALRM, _alarm)
    signal.setitimer(signal.ITIMER_REAL, timeout)
    start = time.perf_counter()
    try:
        if algo == 1:
            status = "SAT" if dpll_sat(clauses, rng, stats) else "UNSAT"
        else:
            status = dpll(clauses, rng, stats)[0]
    except Timeout:
        status = "TIMEOUT"
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    return status, time.perf_counter() - start, stats


def random_3sat(nb_vars, nb_clauses, rng):
    """3-SAT aléatoire : trois variables distinctes, signes au hasard
    (même modèle que les instances SATLIB uf/uuf)."""
    return [
        frozenset(v if rng.random() < 0.5 else -v for v in rng.sample(range(1, nb_vars + 1), 3))
        for _ in range(nb_clauses)
    ]


def measure(writer, rows, family, instance, clauses, algo, seed, timeout):
    status, elapsed, stats = run(clauses, algo, seed, timeout)
    row = {"family": family, "instance": instance, "algo": algo, "seed": seed,
           "status": status, "time": round(elapsed, 6), **asdict(stats)}
    writer.writerow(row)
    rows.append(row)
    return row


def summary(title, rows, key):
    """Affiche, par groupe, les médianes des mesures des runs terminés."""
    print(f"\n== {title}")
    print(f"{'groupe':>16} {'runs':>5} {'SAT':>4} {'UNSAT':>5} {'TO':>3} "
          f"{'t med (s)':>10} {'t max (s)':>10} {'déc med':>8} {'bt med':>8} "
          f"{'unit med':>9} {'pur med':>8}")
    groups = {}
    for row in rows:
        groups.setdefault(key(row), []).append(row)
    for group, items in groups.items():
        done = [r for r in items if r["status"] != "TIMEOUT"] or items

        def med(field):
            return statistics.median(r[field] for r in done)

        print(f"{str(group):>16} {len(items):>5} "
              f"{sum(r['status'] == 'SAT' for r in items):>4} "
              f"{sum(r['status'] == 'UNSAT' for r in items):>5} "
              f"{sum(r['status'] == 'TIMEOUT' for r in items):>3} "
              f"{med('time'):>10.4f} {max(r['time'] for r in done):>10.4f} "
              f"{med('decisions'):>8.0f} {med('backtracks'):>8.0f} "
              f"{med('unit_propagations'):>9.0f} {med('pure_literals'):>8.0f}")


def exp_satlib(writer, timeout):
    rows = []
    sizes = {"uf20-91": 50, "uf50-218": 50, "uuf50-218": 50, "uf75-325": 30, "uuf75-325": 30}
    for family, count in sizes.items():
        for path in sorted((SATLIB / family).glob("*.cnf"))[:count]:
            _, clauses = read_dimacs(path)
            for seed in range(3):
                for algo in (1, 2):
                    measure(writer, rows, family, path.name, clauses, algo, seed, timeout)
    summary("SATLIB, par famille et algorithme", rows, lambda r: f"{r['family']}/a{r['algo']}")


def exp_phase(writer, timeout, nb_vars=40, per_ratio=40):
    rows = []
    rng = random.Random(1)
    for ratio in (2, 3, 3.5, 4, 4.26, 4.5, 5, 6, 8):
        for index in range(per_ratio):
            clauses = random_3sat(nb_vars, round(ratio * nb_vars), rng)
            measure(writer, rows, f"r={ratio}", index, clauses, 2, index, timeout)
    summary(f"3-SAT aléatoire, n = {nb_vars}, par ratio m/n", rows, lambda r: r["family"])


def exp_scaling(writer, timeout, per_size=20):
    rows = []
    rng = random.Random(2)
    for nb_vars in (20, 30, 40, 50, 60, 70):
        for index in range(per_size):
            clauses = random_3sat(nb_vars, round(4.26 * nb_vars), rng)
            measure(writer, rows, f"n={nb_vars}", index, clauses, 2, index, timeout)
    summary("3-SAT aléatoire au ratio 4,26, par n", rows, lambda r: r["family"])
    summary("3-SAT aléatoire au ratio 4,26, par n et statut", rows,
            lambda r: f"{r['family']}/{r['status']}")


def meowdoku_clauses(n, seed, directory):
    grid, cnf = Path(directory) / "g.txt", Path(directory) / "g.cnf"
    generate_meowdoku(n, grid, seed=seed)
    meowdoku_to_dimacs(grid, cnf)
    return read_dimacs(cnf)[1]


def exp_meowdoku(writer, timeout, per_size=10):
    rows = []
    with tempfile.TemporaryDirectory() as directory:
        for n in (4, 6, 8, 10, 12, 14, 16):
            for seed in range(per_size):
                clauses = meowdoku_clauses(n, seed, directory)
                measure(writer, rows, f"n={n}", seed, clauses, 2, 0, timeout)
    summary("Meowdoku, par taille de grille", rows, lambda r: r["family"])


def exp_variance(writer, timeout, nb_seeds=100):
    rows = []
    instances = {name: read_dimacs(SATLIB / name)[1]
                 for name in ("uf50-218/uf50-01.cnf", "uuf50-218/uuf50-01.cnf")}
    with tempfile.TemporaryDirectory() as directory:
        instances["meowdoku n=14 (grille 2)"] = meowdoku_clauses(14, 2, directory)
    for name, clauses in instances.items():
        seeds = nb_seeds if "meowdoku" not in name else 20
        for seed in range(seeds):
            measure(writer, rows, name, name, clauses, 2, seed, timeout)
    summary("Une instance, plusieurs graines", rows, lambda r: r["family"][:16])
    for name in instances:
        times = sorted(r["time"] for r in rows if r["family"] == name)
        print(f"  {name} : min {times[0]:.3f} s, médiane {statistics.median(times):.3f} s, "
              f"max {times[-1]:.3f} s, timeouts "
              f"{sum(r['status'] == 'TIMEOUT' for r in rows if r['family'] == name)}")


EXPERIMENTS = {"satlib": exp_satlib, "phase": exp_phase, "scaling": exp_scaling,
               "meowdoku": exp_meowdoku, "variance": exp_variance}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("experiments", nargs="*",
                        help=f"Expériences parmi {', '.join(EXPERIMENTS)} (toutes par défaut)")
    parser.add_argument("--timeout", type=float, default=30.0,
                        help="Délai maximal par résolution, en secondes")
    args = parser.parse_args(argv)
    unknown = set(args.experiments) - set(EXPERIMENTS)
    if unknown:
        parser.error(f"expérience(s) inconnue(s) : {', '.join(sorted(unknown))}")

    RESULTS.mkdir(exist_ok=True)
    for name in args.experiments or EXPERIMENTS:
        with (RESULTS / f"q2_{name}.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=FIELDS)
            writer.writeheader()
            EXPERIMENTS[name](writer, args.timeout)


if __name__ == "__main__":
    main()
