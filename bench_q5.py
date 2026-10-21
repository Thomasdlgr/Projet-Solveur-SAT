"""Comparaison des heuristiques de DPLL_H (question 5).

Deux étapes :
  run     résout chaque instance avec chaque heuristique et écrit une ligne
          par résolution dans ``results/q5_runs.csv`` ;
  report  lit ce fichier, affiche un résumé et écrit les tableaux LaTeX et
          les données des courbes dans ``rapports/question5/generated``.

Familles d'instances :
  uf       3-SAT aléatoire SAT (SATLIB uf50, uf75) ;
  uuf      3-SAT aléatoire UNSAT (SATLIB uuf50, uuf75) ;
  struct   instances publiques structurées (toutes sauf les 3-SAT à
           50 variables) : coloration, planification, circuits, ... ;
  meow     grilles Meowdoku de la question 1 (SAT par construction) ;
  meowr    grilles Meowdoku à régions aléatoires (SAT ou UNSAT).

Chaque résolution est interrompue après ``--timeout`` secondes. Les
résolutions sont réparties sur plusieurs processus (``--jobs``) ; chaque
processus mesure son propre temps CPU, qui ne dépend donc pas des autres.

Usage :
    python bench_q5.py run [--timeout 20] [--jobs 6]
    python bench_q5.py report
"""

import argparse
import csv
import json
import math
import multiprocessing
import random
import signal
import statistics
import sys
import time
from functools import cache
from pathlib import Path

from dimacs import check_model, read_dimacs
from dpll import SAT, UNSAT, Stats, complete
from grid_convertion import meowdoku_to_dimacs
from grid_generation import generate_meowdoku
from heuristics import HEURISTICS, dpll_h

RESULTS = Path("results/q5_runs.csv")
INSTANCES = Path("data/q5")
SATLIB = Path("data/satlib")
PUBLIC = Path("public-instances/instances")
GENERATED = Path("rapports/question5/generated")
TIMEOUT = "TIMEOUT"

FAMILIES = {
    "uf": "3-SAT aléatoire SAT",
    "uuf": "3-SAT aléatoire UNSAT",
    "struct": "Instances structurées",
    "meow": "Meowdoku (question 1)",
    "meowr": "Meowdoku, régions aléatoires",
}
FIELDS = ["family", "instance", "nb_vars", "nb_clauses", "heuristic", "status",
          "cpu", "wall", "decisions", "backtracks", "unit_propagations",
          "pure_literals", "heuristic_time", "model_ok"]


# --- Instances ---------------------------------------------------------------

def random_regions_grid(n, rng):
    """Grille n x n à n régions connexes grandies depuis n cases tirées au
    hasard. Contrairement à la question 1, aucune solution n'est placée
    d'abord : la grille peut être SAT ou UNSAT."""
    cells = [(i, j) for i in range(n) for j in range(n)]
    seeds = rng.sample(cells, n)
    grid = [[None] * n for _ in range(n)]
    names = [f"R{k + 1}" for k in range(n)]
    frontier = []
    for k, (i, j) in enumerate(seeds):
        grid[i][j] = names[k]
        frontier += [(i + di, j + dj, names[k]) for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    while frontier:
        index = rng.randrange(len(frontier))
        frontier[index], frontier[-1] = frontier[-1], frontier[index]
        i, j, name = frontier.pop()
        if 0 <= i < n and 0 <= j < n and grid[i][j] is None:
            grid[i][j] = name
            frontier += [(i + di, j + dj, name) for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1))]
    lines = [f"GRID {n} {n}", "ZONES " + " ".join(names)] + [" ".join(row) for row in grid]
    return "\n".join(lines) + "\n"


def build_meowdoku_instances():
    """Écrit les grilles Meowdoku et leurs CNF dans ``data/q5`` (graines
    fixées : les mêmes fichiers sont recréés à chaque fois)."""
    INSTANCES.mkdir(parents=True, exist_ok=True)
    paths = []
    for n in (8, 10, 12, 14, 16):
        for seed in range(4):
            grid = INSTANCES / f"meow_n{n:02}_s{seed}.txt"
            generate_meowdoku(n, grid, seed=1000 * n + seed)
            paths.append(("meow", grid))
    for n in (6, 7, 8, 9, 10):
        rng = random.Random(n)
        for seed in range(6):
            grid = INSTANCES / f"meowr_n{n:02}_s{seed}.txt"
            grid.write_text(random_regions_grid(n, rng), encoding="utf-8")
            paths.append(("meowr", grid))
    instances = []
    for family, grid in paths:
        cnf = grid.with_suffix(".cnf")
        meowdoku_to_dimacs(grid, cnf)
        instances.append((family, cnf))
    return instances


def all_instances():
    """Liste des couples (famille, chemin du fichier CNF)."""
    instances = []
    for family, folder, count in (("uf", "uf50-218", 30), ("uf", "uf75-325", 20),
                                  ("uuf", "uuf50-218", 30), ("uuf", "uuf75-325", 20)):
        files = sorted((SATLIB / folder).rglob("*.cnf"))[:count]
        if not files:
            sys.exit(f"{SATLIB / folder} est vide : lancer d'abord download_satlib.py")
        instances += [(family, path) for path in files]
    for path in sorted(PUBLIC.glob("public-*.cnf")):
        nb_vars, clauses = read_dimacs(path)
        # Les publiques à 50 variables et 218 clauses sont des uf50 / uuf50.
        if (nb_vars, len(clauses)) != (50, 218):
            instances.append(("struct", path))
    return instances + build_meowdoku_instances()


# --- Une résolution ----------------------------------------------------------

class Timeout(Exception):
    pass


def _alarm(signum, frame):
    raise Timeout


@cache
def load(path):
    return read_dimacs(path)


def solve(task):
    """Résout une instance avec une heuristique ; renvoie une ligne du CSV.

    La graine de H0 dépend du nom de l'instance : chaque instance a son
    tirage, et une nouvelle exécution redonne exactement les mêmes choix."""
    family, path, heuristic, timeout = task
    nb_vars, clauses = load(path)
    stats = Stats()
    rng = random.Random(Path(path).name)
    signal.signal(signal.SIGALRM, _alarm)
    signal.setitimer(signal.ITIMER_REAL, timeout)
    cpu, wall = time.process_time(), time.perf_counter()
    try:
        status, valuation = dpll_h(clauses, heuristic, rng, stats)
    except Timeout:
        status, valuation = TIMEOUT, None
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
    cpu, wall = time.process_time() - cpu, time.perf_counter() - wall
    model_ok = "" if status != SAT else check_model(clauses, complete(valuation, nb_vars))
    return {"family": family, "instance": Path(path).name, "nb_vars": nb_vars,
            "nb_clauses": len(clauses), "heuristic": heuristic, "status": status,
            "cpu": round(cpu, 6), "wall": round(wall, 6), "decisions": stats.decisions,
            "backtracks": stats.backtracks, "unit_propagations": stats.unit_propagations,
            "pure_literals": stats.pure_literals,
            "heuristic_time": round(stats.heuristic_time, 6), "model_ok": model_ok}


def run(timeout, jobs):
    instances = all_instances()
    # Les plus gros fichiers d'abord : sinon une longue résolution lancée en
    # dernier laisse les autres processus inoccupés.
    instances.sort(key=lambda item: -item[1].stat().st_size)
    tasks = [(family, str(path), heuristic, timeout)
             for family, path in instances for heuristic in HEURISTICS]
    print(f"{len(instances)} instances x {len(HEURISTICS)} heuristiques = {len(tasks)} "
          f"résolutions, délai {timeout} s, {jobs} processus", flush=True)
    RESULTS.parent.mkdir(exist_ok=True)
    start = time.perf_counter()
    with RESULTS.open("w", newline="", encoding="utf-8") as stream, \
            multiprocessing.Pool(jobs) as pool:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        for done, row in enumerate(pool.imap_unordered(solve, tasks, chunksize=1), 1):
            writer.writerow(row)
            if row["model_ok"] is False:
                print(f"ERREUR : modèle faux pour {row['instance']} / {row['heuristic']}")
            if done % 200 == 0:
                stream.flush()
                print(f"  {done}/{len(tasks)} ({time.perf_counter() - start:.0f} s)", flush=True)
    print(f"Terminé en {time.perf_counter() - start:.0f} s -> {RESULTS}")


# --- Analyse -----------------------------------------------------------------

def read_runs():
    with RESULTS.open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        for field in ("cpu", "wall", "heuristic_time"):
            row[field] = float(row[field])
        for field in ("decisions", "backtracks", "unit_propagations", "pure_literals",
                      "nb_vars", "nb_clauses"):
            row[field] = int(row[field])
    return rows


def expected_statuses(rows):
    """Statut de chaque instance : connu (SATLIB, publiques, Meowdoku de la
    question 1) ou, pour les grilles aléatoires, celui des heuristiques qui
    ont terminé. Toute contradiction est une erreur."""
    public = json.loads((PUBLIC.parent / "expected.json").read_text(encoding="utf-8"))
    found = {}
    for row in rows:
        if row["status"] != TIMEOUT:
            found.setdefault(row["instance"], set()).add(row["status"])
    statuses = {}
    for row in rows:
        name = row["instance"]
        if name in statuses:
            continue
        known = {"uf": SAT, "uuf": UNSAT, "meow": SAT}.get(row["family"]) or public.get(name)
        observed = found.get(name, set())
        if len(observed) > 1 or (known and observed and observed != {known}):
            sys.exit(f"Statuts contradictoires pour {name} : {observed}, attendu {known}")
        statuses[name] = known or next(iter(observed), None)
    return statuses


def geometric_mean(values):
    values = [max(v, 1e-6) for v in values]
    return math.exp(sum(map(math.log, values)) / len(values)) if values else float("nan")


def group_stats(rows, timeout):
    """Indicateurs d'un groupe de résolutions d'une même heuristique."""
    solved = [r for r in rows if r["status"] != TIMEOUT]
    total_cpu = sum(r["cpu"] for r in rows)
    return {
        "n": len(rows),
        "solved": len(solved),
        # PAR-2 : un dépassement compte pour deux fois le délai.
        "par2": statistics.mean(r["cpu"] if r["status"] != TIMEOUT else 2 * timeout
                                for r in rows),
        "heur_share": sum(r["heuristic_time"] for r in rows) / sum(r["wall"] for r in rows)
        if rows else 0,
        "cpu": total_cpu,
    }


def common_instances(rows):
    """Instances résolues par toutes les heuristiques : seules celles-ci
    permettent de comparer les compteurs (un compteur interrompu par le
    délai n'a pas de sens)."""
    by_instance = {}
    for row in rows:
        by_instance.setdefault(row["instance"], []).append(row)
    return {name for name, items in by_instance.items()
            if all(r["status"] != TIMEOUT for r in items)}


def median_counter(rows, field):
    return statistics.median(r[field] for r in rows) if rows else float("nan")


def fmt(value, digits=0):
    if isinstance(value, float) and math.isnan(value):
        return "--"
    if digits == 0:
        return f"{value:,.0f}".replace(",", "\\,")
    return f"{value:.{digits}f}".replace(".", "{,}")


def write_table(name, header, lines):
    GENERATED.mkdir(parents=True, exist_ok=True)
    body = "\n".join(" & ".join(cells) + r" \\" for cells in lines)
    (GENERATED / f"{name}.tex").write_text(
        f"\\begin{{tabular}}{{{header[0]}}}\n\\toprule\n{header[1]} \\\\\n\\midrule\n"
        f"{body}\n\\bottomrule\n\\end{{tabular}}\n", encoding="utf-8")


def report(timeout):
    rows = read_runs()
    statuses = expected_statuses(rows)
    if any(r["model_ok"] == "False" for r in rows):
        sys.exit("Au moins un modèle renvoyé est faux.")
    for row in rows:
        row["expected"] = statuses[row["instance"]]
    heuristics = [h for h in HEURISTICS if any(r["heuristic"] == h for r in rows)]

    def select(family=None, heuristic=None, instances=None, expected=None):
        return [r for r in rows
                if (family is None or r["family"] == family)
                and (heuristic is None or r["heuristic"] == heuristic)
                and (instances is None or r["instance"] in instances)
                and (expected is None or r["expected"] == expected)]

    # Groupes analysés : chaque famille ; les familles qui mélangent les deux
    # statuts sont séparées en SAT / UNSAT.
    groups = []
    for family in FAMILIES:
        if family in ("struct", "meowr"):
            for status in (SAT, UNSAT):
                groups.append((f"{family}-{status.lower()}", f"{FAMILIES[family]} ({status})",
                               dict(family=family, expected=status)))
        else:
            groups.append((family, FAMILIES[family], dict(family=family)))

    # 1. Un tableau détaillé par groupe.
    summary_lines = []
    for key, title, criteria in groups:
        group_rows = select(**criteria)
        if not group_rows:
            continue
        common = common_instances(group_rows)
        nb_instances = len({r["instance"] for r in group_rows})
        print(f"\n== {title} : {nb_instances} instances, {len(common)} résolues par toutes")
        print(f"{'H':5} {'rés.':>5} {'PAR-2':>8} {'déc':>8} {'bt':>8} {'unit':>9} "
              f"{'pur':>7} {'u/déc':>6} {'%heur':>6}")
        lines = []
        for h in heuristics:
            h_rows = select(heuristic=h, **criteria)
            stats = group_stats(h_rows, timeout)
            c_rows = [r for r in h_rows if r["instance"] in common]
            dec = median_counter(c_rows, "decisions")
            unit = median_counter(c_rows, "unit_propagations")
            per_decision = unit / dec if dec and not math.isnan(dec) else float("nan")
            values = [f"{stats['solved']}/{stats['n']}", fmt(stats["par2"], 2),
                      fmt(dec), fmt(median_counter(c_rows, "backtracks")), fmt(unit),
                      fmt(median_counter(c_rows, "pure_literals")),
                      fmt(per_decision, 1), fmt(100 * stats["heur_share"])]
            lines.append([f"\\texttt{{{h}}}"] + values)
            print(f"{h:5} {values[0]:>5} {stats['par2']:8.3f} {dec:8.0f} "
                  f"{median_counter(c_rows, 'backtracks'):8.0f} {unit:9.0f} "
                  f"{median_counter(c_rows, 'pure_literals'):7.0f} {per_decision:6.1f} "
                  f"{100 * stats['heur_share']:6.1f}")
        write_table(f"detail-{key}", ("lrrrrrrrr",
                    "H & résolues & PAR-2 (s) & décisions & retours & unitaires & purs "
                    "& unit./déc. & \\% heur."), lines)

        # Gain par rapport à H0 sur les instances communes : moyenne
        # géométrique des rapports H0 / H (décisions et temps CPU).
        base = {r["instance"]: r for r in select(heuristic="H0", instances=common, **criteria)}
        gains = []
        for h in heuristics:
            pairs = [(base[r["instance"]], r)
                     for r in select(heuristic=h, instances=common, **criteria)]
            gains.append((
                geometric_mean([(b["decisions"] + 1) / (r["decisions"] + 1) for b, r in pairs]),
                geometric_mean([b["cpu"] / r["cpu"] for b, r in pairs]),
                group_stats(select(heuristic=h, **criteria), timeout)["solved"],
            ))
        summary_lines.append((title, nb_instances, len(common), gains))

    # 2. Tableau de synthèse : gain en temps par rapport à H0, par groupe.
    lines = []
    for h_index, h in enumerate(heuristics):
        cells = [f"\\texttt{{{h}}}"]
        for title, nb, nb_common, gains in summary_lines:
            dec_gain, cpu_gain, solved = gains[h_index]
            cells.append(f"{fmt(cpu_gain, 1)} ({solved})")
        lines.append(cells)
    titles = " & ".join(f"\\rotatebox{{70}}{{{t}}}" for t, *_ in summary_lines)
    write_table("synthese-temps", ("l" + "r" * len(summary_lines), f"H & {titles}"), lines)
    lines = []
    for h_index, h in enumerate(heuristics):
        cells = [f"\\texttt{{{h}}}"]
        for title, nb, nb_common, gains in summary_lines:
            cells.append(fmt(gains[h_index][0], 1))
        lines.append(cells)
    write_table("synthese-decisions", ("l" + "r" * len(summary_lines), f"H & {titles}"), lines)
    with (GENERATED / "groupes.tex").open("w", encoding="utf-8") as stream:
        stream.write("\\begin{tabular}{lrr}\n\\toprule\nGroupe & instances & "
                     "résolues par toutes \\\\\n\\midrule\n")
        for title, nb, nb_common, _ in summary_lines:
            stream.write(f"{title} & {nb} & {nb_common} \\\\\n")
        stream.write("\\bottomrule\n\\end{tabular}\n")

    # 3. Statique contre dynamique, toutes instances confondues.
    print("\n== Statique / dynamique (instances résolues par les deux variantes)")
    lines = []
    for base_name in sorted({h[:2] for h in heuristics if h[-1] in "sd"}):
        static, dynamic = select(heuristic=base_name + "s"), select(heuristic=base_name + "d")
        by_name = {r["instance"]: r for r in static}
        pairs = [(by_name[r["instance"]], r) for r in dynamic
                 if r["status"] != TIMEOUT and by_name[r["instance"]]["status"] != TIMEOUT]
        dec_ratio = geometric_mean([(s["decisions"] + 1) / (d["decisions"] + 1) for s, d in pairs])
        cpu_ratio = geometric_mean([s["cpu"] / d["cpu"] for s, d in pairs])
        cost = geometric_mean([
            (d["heuristic_time"] / max(d["decisions"], 1)) / max(s["heuristic_time"] / max(s["decisions"], 1), 1e-9)
            for s, d in pairs if s["decisions"] and d["decisions"]])
        st_stats, dy_stats = group_stats(static, timeout), group_stats(dynamic, timeout)
        cells = [base_name, f"{st_stats['solved']} / {dy_stats['solved']}", fmt(dec_ratio, 2),
                 fmt(cost, 1), fmt(cpu_ratio, 2),
                 f"{fmt(100 * st_stats['heur_share'])} / {fmt(100 * dy_stats['heur_share'])}"]
        lines.append(cells)
        print(" ".join(f"{c:>12}" for c in cells))
    write_table("statique-dynamique", ("lrrrrr",
                "H & résolues (s / d) & décisions s/d & coût d'un choix d/s & temps s/d "
                "& \\% heur. (s / d)"), lines)

    # 4. Courbes « nombre d'instances résolues en fonction du temps CPU ».
    for name, families in (("cactus-satlib", ("uf", "uuf", "struct")),
                           ("cactus-meowdoku", ("meow", "meowr"))):
        # Un fichier par heuristique : le k-ième temps trié est le temps
        # nécessaire pour résoudre k instances.
        for h in heuristics:
            times = sorted(r["cpu"] for r in rows
                           if r["heuristic"] == h and r["family"] in families
                           and r["status"] != TIMEOUT)
            with (GENERATED / f"{name}-{h}.dat").open("w", encoding="utf-8") as stream:
                stream.write("solved cpu\n")
                for index, value in enumerate(times, 1):
                    stream.write(f"{index} {value:.6f}\n")

    # 5. Mise à l'échelle sur Meowdoku : temps CPU médian par taille.
    lines = []
    sizes = sorted({r["nb_vars"] for r in select(family="meow")})
    for h in heuristics:
        cells = [f"\\texttt{{{h}}}"]
        for size in sizes:
            items = [r for r in select(family="meow", heuristic=h) if r["nb_vars"] == size]
            if sum(r["status"] == TIMEOUT for r in items) * 2 > len(items):
                cells.append("TO")
            else:
                cells.append(fmt(statistics.median(
                    r["cpu"] if r["status"] != TIMEOUT else math.inf for r in items), 3))
        lines.append(cells)
    header = " & ".join(f"$n={round(math.sqrt(s))}$" for s in sizes)
    write_table("meowdoku-taille", ("l" + "r" * len(sizes), f"H & {header}"), lines)

    statuses_meowr = [statuses[n] for n in {r["instance"] for r in select(family="meowr")}]
    print(f"\nGrilles à régions aléatoires : {statuses_meowr.count(SAT)} SAT, "
          f"{statuses_meowr.count(UNSAT)} UNSAT, {statuses_meowr.count(None)} inconnues")
    print(f"Tableaux écrits dans {GENERATED}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=("run", "report"))
    parser.add_argument("--timeout", type=float, default=20.0,
                        help="Délai par résolution, en secondes")
    parser.add_argument("--jobs", type=int, default=max(1, multiprocessing.cpu_count() - 2))
    args = parser.parse_args(argv)
    if args.command == "run":
        run(args.timeout, args.jobs)
    else:
        report(args.timeout)


if __name__ == "__main__":
    main()
