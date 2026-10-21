"""Algorithmes DPLL 1 (satisfiabilité) et 2 (satisfiabilité et valuation).

Une formule CNF est une liste de clauses ; une clause est un ``frozenset``
de littéraux DIMACS (``k`` pour x_k, ``-k`` pour non x_k), comme renvoyé
par ``dimacs.read_dimacs``. Affecter le littéral ``l`` à vrai revient à
affecter sa variable ``abs(l)`` à ``l > 0``.
"""

from dataclasses import dataclass
import random
import sys
import time

SAT = "SAT"
UNSAT = "UNSAT"


@dataclass
class Stats:
    """Compteurs d'exécution, préparés pour l'analyse de la question 5."""

    decisions: int = 0
    backtracks: int = 0
    unit_propagations: int = 0
    pure_literals: int = 0
    heuristic_time: float = 0.0  # secondes passées dans le choix de branchement


def simplify(clauses, literal):
    """Renvoie F[literal <- 1] sans modifier ``clauses``.

    Les clauses contenant ``literal`` sont vraies et disparaissent ;
    ``-literal`` est retiré des autres clauses, qui peuvent devenir vides.
    """
    result = []
    for clause in clauses:
        if literal in clause:
            continue
        if -literal in clause:
            clause = clause - {-literal}
        result.append(clause)
    return result


def find_unit(clauses):
    """Renvoie le littéral d'une clause unitaire, ou ``None``."""
    for clause in clauses:
        if len(clause) == 1:
            return next(iter(clause))
    return None


def find_pure(clauses):
    """Renvoie un littéral pur (dont la négation n'apparaît pas), ou ``None``."""
    literals = set()
    for clause in clauses:
        literals.update(clause)
    # Parcours trié : le résultat ne dépend pas de l'ordre interne du set.
    for literal in sorted(literals, key=abs):
        if -literal not in literals:
            return literal
    return None


def random_choice(clauses, rng):
    """Fonction RandomChoice : variable et valeur de vérité au hasard.

    Le couple (p, b) est renvoyé sous la forme d'un littéral : ``p`` si
    b = 1 et ``-p`` si b = 0. La branche ``else`` utilise son opposé.
    """
    variables = sorted({abs(literal) for clause in clauses for literal in clause})
    variable = rng.choice(variables)
    return variable if rng.random() < 0.5 else -variable


def _propagate(clauses, stats, forced):
    """Lignes 1 à 16 des algorithmes : clause vide, formule vide,
    clauses unitaires et littéraux purs, appliqués tant que possible.

    Les règles unitaire et pure sont des appels récursifs terminaux dans
    l'énoncé ; une boucle donne le même résultat sans consommer la pile.
    Les littéraux fixés sont ajoutés à ``forced`` (si ce n'est pas None).
    Renvoie ``(statut, clauses)`` avec statut SAT, UNSAT ou None si une
    décision est nécessaire.
    """
    while True:
        if any(not clause for clause in clauses):
            return UNSAT, clauses
        if not clauses:
            return SAT, clauses
        literal = find_unit(clauses)
        if literal is not None:
            stats.unit_propagations += 1
        else:
            literal = find_pure(clauses)
            if literal is None:
                return None, clauses
            stats.pure_literals += 1
        if forced is not None:
            forced.append(literal)
        clauses = simplify(clauses, literal)


def _raise_recursion_limit(clauses):
    """La récursion ne porte que sur les décisions : sa profondeur est au
    plus le nombre de variables de la formule."""
    variables = {abs(literal) for clause in clauses for literal in clause}
    needed = len(variables) + 1000
    if sys.getrecursionlimit() < needed:
        sys.setrecursionlimit(needed)


def dpll_sat(clauses, rng=None, stats=None):
    """Algorithme 1 : renvoie True si la formule est satisfiable.

    Exemple :
        dpll_sat([frozenset({1, 2}), frozenset({-1})])  # True
    """
    rng = rng if rng is not None else random.Random()
    stats = stats if stats is not None else Stats()
    _raise_recursion_limit(clauses)
    return _dpll_sat(list(clauses), rng, stats)


def _dpll_sat(clauses, rng, stats):
    status, clauses = _propagate(clauses, stats, None)
    if status is not None:
        return status == SAT
    stats.decisions += 1
    literal = random_choice(clauses, rng)
    if _dpll_sat(simplify(clauses, literal), rng, stats):
        return True
    stats.backtracks += 1
    return _dpll_sat(simplify(clauses, -literal), rng, stats)


def dpll(clauses, rng=None, stats=None, choose=None):
    """Algorithme 2 : renvoie ``(SAT, valuation)`` ou ``(UNSAT, None)``.

    ``choose(clauses) -> littéral`` est la fonction de branchement (ligne
    17). Par défaut c'est RandomChoice (algorithme 2) ; ``heuristics.dpll_h``
    passe ici une heuristique H pour obtenir l'algorithme 3.

    La valuation est un dictionnaire {variable: booléen}. Elle est partielle :
    une variable disparue de la formule sans avoir été affectée n'y figure
    pas, et peut prendre n'importe quelle valeur (voir ``complete``).

    Exemple :
        dpll([frozenset({1, 2}), frozenset({-1})])  # (SAT, {1: False, 2: True})
    """
    if choose is None:
        rng = rng if rng is not None else random.Random()
        choose = lambda current: random_choice(current, rng)
    stats = stats if stats is not None else Stats()
    _raise_recursion_limit(clauses)
    valuation = _dpll(list(clauses), choose, stats)
    return (UNSAT, None) if valuation is None else (SAT, valuation)


def _dpll(clauses, choose, stats):
    """Renvoie une valuation (dict) si SAT, ``None`` si UNSAT."""
    forced = []
    status, clauses = _propagate(clauses, stats, forced)
    if status == UNSAT:
        return None
    if status == SAT:
        valuation = {}
    else:
        stats.decisions += 1
        start = time.perf_counter()
        literal = choose(clauses)
        stats.heuristic_time += time.perf_counter() - start
        valuation = _dpll(simplify(clauses, literal), choose, stats)
        if valuation is None:
            stats.backtracks += 1
            literal = -literal
            valuation = _dpll(simplify(clauses, literal), choose, stats)
            if valuation is None:
                return None
        valuation[abs(literal)] = literal > 0
    # v ∪ {l} pour chaque littéral fixé par propagation ou pureté.
    for literal in forced:
        valuation[abs(literal)] = literal > 0
    return valuation


def complete(valuation, nb_vars, default=False):
    """Étend une valuation partielle à toutes les variables 1..nb_vars.

    Une variable absente de la valuation n'apparaît plus dans la formule
    restante : toute valeur convient, ``default`` est utilisée.
    """
    return {variable: valuation.get(variable, default) for variable in range(1, nb_vars + 1)}
