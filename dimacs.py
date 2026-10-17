"""Lecture des fichiers DIMACS CNF et vérification des modèles."""

from pathlib import Path


def parse_dimacs(text):
    """Traduit le contenu d'un fichier DIMACS CNF en formule Python.

    La formule est représentée par un couple ``(nb_vars, clauses)`` :
    chaque clause est un ``frozenset`` de littéraux DIMACS, l'entier ``k``
    pour x_k et ``-k`` pour non x_k. Un littéral répété dans une clause
    n'est donc conservé qu'une fois.

    Les lignes de commentaires ``c`` et les lignes vides sont ignorées.
    Une clause est une suite d'entiers terminée par ``0`` et peut s'étendre
    sur plusieurs lignes. Une ligne ``%`` termine la lecture : certains
    fichiers SATLIB la placent après la dernière clause.

    Le nombre de clauses annoncé dans l'en-tête n'est pas imposé, car il est
    inutile à la résolution. En revanche, une variable hors de
    ``1..nb_vars`` provoque une ``ValueError``.

    Exemple :
        nb_vars, clauses = parse_dimacs("p cnf 2 1\\n1 -2 0\\n")
    """
    nb_vars = None
    clauses = []
    current = []
    for number, line in enumerate(text.splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("c"):
            continue
        if line.startswith("%"):
            break
        if line.startswith("p"):
            fields = line.split()
            if nb_vars is not None:
                raise ValueError(f"Ligne {number} : en-tête répété.")
            if len(fields) != 4 or fields[1] != "cnf":
                raise ValueError(f"Ligne {number} : l'en-tête doit être p cnf V C.")
            try:
                nb_vars, nb_clauses = int(fields[2]), int(fields[3])
            except ValueError as error:
                raise ValueError(f"Ligne {number} : V et C doivent être des entiers.") from error
            if nb_vars < 0 or nb_clauses < 0:
                raise ValueError(f"Ligne {number} : V et C doivent être positifs.")
            continue
        if nb_vars is None:
            raise ValueError(f"Ligne {number} : clause rencontrée avant l'en-tête p cnf.")

        for token in line.split():
            try:
                literal = int(token)
            except ValueError as error:
                raise ValueError(f"Ligne {number} : littéral invalide {token!r}.") from error
            if literal == 0:
                clauses.append(frozenset(current))
                current = []
            elif abs(literal) > nb_vars:
                raise ValueError(
                    f"Ligne {number} : la variable {abs(literal)} dépasse V = {nb_vars}."
                )
            else:
                current.append(literal)

    if nb_vars is None:
        raise ValueError("L'en-tête p cnf V C est absent.")
    # Tolérance : une dernière clause sans 0 final est tout de même conservée.
    if current:
        clauses.append(frozenset(current))
    return nb_vars, clauses


def read_dimacs(filename):
    """Lit un fichier DIMACS CNF et renvoie ``(nb_vars, clauses)``.

    Voir ``parse_dimacs`` pour la représentation de la formule.

    Exemple :
        nb_vars, clauses = read_dimacs("grille.cnf")
    """
    return parse_dimacs(Path(filename).read_text(encoding="utf-8"))


def check_model(clauses, model):
    """Indique si la valuation ``model`` satisfait toutes les clauses.

    ``model`` associe à un numéro de variable sa valeur booléenne. Un
    littéral dont la variable n'est pas affectée n'est pas considéré
    comme vrai : une clause doit contenir un littéral explicitement vrai.

    Exemple :
        check_model([frozenset({1, -2})], {1: False, 2: False})  # True
    """
    return all(
        any(model.get(abs(literal)) == (literal > 0) for literal in clause)
        for clause in clauses
    )
