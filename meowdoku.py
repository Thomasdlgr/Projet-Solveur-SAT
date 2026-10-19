"""Question 3 : résoudre une grille et écrire la solution au format du sujet."""

import argparse
from itertools import combinations
from pathlib import Path
import random
import sys
from tempfile import TemporaryDirectory

from dimacs import check_model, read_dimacs
from dpll import SAT, complete, dpll
from grid_convertion import meowdoku_to_dimacs, read_meowdoku


def validate_positions(grid, positions):
    """Vérifie les règles du jeu sans utiliser les clauses SAT.

    positions contient des couples (ligne, colonne), numérotés à partir de 1.
    Une solution incorrecte provoque une ValueError.
    """
    n, m = len(grid), len(grid[0])
    if any(not (1 <= i <= n and 1 <= j <= m) for i, j in positions):
        raise ValueError("Un chat est hors de la grille.")
    regions = {zone for row in grid for zone in row}
    occupied = [grid[i - 1][j - 1] for i, j in positions]
    if len(occupied) != len(regions) or set(occupied) != regions:
        raise ValueError("Il faut exactement un chat par région.")
    if len({i for i, j in positions}) != len(positions):
        raise ValueError("Plusieurs chats occupent la même ligne.")
    if len({j for i, j in positions}) != len(positions):
        raise ValueError("Plusieurs chats occupent la même colonne.")
    for (i, j), (k, l) in combinations(positions, 2):
        if max(abs(i - k), abs(j - l)) <= 1:
            raise ValueError("Deux chats sont adjacents.")


def solve_meowdoku(grid_file, output_file, seed=None):
    """Passe par un fichier DIMACS, puis DPLL, et écrit une solution vérifiée.

    Renvoie {région: (ligne, colonne)} si SAT, None si UNSAT.
    Si UNSAT, aucun fichier résultat n'est écrit. Le fichier source ne peut
    pas servir de destination. La graine rend les décisions reproductibles.
    """
    source, destination = Path(grid_file), Path(output_file)
    if source.resolve() == destination.resolve():
        raise ValueError("La sortie doit être différente du fichier d'entrée.")
    # Lecture en bytes pour recopier exactement le préfixe, même en CRLF.
    original = source.read_bytes()
    grid = read_meowdoku(source)
    zone_line = [line.split() for line in original.decode("utf-8").splitlines()
                 if line.strip() and not line.strip().startswith("c")][1]
    zones = zone_line[1:]
    with TemporaryDirectory(prefix="meowdoku-") as directory:
        cnf = Path(directory) / "grille.cnf"
        meowdoku_to_dimacs(source, cnf)
        nb_vars, clauses = read_dimacs(cnf)
        status, valuation = dpll(clauses, rng=random.Random(seed))
    if status != SAT:
        return None
    model = complete(valuation, nb_vars)
    if not check_model(clauses, model):
        raise ValueError("Le modèle renvoyé par DPLL ne satisfait pas la CNF.")
    m = len(grid[0])
    positions = [((v - 1) // m + 1, (v - 1) % m + 1)
                 for v, value in model.items() if value]
    validate_positions(grid, positions)
    solution = {grid[i - 1][j - 1]: (i, j) for i, j in positions}
    lines = [f"{zone} {solution[zone][0]} {solution[zone][1]}" for zone in zones]
    occupied = set(positions)
    lines.append("")
    lines.extend(" ".join("*" if (i + 1, j + 1) in occupied else "."
                          for j in range(m)) for i in range(len(grid)))
    separator = b"\n" if original.endswith(b"\n") else b"\n\n"
    destination.write_bytes(original + separator + ("\n".join(lines) + "\n").encode("utf-8"))
    return solution


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("grid_file", help="Grille au format GRID / ZONES")
    parser.add_argument("output_file", help="Fichier solution à écrire")
    parser.add_argument("--seed", type=int, default=None, help="Graine aléatoire")
    args = parser.parse_args()
    try:
        solution = solve_meowdoku(args.grid_file, args.output_file, args.seed)
    except (OSError, ValueError) as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 1
    if solution is None:
        print("UNSAT : aucune solution ; aucun fichier résultat écrit.")
        return 0
    print(f"SAT : solution vérifiée écrite dans {args.output_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
