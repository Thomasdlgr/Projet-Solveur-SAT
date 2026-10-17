# Public SAT solver tests

These DIMACS CNF files are published so that you can test your solver and the command-line interface required by Question 6 on your own machine. The directory `instances/` contains 41 files:

- 5 small interface tests (`cli_model_sat`, `smoke_*`, `unit_*`).
- 6 edge cases (`edge_*`) that a correct solver must not miss: empty formula, formula without clauses, empty clause, tautological clause, repeated literals, only negative literals. The first comment line of each file says what it tests.
- 30 benchmark instances (`public-01` to `public-30`), 19 SAT and 11 UNSAT, of various kinds and sizes (random 3-SAT, graph colouring, planning, circuit analysis, parity learning, inductive inference, pigeon hole, quasigroups, ...), from 42 to 1363 variables. They come from the SATLIB benchmark library (H. H. Hoos and T. Stützle, *SATLIB: An Online Resource for Research on SAT*, SAT 2000). Most are solved in well under a second by a reasonable solver; a few are noticeably harder for a basic DPLL, and two are deliberately hard: even a well-optimized DPLL solver may need several tens of seconds for them, close to the competition time limit.

Example:

```bash
python sat.py public-instances/instances/smoke_01_sat.cnf --mode optimized --output-model
```

`expected.json` gives the correct SAT/UNSAT result for every file in `instances/`. For a SAT instance, the model printed with `--output-model` must also satisfy every clause of the formula.

These files are not used for the official competition ranking.
