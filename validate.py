"""Validation des deux DPLL sur un ensemble de fichiers DIMACS.

Pour chaque fichier ``.cnf`` trouvé (récursivement) dans les dossiers donnés :
  * les algorithmes 1 et 2 doivent renvoyer le même statut ;
  * si le statut attendu est connu, il doit être obtenu ;
  * si la formule est SAT, le modèle complété doit satisfaire toutes les clauses.

Le statut attendu est lu dans un fichier ``expected.json`` (format des
instances publiques des enseignants : {"nom.cnf": "SAT" | "UNSAT"}) placé
dans le dossier du fichier ou dans un dossier parent. À défaut, il est déduit
du nom : préfixe ``uuf`` / ``uf`` (SATLIB), ou mention ``unsat`` / ``sat``.
Il est inconnu sinon, et seule la cohérence est testée.

Chaque algorithme est interrompu après ``--timeout`` secondes (60 s, comme
en compétition) ; l'instance est alors comptée comme « timeout ».

Usage :
    python validate.py public-instances data/satlib [--timeout 60] [-v]
"""

import argparse
import json
import random
import signal
import sys
import time
from functools import cache
from pathlib import Path

from dimacs import check_model, read_dimacs
from dpll import SAT, UNSAT, complete, dpll, dpll_sat

TIMEOUT = "TIMEOUT"


class Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise Timeout


def with_timeout(function, timeout):
    """Appelle ``function()`` ; lève ``Timeout`` après ``timeout`` secondes."""
    signal.signal(signal.SIGALRM, _alarm)
    signal.setitimer(signal.ITIMER_REAL, timeout)
    try:
        return function()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


@cache
def expected_file(directory):
    """Contenu du fichier expected.json de ``directory`` ou d'un parent."""
    for folder in (directory, *directory.parents):
        candidate = folder / "expected.json"
        if candidate.is_file():
            return json.loads(candidate.read_text(encoding="utf-8"))
    return {}


def expected_status(path):
    """Statut attendu pour ``path``, ou ``None`` s'il est inconnu."""
    status = expected_file(path.resolve().parent).get(path.name)
    if status is not None:
        return status
    name = path.name.lower()
    if name.startswith("uuf") or "unsat" in name:
        return UNSAT
    if name.startswith("uf") or "sat" in name:
        return SAT
    return None


def cnf_files(paths):
    for path in map(Path, paths):
        if path.is_dir():
            yield from sorted(path.rglob("*.cnf"))
        else:
            yield path


def validate(path, seed, timeout):
    """Renvoie ``(statut, message d'erreur ou None, durée en secondes)``."""
    nb_vars, clauses = read_dimacs(path)
    start = time.perf_counter()
    try:
        satisfiable = with_timeout(lambda: dpll_sat(clauses, random.Random(seed)), timeout)
        status, valuation = with_timeout(lambda: dpll(clauses, random.Random(seed)), timeout)
    except Timeout:
        return TIMEOUT, None, time.perf_counter() - start
    elapsed = time.perf_counter() - start

    if (status == SAT) != satisfiable:
        return status, "les algorithmes 1 et 2 sont en désaccord", elapsed
    expected = expected_status(path)
    if expected is not None and status != expected:
        return status, f"{expected} attendu", elapsed
    if status == SAT and not check_model(clauses, complete(valuation, nb_vars)):
        return status, "le modèle ne satisfait pas la formule", elapsed
    return status, None, elapsed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", help="Fichiers .cnf ou dossiers")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--timeout", type=float, default=60.0,
                        help="Délai par algorithme et par instance, en secondes")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Affiche une ligne par fichier")
    args = parser.parse_args(argv)

    counts = {SAT: 0, UNSAT: 0, TIMEOUT: 0}
    errors = 0
    total_time = 0.0
    for path in cnf_files(args.paths):
        status, error, elapsed = validate(path, args.seed, args.timeout)
        counts[status] += 1
        total_time += elapsed
        if args.verbose:
            print(f"{path.name:40} {status:8} {elapsed:8.3f} s", flush=True)
        if error is not None:
            errors += 1
            print(f"ÉCHEC {path} : {error}", flush=True)

    print(f"{sum(counts.values())} fichiers : {counts[SAT]} SAT, {counts[UNSAT]} UNSAT, "
          f"{counts[TIMEOUT]} timeout(s), {errors} échec(s), {total_time:.1f} s "
          f"(algorithmes 1 et 2)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
