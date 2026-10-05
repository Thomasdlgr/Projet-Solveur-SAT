"""Génération de grilles Meowdoku possédant au moins une solution."""

from pathlib import Path
import random


def generate_meowdoku(n, filename=None, seed=None):
    """Génère une grille de n lignes, n colonnes et n régions connexes.

    Une solution est d'abord construite, puis chaque chat devient le point
    de départ d'une région. Les régions grandissent sans déplacer les chats.
    La solution existe donc par construction, mais n'est pas forcément unique.

    Args:
        n: Taille de la grille (1 ou un entier supérieur ou égal à 4).
        filename: Chemin facultatif du fichier GRID / ZONES à écrire.
        seed: Graine facultative pour reproduire la même grille.

    Returns:
        Une liste de listes contenant les noms des régions.

    Example:
        grid = generate_meowdoku(6, "grille.txt", seed=42)
    """
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError("n doit être un entier strictement positif.")
    if n in (2, 3):
        raise ValueError("Aucune solution n'existe pour n = 2 ou n = 3.")

    rng = random.Random(seed)
    columns = []
    available = set(range(n))

    def place_cats():
        # Un chat par ligne ; chaque colonne est utilisée une seule fois.
        if len(columns) == n:
            return True
        candidates = sorted(available)
        rng.shuffle(candidates)
        for column in candidates:
            # Deux chats sur des lignes consécutives ne doivent pas être
            # voisins en diagonale. Les autres lignes sont assez éloignées.
            if columns and abs(column - columns[-1]) == 1:
                continue
            columns.append(column)
            available.remove(column)
            if place_cats():
                return True
            available.add(column)
            columns.pop()
        return False

    if not place_cats():
        raise ValueError("Impossible de placer les chats pour cette taille.")

    # A à Z pour les petites grilles, R1, R2, ... pour les grandes.
    zones = [chr(ord("A") + i) if n <= 26 else f"R{i + 1}" for i in range(n)]
    grid = [[None for _ in range(n)] for _ in range(n)]
    for row, column in enumerate(columns):
        grid[row][column] = zones[row]

    frontier = []

    def add_neighbors(row, column):
        # Chaque entrée propose d'étendre une région vers une case vide.
        for di, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            i, j = row + di, column + dj
            if 0 <= i < n and 0 <= j < n and grid[i][j] is None:
                frontier.append((i, j, grid[row][column]))

    for row, column in enumerate(columns):
        add_neighbors(row, column)

    while frontier:
        index = rng.randrange(len(frontier))
        frontier[index], frontier[-1] = frontier[-1], frontier[index]
        row, column, zone = frontier.pop()
        # Plusieurs régions peuvent avoir proposé la même case.
        if grid[row][column] is not None:
            continue
        grid[row][column] = zone
        add_neighbors(row, column)

    if filename is not None:
        with Path(filename).open("w", encoding="utf-8") as stream:
            stream.write("c Grille Meowdoku avec au moins une solution\n")
            stream.write(f"GRID {n} {n}\n")
            stream.write("ZONES " + " ".join(zones) + "\n")
            for row in grid:
                stream.write(" ".join(row) + "\n")

    return grid
