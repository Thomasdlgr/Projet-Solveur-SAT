"""Conversion des fichiers de grilles Meowdoku en DIMACS CNF."""

from itertools import combinations
from pathlib import Path


def read_meowdoku(filename):
    """Lit une grille au format GRID / ZONES du sujet.

    Renvoie une matrice de noms de régions. Les lignes vides et les
    commentaires commençant par ``c`` sont ignorés.
    """
    lines = []
    for line in Path(filename).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("c"):
            lines.append(line.split())

    if len(lines) < 2 or len(lines[0]) != 3 or lines[0][0] != "GRID":
        raise ValueError("La première ligne utile doit être GRID N M.")
    try:
        n, m = map(int, lines[0][1:])
    except ValueError as error:
        raise ValueError("N et M doivent être des entiers.") from error
    if n <= 0 or m <= 0:
        raise ValueError("Les dimensions doivent être strictement positives.")

    if lines[1][0] != "ZONES" or len(lines[1]) < 2:
        raise ValueError("La deuxième ligne utile doit être ZONES suivie des régions.")
    zones = lines[1][1:]
    if len(set(zones)) != len(zones):
        raise ValueError("Les noms des régions doivent être distincts.")

    grid = lines[2:]
    if len(grid) != n or any(len(row) != m for row in grid):
        raise ValueError(f"La grille doit contenir {n} lignes de {m} cases.")
    used_zones = {zone for row in grid for zone in row}
    if used_zones != set(zones):
        raise ValueError("Chaque région déclarée doit apparaître, et aucune autre.")
    return grid


def meowdoku_to_dimacs(grid_file, dimacs_file):
    """Convertit un fichier grille Meowdoku en un fichier DIMACS CNF.

    La variable x(i, j) signifie « un chat occupe la case (i, j) ».
    Pour des coordonnées commençant à 1, son numéro est (i - 1) * M + j.
    Accepte les grilles rectangulaires et un nombre quelconque de régions.
    Renvoie le chemin du fichier DIMACS écrit (un objet Path).

    Exemple :
        meowdoku_to_dimacs("grille.txt", "grille.cnf")
    """
    grid = read_meowdoku(grid_file)
    n, m = len(grid), len(grid[0])

    def variable(i, j):
        # Les indices Python commencent à 0, les variables DIMACS à 1.
        return i * m + j + 1

    regions = {}
    for i in range(n):
        for j in range(m):
            regions.setdefault(grid[i][j], []).append(variable(i, j))

    # Une paire interdite (a, b) donne la clause (non a OU non b).
    # Le set évite de répéter les contraintes communes à plusieurs règles.
    forbidden_pairs = set()

    # Au plus un chat par ligne et par colonne.
    for i in range(n):
        forbidden_pairs.update(combinations([variable(i, j) for j in range(m)], 2))
    for j in range(m):
        forbidden_pairs.update(combinations([variable(i, j) for i in range(n)], 2))

    # Exactement un chat par région : au moins un, puis au plus un.
    clauses = []
    for cells in regions.values():
        clauses.append(cells)
        forbidden_pairs.update(combinations(cells, 2))

    # Les voisinages horizontaux/verticaux sont déjà couverts ci-dessus.
    # Il reste les deux diagonales vers la ligne suivante.
    for i in range(n - 1):
        for j in range(m):
            for next_j in (j - 1, j + 1):
                if 0 <= next_j < m:
                    forbidden_pairs.add((variable(i, j), variable(i + 1, next_j)))

    clauses.extend([-a, -b] for a, b in sorted(forbidden_pairs))
    output = Path(dimacs_file)
    with output.open("w", encoding="utf-8") as stream:
        stream.write("c Meowdoku : variable(i, j) = (i - 1) * M + j\n")
        stream.write(f"c GRID {n} {m}\n")
        stream.write(f"p cnf {n * m} {len(clauses)}\n")
        for clause in clauses:
            stream.write(" ".join(map(str, clause)) + " 0\n")
    return output


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("grid_file", help="Fichier de grille au format GRID / ZONES")
    parser.add_argument("dimacs_file", help="Fichier DIMACS à créer")
    args = parser.parse_args()
    meowdoku_to_dimacs(args.grid_file, args.dimacs_file)
