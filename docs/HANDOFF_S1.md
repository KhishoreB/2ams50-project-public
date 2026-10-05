# Handoff — Student 1 (Baselines & Benchmark Framework)

Status as of the Oct 5 check-in. Parser/validator reviewed, canonical cost fixed,
MIP gap surfaced, machine-readable baseline artifacts exported for Student 3.

## For Student 3 (column generation handoff)

Baseline artifacts are written under `results/`:

- `results/baseline_toy.json`, `results/baseline_mandl.json` — exact pool + frequencies + validated cost
- `results/benchmarks.json` — all five datasets

Each record contains:

- `lines[]`: `id, edges, nodes, length, cost, frequency`
- `cost_params`: `fixed, per_length, per_edge`
- `solver`: `status, objective, solve_time_seconds, mip_gap`
- `validation`: `is_feasible, direct_traveler_percentage, min/max_frequency_violations, ...`

To seed the RMP: load a record, rebuild the pool from `lines[]`, and use the
recorded frequencies as a start. `src/reporting.py` builds these records.

### API notes (both changed)

- `solve_cost_mip(...)` now returns a 5-tuple:
  `(frequencies, objective, solve_time, status, gap)`.
- `evaluate_line_plan(...)` raises `ValueError` if the `frequencies` key set does
  not match the pool you pass. Pass the same pool you solved.

### Cost convention

Canonical for every pool (given and generated):

```
c_l = lpool_costs_fixed + lpool_costs_length * length(l) + lpool_costs_edges * |edges(l)|
```

parameters read from each dataset's `Config.cnf` (`lpool_costs_*`), defaulting to
`50 / 0.05 / 0.05` from `Global-Config.cnf`. Use `utils.compute_line_cost` and
`utils.line_cost_params` in the pricing subproblem so reduced costs share the scale.

## Group status

Baseline table, all optimal, MIP gap 0:

| Dataset | $\lvert V \rvert$ | $\lvert E \rvert$ | Pool | Cost | MIP Gap | Lines | Direct % | CPU (s) |
| --- | --: | --: | --: | --: | --: | --: | --: | --: |
| toy | 8 | 8 | 8 | 703.80 | 0.0000 | 5 | 85.4 | 0.0008 |
| mandl | 15 | 21 | 154 | 1933.32 | 0.0000 | 13 | 85.1 | 0.0026 |
| sioux_falls | 24 | 38 | 681 | 3893.72 | 0.0000 | 31 | 73.2 | 0.0444 |
| grid | 25 | 40 | 723 | 812.15 | 0.0000 | 15 | 78.9 | 0.2715 |
| athens | 51 | 52 | 59 | 1886.63 | 0.0000 | 13 | 46.6 | 0.0020 |

Numbers are from `scripts/run_benchmarks.py` (source of truth); regenerate with
`.venv/bin/python scripts/run_benchmarks.py`.

### What changed from the old walkthrough

toy and athens moved because given pools now use the config cost formula instead of
the stored `Pool-Cost.giv` (which used a different, dataset-specific convention):

- toy: cost 51.20 → 703.80 (direct unchanged 85.4%)
- athens: cost 408.17 → 1886.63, direct 39.7% → 46.6%

`walkthrough.md` still quotes the old athens 39.70% and should be treated as stale.

## Open items for S1

- Frequency-bound policy: when `Load.giv` exists it overrides `Edge.giv` entirely,
  so the track-capacity upper bound is effectively off (e.g. toy edge 5, `Edge.giv`
  cap 2, `Load.giv` max 20). Justify in the report or fix.
- Direct-traveler metric in `validator.py` is binary connectivity over node sets:
  ignores direction, frequency and capacity (Schöbel-style). Document in the report.
- `results/` is currently untracked; decide whether handoff artifacts belong in git.
