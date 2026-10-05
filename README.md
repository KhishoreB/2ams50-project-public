# 2AMS50 Project: Public Transport Line Planning

This repository contains the optimization pipeline and benchmark evaluation suite for the **Public Transport Line Planning Problem (LPP)** using **LinTim** benchmark instances, developed for the TU/e course *2AMS50 Optimization for Data Science*.

---

## 1. Directory Layout

```
line_planning/
├── data/                      # Benchmark datasets downloaded from OpenLinTim
│   ├── Global-Config.cnf      # Global default LinTim configuration
│   ├── toy/                   # 8 stops, 8 edges (unit test / validation)
│   ├── mandl/                 # 15 stops, 21 edges (classic literature benchmark)
│   ├── sioux_falls/           # 24 stops, 38 edges (standard transportation network)
│   ├── grid/                  # 25 stops, 40 edges (regular grid topology)
│   └── athens/                # 51 stops, 52 edges (real metro system)
├── src/
│   ├── parser.py              # LinTim .giv and .cnf parser into Python dataclasses
│   ├── pool_generator.py      # Candidate line pool generation (k-shortest simple paths)
│   ├── utils.py               # Graph adjacency, path reconstruction, LinTim cost formulas
│   ├── validator.py           # Evaluation engine: feasibility, costs, direct passenger %
│   ├── models/
│   │   └── cost_mip.py        # Baseline Cost-Minimizing Line Planning MIP (SCIP & Gurobi)
│   └── heuristics/            # (Heuristic methods developed by Students 4 & 5)
└── scripts/
    ├── download_data.py       # Script to download benchmark data from GitLab
    ├── verify_datasets.py     # Script to check integrity of all downloaded datasets
    ├── run_baseline.py        # Quick test of baseline MIP on toy and mandl
    └── run_benchmarks.py      # Full benchmark suite across all 5 datasets (LaTeX table output)
```

---

## 2. 5-Person Team Role Mapping & Defense Ownership

Each student owns one **method** (developed and implemented by them, satisfying the "every member develops solution methods" rubric line), one **report section** (they draft it, and are the named owner in the contributions section), and one **defense topic**. Students are paired so that no method has a single point of failure: the pair members can each answer the other's defense questions.

| Student | Method (implemented by them) | Report section drafted | Key File(s) | Defense Topic | Pair |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Student 1** | **Data & Baseline MIP**: LinTim ingestion, feasibility validation, baseline Cost-MIP on toy/mandl | § Results (presentation, tables, plots) | `parser.py`, `validator.py`, `models/cost_mip.py` | LPP problem space, graph representations, baseline optimality | S2 |
| **Student 2** | **Formulations & Strengthening**: budget variant (RQ2) and min-transfer variant (RQ3); formulation strength (Ch 4.4); valid inequalities (Ch 4.3) *after verifying LP relaxation weakness* (gap of LP vs. IP on Mandl; commit to `cuts_mip.py` only if the gap justifies it) | § Problem Formulation (Models A/B vs. literature) | `models/strong_formulation.py`, `models/cuts_mip.py` | Formulation strength, LP relaxation tightness, branch-and-cut | S3 |
| **Student 3** | **Column Generation**: Dantzig–Wolfe decomposition (Ch 3), Restricted Master Problem, pricing subproblem (constrained shortest path) on Sioux Falls/Athens | § Solution Methods (exact) | `models/column_generation.py` | Reduced cost theory, shadow prices, dynamic column generation | S2 |
| **Student 4** | **Greedy Heuristics**: demand-driven pool generation, greedy direct-traveler selection, LP rounding; runs the Pareto budget sweep for RQ2 | § Solution Methods (heuristics) | `pool_generator.py`, `heuristics/greedy_pool.py` | Greedy algorithms, LP relaxation rounding, approximation quality | S5 |
| **Student 5** | **Improvement Metaheuristic (LNS)**: destroy/repair operators, simulated annealing, scaling on Göttingen | § Literature Study + report assembly + AI-usage declaration | `heuristics/lns.py` | Metaheuristics, neighborhood structures, anytime optimization | S4 |

**Defense-pairing rules.** (S1, S2) cover the formulation/MIP side for each other; (S4, S5) cover the heuristic side. S3's column generation is the most defense-sensitive topic, so S2 must be able to explain reduced costs and pricing fluently even though S3 owns the implementation. Student 5's literature-study ownership doubles as defense insurance: having surveyed the literature, they can contextualize every other method.

**Every-student-runs-experiments rule.** Beyond their own method, each student executes and documents at least one run of another method (logged in the contributions table of the report): S1 runs the LNS on Athens, S2 runs the greedy on Mandl, S3 runs the baseline MIP on toy, S4 runs column generation on Sioux Falls, S5 runs the baseline MIP on Mandl.

1. Hand-solve the toy instance (week 1, everyone). Take the toy dataset, generate the pool by hand, pick lines, check frequency bounds and capacity by hand, compute the cost. One evening each. Anyone who has done this can reconstruct the whole model on a whiteboard — the single best defense insurance there is.
2. Walk the iron route once. Clone the repo, run verify_datasets.py → run_baseline.py → run_benchmarks.py, and read the console output until they can explain every number the validator prints (cost, feasibility, direct-passenger %). Understanding the pipeline end-to-end matters more than any one person's module.
3. Core reading, minimal set. Schöbel (2012) survey + one column-generation source for everyone, so duality/reduced-cost talk isn't S3-and-S2's private language. Plus each member reads one paper closely in their own area (S4/S5: Mandl 1979 + one metaheuristic paper; S2: a formulation-strength paper; S1: the LinTim documentation).
4. Model walkthrough session. After S2 freezes Model A, everyone redoes the constraint derivation once from the data files (where does $\underline f_e$ come from? why is the capacity constraint a product?). Weak formulations get caught here, not in week 4.
5. Mock defenses in week 6. Each member gets 15 minutes of questions from the others on a section they did not write, using the rubric's own questions (which techniques? which problem class? benefits/drawbacks of the models?). Repeat whatever fails.
Plus the two structural rules already in the README: the cross-experiment rule (each member runs another member's method) and a shared logbook where each entry names who did what — that becomes the contributions section almost verbatim.

---

## 3. Quick Start & Execution

Ensure you are using the virtual environment:
```bash
# Verify datasets integrity
.venv/bin/python scripts/verify_datasets.py

# Run quick baseline test on toy and mandl
.venv/bin/python scripts/run_baseline.py

# Run full benchmark suite across all 5 LinTim datasets
.venv/bin/python scripts/run_benchmarks.py
```
