"""Question 6 : DPLL itératif, implications binaires et littéraux surveillés.

Aucune dépendance externe. La formule d'entrée reste inchangée. Le moteur
accepte toute CNF ; seule l'heuristique dépend de sa forme syntaxique.
"""

import time

from dpll import SAT, UNSAT, Stats


def optimized(nb_vars, clauses, stats=None):
    """Renvoie (SAT, valuation complète) ou (UNSAT, None).

    Pour les CNF composées de clauses positives et d'exclusions binaires
    négatives, choisit dans la plus petite clause positive restante (H8
    localisée), avec les scores H8s pour départager les candidats. Sinon,
    utilise H4d (MOMS). Les branches opposées sont toujours explorées.
    """
    stats = stats if stats is not None else Stats()
    solver = _Solver(nb_vars, clauses, stats)
    if not solver.consistent or not solver.search():
        return UNSAT, None
    return SAT, {v: solver.values[v] == 1 for v in range(1, nb_vars + 1)}


class _Solver:
    def __init__(self, nb_vars, clauses, stats):
        self.stats = stats
        # Les indices négatifs Python donnent une case distincte à chaque
        # littéral dans ces tableaux de longueur 2*n+1 (indice 0 inutilisé).
        self.values = [0] * (2 * nb_vars + 1)
        self.binary = [[] for _ in self.values]
        self.watches = [[] for _ in self.values]
        self.clauses = []
        self.positive_clauses = []
        self.trail = []
        self.head = 0
        self.consistent = True
        positive_scores = {}
        self.placement = True
        seen = set()
        for raw in clauses:
            clause_set = frozenset(raw)
            if any(-lit in clause_set for lit in clause_set) or clause_set in seen:
                continue
            seen.add(clause_set)
            clause = sorted(clause_set, key=lambda lit: (abs(lit), lit < 0))
            self.clauses.append(clause)
            if not clause:
                self.consistent = False
                return
            positive = all(lit > 0 for lit in clause)
            if positive:
                self.positive_clauses.append(clause)
                weight = 2.0 ** -len(clause)
                for lit in clause:
                    positive_scores[lit] = positive_scores.get(lit, 0.0) + weight
            elif not (len(clause) == 2 and all(lit < 0 for lit in clause)):
                self.placement = False
            if len(clause) == 1:
                if not self.enqueue(clause[0]):
                    self.consistent = False
                    return
            elif len(clause) == 2:
                a, b = clause
                self.binary[-a].append(b)
                self.binary[-b].append(a)
            else:
                # Les deux premières positions de la liste sont surveillées.
                self.watches[clause[0]].append(clause)
                self.watches[clause[1]].append(clause)
        self.positive_scores = positive_scores

    def enqueue(self, literal):
        """Affectation forcée ; False signifie une contradiction immédiate."""
        value = self.values[literal]
        if value:
            return value == 1
        self.values[literal] = 1
        self.values[-literal] = -1
        self.trail.append(literal)
        self.stats.unit_propagations += 1
        return True

    def propagate(self):
        """Ne visite que les implications et surveillances touchées."""
        values = self.values
        while self.head < len(self.trail):
            literal = self.trail[self.head]
            self.head += 1
            for implied in self.binary[literal]:
                if not self.enqueue(implied):
                    return False
            false = -literal
            watched = self.watches[false]
            index = 0
            while index < len(watched):
                clause = watched[index]
                if clause[0] == false:
                    clause[0], clause[1] = clause[1], clause[0]
                other = clause[0]
                if values[other] == 1:
                    index += 1
                    continue
                for k in range(2, len(clause)):
                    if values[clause[k]] != -1:
                        replacement = clause[k]
                        clause[1], clause[k] = replacement, false
                        self.watches[replacement].append(clause)
                        watched[index] = watched[-1]
                        watched.pop()
                        break
                else:
                    # Aucun remplaçant : clause unitaire ou conflit.
                    if not self.enqueue(other):
                        return False
                    index += 1
        return True

    def choose(self):
        if self.placement:
            # On ne parcourt pas les nombreuses exclusions négatives.
            # Une fois les clauses positives satisfaites, compléter à faux
            # préserve toutes les exclusions binaires déjà propagées.
            best = None
            for clause in self.positive_clauses:
                remaining = []
                for lit in clause:
                    value = self.values[lit]
                    if value == 1:
                        break
                    if value == 0:
                        remaining.append(lit)
                else:
                    if best is None or len(remaining) < len(best):
                        best = remaining
            if not best:
                return 0
            return max(best, key=lambda v: (self.positive_scores[v], -v))
        minimum = float("inf")
        counts = {}
        for clause in self.clauses:
            remaining = []
            for lit in clause:
                value = self.values[lit]
                if value == 1:
                    break
                if value == 0:
                    remaining.append(lit)
            else:
                size = len(remaining)
                if size > minimum:
                    continue
                if size < minimum:
                    minimum = size
                    counts.clear()
                for lit in remaining:
                    counts[lit] = counts.get(lit, 0) + 1
        if not counts:
            return 0
        variable = max({abs(lit) for lit in counts},
                       key=lambda v: (counts.get(v, 0) + counts.get(-v, 0), -v))
        return variable if counts.get(variable, 0) >= counts.get(-variable, 0) else -variable

    def undo(self, mark):
        for lit in self.trail[mark:]:
            self.values[lit] = self.values[-lit] = 0
        del self.trail[mark:]
        self.head = mark
        # Les surveillances restent valides après désaffectation : aucun
        # littéral ne devient faux en remontant dans l'arbre.

    def decide(self, literal):
        self.values[literal] = 1
        self.values[-literal] = -1
        self.trail.append(literal)

    def search(self):
        # (littéral de la première branche, début du niveau, branche opposée ?)
        stack = []
        while True:
            if self.propagate():
                start = time.perf_counter()
                literal = self.choose()
                self.stats.heuristic_time += time.perf_counter() - start
                if not literal:
                    return True
                self.stats.decisions += 1
                stack.append((literal, len(self.trail), False))
                self.decide(literal)
            else:
                while stack:
                    literal, mark, flipped = stack.pop()
                    self.undo(mark)
                    if not flipped:
                        self.stats.backtracks += 1
                        stack.append((literal, mark, True))
                        self.decide(-literal)
                        break
                else:
                    return False
