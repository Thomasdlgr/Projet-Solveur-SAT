"""Heuristiques de branchement pour DPLL_H (algorithme 3, question 4).

Une heuristique est une fonction ``choose(clauses) -> littéral`` appelée à
la ligne 17 de l'algorithme : le littéral renvoyé code le couple (p, b),
``p`` si b = 1 et ``-p`` si b = 0, comme ``random_choice`` à la question 2.
Elle n'est appelée que si la formule courante n'a ni clause vide, ni clause
unitaire, ni littéral pur : la formule contient donc au moins une variable,
et toutes ses clauses ont au moins deux littéraux.

Heuristiques disponibles (noms de ``HEURISTICS``) :
  H0          choix aléatoire (CA), celui de l'algorithme 2 ;
  H1          première variable libre (PVL), valeur 1 ;
  H2s / H2d   variable la plus fréquente, polarité majoritaire (VPPM) ;
  H3s / H3d   littéral le plus fréquent (LP) ;
  H4s / H4d   variable la plus fréquente dans les clauses de taille
              minimale, polarité majoritaire (VFCM, MOMS) ;
  H5s / H5d   littéral le plus fréquent dans les clauses de taille
              minimale (LFCM) ;
  H6s / H6d   variable de meilleur poids de Jeroslow-Wang (VJW) ;
  H7s / H7d   littéral de meilleur poids de Jeroslow-Wang (LJW) ;
  H8s / H8d   heuristique ajoutée (JWP) : comme H7, mais en ne choisissant
              que des littéraux positifs tant qu'il en reste. Sur Meowdoku,
              cela revient à placer un chat dans la plus petite région.
Le suffixe ``s`` (statique) calcule les scores une seule fois sur la formule
initiale ; ``d`` (dynamique) les recalcule sur la formule courante.

En cas d'égalité de score, on prend la plus petite variable, puis la
polarité positive : le choix est ainsi déterministe et reproductible.
"""

import random
from collections import Counter

from dpll import dpll, random_choice


# --- Poids d'une clause selon sa taille -----------------------------------
# Chaque heuristique H2 à H7 compte des occurrences de littéraux, chaque
# occurrence étant pondérée par un poids qui ne dépend que de la taille de sa
# clause. Seuls les poids et le mode de sélection (variable ou littéral)
# changent d'une heuristique à l'autre.

def weight_one(size, min_size):
    """H2, H3 : toutes les occurrences comptent pour 1."""
    return 1


def weight_min_size(size, min_size):
    """H4, H5 : seules comptent les clauses de taille minimale k."""
    return 1 if size == min_size else 0


def weight_jeroslow_wang(size, min_size):
    """H6, H7, H8 : une clause de taille k pèse 2^-k."""
    return 2.0 ** -size


def literal_scores(clauses, weight):
    """Renvoie un ``Counter`` {littéral: somme des poids de ses occurrences}.

    Avec ``weight_one``, le score de ``l`` est occ(l, F) ; le score de la
    variable p est alors score[p] + score[-p] = #(p, F).
    """
    min_size = min((len(clause) for clause in clauses), default=0)
    scores = Counter()
    for clause in clauses:
        w = weight(len(clause), min_size)
        if w:
            for literal in clause:
                scores[literal] += w
    return scores


# --- Sélection d'après les scores ------------------------------------------
# Chaque mode de sélection est décrit par une clé de tri des littéraux : le
# littéral choisi est celui de plus grande clé. La même clé sert à la
# version dynamique (max) et au prétraitement de la version statique (tri).

def variable_key(scores):
    """Sélection d'une variable (H2, H4, H6).

    Le littéral p (ou -p) a pour clé le score de sa variable,
    #(p) = score[p] + score[-p], puis le fait d'être la polarité
    majoritaire (1 si score[p] >= score[-p], comme dans l'énoncé)."""
    def key(literal):
        p = abs(literal)
        majority = p if scores[p] >= scores[-p] else -p
        return (scores[p] + scores[-p], -p, literal == majority)
    return key


def literal_key(scores):
    """Sélection d'un littéral (H3, H5, H7) : son propre score."""
    return lambda literal: (scores[literal], -abs(literal), literal > 0)


def positive_literal_key(scores):
    """Sélection d'un littéral positif (H8) : les littéraux positifs présents
    dans la formule passent d'abord ; s'il n'y en a aucun, on retombe sur
    la clé de H7."""
    return lambda literal: (literal > 0 and scores[literal] > 0, scores[literal],
                            -abs(literal), literal > 0)


def variables_of(clauses):
    return {abs(literal) for clause in clauses for literal in clause}


def literals_of(variables):
    return [literal for p in variables for literal in (p, -p)]


# --- Construction des heuristiques -----------------------------------------

def first_free(clauses):
    """H1 (PVL) : plus petite variable de la formule courante, valeur 1."""
    return min(variables_of(clauses))


def make_dynamic(weight, make_key):
    """Scores recalculés sur la formule courante à chaque décision."""
    def choose(clauses):
        key = make_key(literal_scores(clauses, weight))
        return max(literals_of(variables_of(clauses)), key=key)
    return choose


def make_static(initial_clauses, weight, make_key):
    """Scores calculés une fois sur la formule initiale.

    Prétraitement : les littéraux sont triés par clé décroissante ; on ne
    garde que le premier de chaque variable. Choisir revient ensuite à
    prendre le premier littéral de cet ordre dont la variable est libre."""
    key = make_key(literal_scores(initial_clauses, weight))
    order, seen = [], set()
    for literal in sorted(literals_of(variables_of(initial_clauses)), key=key, reverse=True):
        if abs(literal) not in seen:
            seen.add(abs(literal))
            order.append(literal)

    def choose(clauses):
        # Première variable de l'ordre encore présente dans la formule
        # courante (les autres sont affectées ou n'interviennent plus).
        present = variables_of(clauses)
        return next(literal for literal in order if abs(literal) in present)
    return choose


# Nom : (description, poids, sélection) pour H2 à H7.
SCORED = {
    "H2": ("VPPM : variable la plus fréquente", weight_one, variable_key),
    "H3": ("LP : littéral le plus fréquent", weight_one, literal_key),
    "H4": ("VFCM : variable la plus fréquente dans les clauses de taille minimale",
           weight_min_size, variable_key),
    "H5": ("LFCM : littéral le plus fréquent dans les clauses de taille minimale",
           weight_min_size, literal_key),
    "H6": ("VJW : variable de meilleur poids de Jeroslow-Wang",
           weight_jeroslow_wang, variable_key),
    "H7": ("LJW : littéral de meilleur poids de Jeroslow-Wang",
           weight_jeroslow_wang, literal_key),
    "H8": ("JWP : littéral positif de meilleur poids de Jeroslow-Wang",
           weight_jeroslow_wang, positive_literal_key),
}

HEURISTICS = {"H0": "CA : choix aléatoire", "H1": "PVL : première variable libre"}
for _name, (_description, _, _) in SCORED.items():
    HEURISTICS[_name + "s"] = _description + " (statique)"
    HEURISTICS[_name + "d"] = _description + " (dynamique)"


def make_heuristic(name, clauses, rng=None):
    """Renvoie la fonction ``choose`` de l'heuristique ``name``.

    ``clauses`` est la formule initiale, utilisée par les versions statiques.
    ``rng`` n'est utilisé que par H0.
    """
    if name == "H0":
        rng = rng if rng is not None else random.Random()
        return lambda current: random_choice(current, rng)
    if name == "H1":
        return first_free
    base, variant = name[:-1], name[-1:]
    if base not in SCORED or variant not in ("s", "d"):
        raise ValueError(f"heuristique inconnue : {name!r} (choix : {', '.join(HEURISTICS)})")
    _, weight, make_key = SCORED[base]
    if variant == "d":
        return make_dynamic(weight, make_key)
    return make_static(clauses, weight, make_key)


def dpll_h(clauses, heuristic="H0", rng=None, stats=None):
    """Algorithme 3 : DPLL avec l'heuristique de branchement ``heuristic``.

    Renvoie ``(SAT, valuation)`` ou ``(UNSAT, None)`` comme ``dpll``.

    Exemple :
        dpll_h([frozenset({1, 2}), frozenset({-1, 2})], "H6d")
    """
    choose = make_heuristic(heuristic, clauses, rng)
    return dpll(clauses, stats=stats, choose=choose)
