"""Question 6 : comparaison reproductible des deux interfaces sat.py.

    python bench_q6.py run --timeout 60
    python bench_q6.py report

Le temps wall inclut Python, les imports, la lecture, la résolution et la
sortie du modèle. Les temps CPU/solve_wall concernent uniquement solve().
Les processus sont lancés l'un après l'autre pour limiter la contention.
"""

import argparse
import csv
import hashlib
import json
import math
import platform
import statistics
import subprocess
import sys
import time
from pathlib import Path

from bench_q5 import build_meowdoku_instances, expected_statuses, read_runs
from dimacs import check_model, read_dimacs
from dpll import SAT, UNSAT

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results/q6_runs.csv"
GENERATED = ROOT / "rapports/question6/generated"
FIELDS = ["family", "instance", "nb_vars", "nb_clauses", "mode", "repeat",
          "seed", "expected", "status", "correct", "wall", "solve_cpu",
          "solve_wall", "decisions", "backtracks", "unit_propagations",
          "pure_literals", "heuristic_time", "timeout", "error"]


def parse_output(stdout, nb_vars, clauses):
    """Valide le protocole et le modèle complet sans faire confiance au solveur."""
    lines = stdout.strip().splitlines()
    if lines == ["s UNSATISFIABLE"]:
        return UNSAT
    if len(lines) != 2 or lines[0] != "s SATISFIABLE":
        raise ValueError("format de résultat invalide")
    tokens = lines[1].split()
    if not tokens or tokens[0] != "v" or tokens[-1] != "0":
        raise ValueError("ligne de modèle invalide")
    literals = list(map(int, tokens[1:-1]))
    if sorted(map(abs, literals)) != list(range(1, nb_vars + 1)):
        raise ValueError("modèle incomplet, répété ou hors limites")
    model = {abs(lit): lit > 0 for lit in literals}
    if not check_model(clauses, model):
        raise ValueError("modèle ne satisfaisant pas la formule")
    return SAT


def instances(suite):
    result = []
    if suite in ("all", "public"):
        expected = json.loads((ROOT / "public-instances/expected.json").read_text())
        for path in sorted((ROOT / "public-instances/instances").glob("*.cnf")):
            family = "public" if path.name.startswith("public-") else "interface"
            result.append((family, path, expected[path.name]))
    if suite in ("all", "meowdoku"):
        # Statuts de la campagne Q5, vérifiés entre les 16 heuristiques.
        expected = expected_statuses(read_runs())
        for family, path in build_meowdoku_instances():
            status = SAT if family == "meow" else expected.get(path.name)
            if status not in (SAT, UNSAT):
                raise ValueError(f"statut de référence absent pour {path}")
            result.append((family, path.resolve(), status))
    return result


def measure(family, path, expected, mode, repeat, timeout):
    n, clauses = read_dimacs(path)
    seed = int(hashlib.sha256(path.name.encode()).hexdigest()[:8], 16)
    row = {key: "" for key in FIELDS}
    row.update(family=family, instance=path.name, nb_vars=n,
               nb_clauses=len(clauses), mode=mode, repeat=repeat, seed=seed,
               expected=expected, correct=False, timeout=timeout)
    command = [sys.executable, str(ROOT / "sat.py"), str(path), "--mode", mode,
               "--output-model", "--stats", "--seed", str(seed)]
    start = time.perf_counter()
    try:
        process = subprocess.run(command, capture_output=True, text=True,
                                 timeout=timeout, cwd=ROOT)
        row["wall"] = time.perf_counter() - start
        if process.returncode:
            raise ValueError(f"code {process.returncode}: {process.stderr.strip()[:250]}")
        row["status"] = parse_output(process.stdout, n, clauses)
        if row["status"] != expected:
            raise ValueError(f"statut {row['status']}, attendu {expected}")
        stats = json.loads(process.stderr)
        row["solve_cpu"] = stats["solve_cpu_s"]
        row["solve_wall"] = stats["solve_wall_s"]
        for key in ("decisions", "backtracks", "unit_propagations", "pure_literals", "heuristic_time"):
            row[key] = stats[key]
        row["correct"] = True
    except subprocess.TimeoutExpired:
        row.update(status="TIMEOUT", wall=time.perf_counter() - start)
    except (ValueError, KeyError) as error:
        row.update(status="ERROR", error=str(error), wall=time.perf_counter() - start)
    return row


def run(args):
    corpus = instances(args.suite)
    args.csv.parent.mkdir(parents=True, exist_ok=True)
    metadata = {"python": platform.python_version(), "platform": platform.platform(),
                "machine": platform.machine(), "timeout": args.timeout,
                "repeats": args.repeats, "suite": args.suite, "instances": len(corpus),
                "timing": "sequential subprocess wall time, including model output",
                "modes": args.modes}
    args.csv.with_suffix(".json").write_text(json.dumps(metadata, indent=2) + "\n")
    total = len(corpus) * args.repeats * len(args.modes)
    errors = 0
    with args.csv.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        done = 0
        for repeat in range(args.repeats):
            for family, path, expected in corpus:
                # Alterne l'ordre lors des répétitions pour limiter un biais thermique.
                modes = args.modes if repeat % 2 == 0 else list(reversed(args.modes))
                for mode in modes:
                    row = measure(family, path, expected, mode, repeat, args.timeout)
                    writer.writerow(row)
                    stream.flush()
                    done += 1
                    errors += row["status"] == "ERROR"
                    print(f"[{done:3}/{total}] {path.name:32} {mode:9} "
                          f"{row['status']:8} {row['wall']:.4f} s", flush=True)
    print(f"Résultats : {args.csv} ({errors} erreur(s))")
    return 1 if errors else 0


def load_rows(path):
    with path.open(encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        row["correct"] = row["correct"] == "True"
        for key in ("wall", "timeout", "solve_cpu", "solve_wall"):
            row[key] = float(row[key]) if row[key] else None
    return rows


def geometric_mean(values):
    return math.exp(statistics.mean(math.log(max(value, 1e-9)) for value in values))


def summary(rows):
    result = []
    for mode in sorted({r["mode"] for r in rows}):
        selected = [r for r in rows if r["mode"] == mode]
        solved = [r for r in selected if r["correct"]]
        result.append({"mode": mode, "solved": len(solved), "total": len(selected),
                       "timeouts": sum(r["status"] == "TIMEOUT" for r in selected),
                       "errors": sum(r["status"] == "ERROR" for r in selected),
                       "time": sum(r["wall"] for r in solved),
                       "median": statistics.median(r["wall"] for r in solved) if solved else 0,
                       "par2": statistics.mean(r["wall"] if r["correct"] else 2*r["timeout"]
                                               for r in selected)})
    return result


def paired_gains(rows):
    by_key = {(r["instance"], r["repeat"], r["mode"]): r for r in rows}
    pairs = []
    for r in rows:
        if r["mode"] != "dpll" or not r["correct"]:
            continue
        other = by_key.get((r["instance"], r["repeat"], "optimized"))
        if other and other["correct"]:
            pairs.append((r, other))
    if not pairs:
        return None
    return {"pairs": len(pairs),
            "wall": geometric_mean([a["wall"]/b["wall"] for a,b in pairs]),
            "cpu": geometric_mean([max(a["solve_cpu"], 1e-9)/max(b["solve_cpu"], 1e-9)
                                   for a,b in pairs])}


def report(args):
    rows = load_rows(args.csv)
    if not rows:
        raise ValueError("aucune mesure")
    generated = args.generated or (GENERATED if args.csv.resolve() == RESULTS else
                                  args.csv.parent / (args.csv.stem + "_report"))
    generated.mkdir(parents=True, exist_ok=True)
    groups = [("Ensemble", rows)]
    for family, name in [("public", "Benchmarks publics"), ("interface", "Interface et cas limites"),
                         ("meow", "Meowdoku SAT"), ("meowr", "Régions aléatoires")]:
        selected = [r for r in rows if r["family"] == family]
        if selected:
            groups.append((name, selected))
    table = [r"\begin{tabular}{llrrr}", r"\toprule",
             r"Corpus & Mode & Résolus / essais & Temps total (s) & PAR-2 (s) \\", r"\midrule"]
    for name, selected in groups:
        print(f"\n{name}")
        for s in summary(selected):
            print(f"  {s['mode']:9} {s['solved']}/{s['total']} corrects, "
                  f"{s['timeouts']} timeout(s), {s['errors']} erreur(s), "
                  f"total résolus {s['time']:.3f} s, PAR-2 {s['par2']:.3f} s")
            table.append(f"{name} & {s['mode']} & {s['solved']}/{s['total']} & "
                         f"{s['time']:.3f} & {s['par2']:.3f}" + r" \\")
        gains = paired_gains(selected)
        if gains:
            print(f"  Gain géométrique dpll/optimized sur {gains['pairs']} paires : "
                  f"x{gains['wall']:.2f} (processus complet), x{gains['cpu']:.2f} (CPU solveur)")
    table += [r"\bottomrule", r"\end{tabular}"]
    (generated / "synthese.tex").write_text("\n".join(table) + "\n")
    sizes = [r"\begin{tabular}{rrrrr}", r"\toprule",
             r"Taille & CPU DPLL (ms) & CPU optimisé (ms) & Processus DPLL (ms) & Processus optimisé (ms) \\",
             r"\midrule"]
    for n in sorted({int(r["nb_vars"]) for r in rows if r["family"] == "meow"}):
        medians = []
        for field in ("solve_cpu", "wall"):
            for mode in ("dpll", "optimized"):
                values = [r[field]*1000 for r in rows if r["family"] == "meow"
                          and int(r["nb_vars"]) == n and r["mode"] == mode and r["correct"]]
                medians.append(f"{statistics.median(values):.2f}" if values else "--")
        sizes.append(str(math.isqrt(n)) + " & " + " & ".join(medians) + r" \\")
    sizes += [r"\bottomrule", r"\end{tabular}"]
    (generated / "tailles.tex").write_text("\n".join(sizes) + "\n")
    for mode in ("dpll", "optimized"):
        times = sorted(r["wall"] for r in rows if r["mode"] == mode and r["correct"])
        (generated / f"cactus-{mode}.dat").write_text("wall solved\n" + "".join(
            f"{duration:.8f} {i}\n" for i, duration in enumerate(times, 1)))
    write_analysis(rows, generated)
    print(f"\nTableaux et courbes : {generated}")
    return 1 if any(r["status"] == "ERROR" for r in rows) else 0


def write_analysis(rows, generated):
    """Les commentaires chiffrés du rapport dérivent aussi du CSV."""
    overview = {s["mode"]: s for s in summary(rows)}
    gains = paired_gains(rows)
    global_text = []
    if {"dpll", "optimized"} <= overview.keys():
        a, b = overview["dpll"], overview["optimized"]
        global_text.append(f"Le mode optimisé obtient {b['solved']}/{b['total']} résolutions correctes, "
                           f"contre {a['solved']}/{a['total']} pour DPLL. "
                           f"La campagne compte {a['errors'] + b['errors']} erreur(s) de statut, "
                           "de modèle ou d'interface.")
        for mode in ("dpll", "optimized"):
            names = sorted({r["instance"].replace("_", r"\_") for r in rows
                            if r["mode"] == mode and r["status"] == "TIMEOUT"})
            if names:
                global_text.append("Dépassements de délai (" + mode + ") : " +
                                   ", ".join(r"\texttt{" + name + "}" for name in names) + ".")
        if gains:
            global_text.append(f"Sur les {gains['pairs']} paires résolues par les deux modes, "
                               f"la moyenne géométrique du rapport DPLL/optimisé vaut "
                               f"{gains['wall']:.2f} pour le temps complet et {gains['cpu']:.2f} "
                               "pour le temps CPU de résolution.")
        other = {(r["instance"], r["repeat"]): r for r in rows
                 if r["mode"] == "optimized" and r["correct"]}
        losses = [(other[(r["instance"], r["repeat"])]["wall"] / r["wall"], r["instance"])
                  for r in rows if r["mode"] == "dpll" and r["correct"]
                  and (r["instance"], r["repeat"]) in other]
        if losses and max(losses)[0] > 2:
            ratio, name = max(losses)
            global_text.append(r"Le gain n'est pas uniforme : sur \texttt{" + name.replace("_", r"\_") +
                               f"}}, le mode optimisé est {ratio:.1f} fois plus lent en temps complet "
                               "pour cette graine de DPLL.")
    (generated / "analyse-globale.tex").write_text("\n".join(global_text) + "\n")
    selected = [r for r in rows if r["family"] in ("meow", "meowr")]
    gains = paired_gains(selected)
    text = []
    if gains:
        text.append(f"Sur les {gains['pairs']} paires Meowdoku résolues par les deux modes, "
                    f"le gain géométrique est de \\textbf{{{gains['cpu']:.1f} fois}} "
                    f"sur le temps CPU du solveur, contre \\textbf{{{gains['wall']:.1f} fois}} "
                    "sur le temps complet. Le démarrage de Python et la lecture de la CNF "
                    "réduisent donc le gain visible de bout en bout.")
        by_mode = {s["mode"]: s for s in summary(selected)}
        b = by_mode["optimized"]
        text.append(f"Le mode optimisé réussit {b['solved']}/{b['total']} résolutions Meowdoku.")
    (generated / "analyse-meowdoku.tex").write_text("\n".join(text) + "\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    run_parser = sub.add_parser("run", help="Lance les deux modes et vérifie leurs sorties")
    run_parser.add_argument("--timeout", type=float, default=60)
    run_parser.add_argument("--repeats", type=int, default=1)
    run_parser.add_argument("--suite", choices=("all", "public", "meowdoku"), default="all")
    run_parser.add_argument("--modes", nargs="+", choices=("dpll", "optimized"), default=["dpll", "optimized"])
    run_parser.add_argument("--csv", type=Path, default=RESULTS)
    report_parser = sub.add_parser("report", help="Affiche la synthèse des mesures enregistrées")
    report_parser.add_argument("--csv", type=Path, default=RESULTS)
    report_parser.add_argument("--generated", type=Path,
                               help="Dossier des tableaux (par défaut, séparé pour un CSV alternatif)")
    args = parser.parse_args(argv)
    if args.command == "run" and (args.timeout <= 0 or not math.isfinite(args.timeout) or args.repeats < 1):
        parser.error("timeout doit être fini et positif ; repeats doit être au moins 1")
    # Les générateurs Q5 utilisent des chemins relatifs au projet.
    import os
    os.chdir(ROOT)
    return run(args) if args.command == "run" else report(args)


if __name__ == "__main__":
    sys.exit(main())
