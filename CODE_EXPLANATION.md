# Code explanation: line-planning heuristics

This guide describes the implementation included in this update. It explains what the code currently does, including its limitations. It is implementation documentation, not a final project report.

## 1. Purpose and inputs

The code chooses operating frequencies for candidate public-transport lines within a budget. It compares greedy construction with LP rounding followed by greedy repair across several budgets.

A **stop** is a network node. An **edge** connects stops. A **line** is a simple path through the network. Its **frequency** is the number of times it operates during the planning period. An **OD pair** identifies an origin and destination and its passenger demand.

The implementation receives a `PTNInstance` from the shared parser and a dictionary of candidate `Line` objects. It relies on the existing repository's parser, utilities, validator, pool generator and, for Gurobi/SCIP, cost model. This ZIP is an update to that repository, not a standalone project.

| Input | How it is used |
|---|---|
| Stops and edges | Validate the network and candidate paths |
| OD matrix | Measure demand covered by active lines |
| Candidate pool | Supply the lines the heuristic may select |
| Cost per line | Calculate cost for each frequency unit |
| Effective edge-frequency bounds | Enforce minimum and maximum edge service |
| Budget | Limit the total operating cost |

Total cost is the sum of `line.cost * frequency` across selected lines. A frequency of zero means the line is inactive.

## 2. What the service score means

The score is **direct-demand coverage**: an OD pair is covered if both endpoints occur on at least one active line. Its demand is counted once even if several lines cover it. The code assumes an undirected network.

For example, if demand from A to C is 100 and an active line visits A, B and C, those 100 units count as covered. Adding a second line covering the same pair adds zero new coverage. Adding a line covering another previously uncovered pair with demand 60 adds 60.

This measure does not allocate passengers to vehicles. It does not certify capacity-feasible passenger transport, waiting times, or transfer counts. Increasing an already active line's frequency does not improve this coverage score, though it may be needed to meet edge-frequency requirements.

## 3. Files and responsibilities

| File | Responsibility |
|---|---|
| `src/heuristics/greedy_pool.py` | Validate the problem, build a frequency plan, repair deficits and improve coverage |
| `src/heuristics/lp_rounding.py` | Solve the continuous cost relaxation and convert its frequencies into an integer heuristic plan |
| `src/heuristics/budget_sweep.py` | Run both methods over a sorted budget grid and retain the best feasible results |
| `src/heuristics/input_audit.py` | Check that frequency inputs will not trigger the shared helper's problematic fallback |
| `scripts/run_budget_sweep.py` | Load datasets, prepare pools, run experiments and save results |
| `scripts/run_column_generation_check.py` | Run the existing column-generation implementation with an external time limit |
| `tests/test_heuristics.py` | Test the main algorithm behaviours and input checks |

The update uses the shared `pool_generator.py`; it does not include a replacement candidate-generation algorithm.

## 4. Greedy construction in detail

### `PoolProblem`

This class prepares consistent views of the inputs. It checks the network, nonnegative finite OD demand and line costs, line IDs, and contiguous simple paths. It reconstructs line nodes from their edge sequences and copies lines so that the caller's pool is not mutated.

It builds `cover`, which maps each line to the OD pairs whose endpoints it contains. It also obtains integer frequency bounds through the shared `effective_frequency_bounds` helper. Under this implementation, an effective upper bound of zero means no upper bound.

Useful methods calculate total cost, edge frequencies, and the union of covered OD pairs. `check_seed` checks any supplied initial frequency dictionary for unknown lines and nonnegative integer values.

### `greedy_select`

The function runs the following phases:

1. **Validate the starting plan.** Start from zero frequencies or a supplied seed. Reject a seed that exceeds the budget or an effective upper bound. Detect required edges not covered by any candidate line.
2. **Repair minimum edge frequencies.** Consider adding one frequency unit to each candidate line. An increment must fit the budget and every affected upper bound. Its repair score is the number of currently deficient edges it helps, divided by its cost. Ties prefer greater newly covered demand, then lower cost, then lower line ID. Update the selected line, its edge frequencies, cost and covered OD pairs.
3. **Remove redundant frequency units.** Visit active lines from highest cost to lowest. Reduce frequencies while retaining at least one unit on each active line and preserving all minimum edge requirements. Keeping every active line preserves coverage.
4. **Improve service.** Consider inactive lines that fit the remaining budget and upper bounds. Select the line with the greatest newly covered demand per unit cost. Ties prefer greater demand gain, then lower cost and lower line ID. Repeat until no admissible positive-gain line remains.
5. **Evaluate the result.** Call the shared validator and separately check the budget.

`_fits` checks whether an increment is allowed; `_add` applies it. `_ratio` handles zero-cost choices without division by zero. `make_result` packages the final evaluation and elapsed time.

The algorithm has no backtracking. A locally attractive choice can prevent a later necessary increment, so construction failure does not prove the instance infeasible. No theoretical approximation ratio is claimed.

## 5. LP rounding in detail

### `solve_cost_relaxation`

This function minimizes operating cost while allowing continuous, nonnegative line frequencies. It enforces the same effective edge-frequency lower and upper bounds used by the heuristic.

For `gurobi`, `scip` or `auto`, it calls the shared `solve_cost_mip` with `integer=False`. The `scipy` backend constructs the corresponding linear inequalities and uses `linprog`. An optimal LP objective is a lower bound on the minimum integer cost for the same instance and pool.

This is a **cost LP**. It is not an LP maximizing passenger coverage under a budget, and its objective is not an upper bound on service quality.

### `lp_rounding`

The function can solve a new LP or reuse a supplied relaxation of the same instance and pool.

- If the LP is infeasible, return `lp_infeasible`.
- If the budget is below the optimal LP cost, return `budget_below_lp_bound`.
- If the LP is optimal, round its nonnegative frequencies down and use them as the greedy seed.
- Repair minimum frequencies and improve coverage through `greedy_select`.
- If that construction fails, or an optimal LP solution was unavailable, try greedy construction from zero and record `fallback_used`.

For example, frequencies 2.7, 0.8 and 1.2 produce a seed of 2, 0 and 1. Rounding down may leave edge deficits; the repair phase is necessary. The fallback means an output labelled `lp_rounding` can ultimately come from a fresh greedy run, which is disclosed in its details.

## 6. Budget sweep

`run_budget_sweep` sorts and removes duplicate budgets, solves the cost LP once, and then runs greedy and LP rounding at each budget.

Each method keeps its own best feasible solution. A new solution replaces it if coverage is higher, or coverage is equal and cost is lower. Otherwise the earlier plan remains available at the larger budget.

Every record stores both the fresh trial (`raw`) and retained solution (`best_feasible`). `selected_from_budget` identifies where the retained plan was found; `carried_forward` indicates reuse. Consequently retained coverage cannot decrease with budget, even though fresh greedy trials can perform worse or fail.

This is a discrete budget-grid experiment, not a proof of the exact Pareto frontier. The shared LP time is recorded separately; do not add that same time repeatedly when calculating the total sweep runtime.

## 7. Input audit and safeguards

`audit_lintim_frequency_inputs` checks for missing `Load.giv` rows and nonpositive load bounds. The latter need explicit interpretation because the shared helper can substitute edge values when a load bound is zero.

In the documented shared pipeline, `Edge.giv` travel-time bounds can incorrectly become frequency bounds. The standard CLI stops when the audit detects this risk. `--allow-legacy-frequency-bounds` allows diagnostic reproduction; it does not fix the data or validate the resulting benchmark.

The budget runner also checks generated paths against `--max-edges`. Normal runs reject overlong paths. Diagnostic runs can retain them to reproduce the previously used pool.

Calling the low-level heuristic functions directly does not run the LinTim input audit automatically. Use the runner or call the audit explicitly before interpreting real-data results.

## 8. Running and reading the outputs

Run these commands from the existing repository root after extracting the update:

```bash
python -m pip install -r requirements-heuristics.txt
python -m pip install gurobipy
python -m unittest discover -s tests -p 'test_heuristics.py' -v
python scripts/run_budget_sweep.py --datasets toy --pool-source existing --reference-cost 703.8 --factors 1 1.25 1.5 2 --solver gurobi --plot
```

Gurobi requires a working licence. The supplied reference cost determines the budget grid; specifying a number does not establish that it is an optimum. To choose budgets directly, use `--budgets` instead of `--reference-cost` and `--factors`.

The default output directory is `results/heuristics/<dataset>/`.

| Output | Contents |
|---|---|
| `budget_sweep.csv` | Compact comparison of budgets, trial status, costs, selected coverage and timing |
| `budget_sweep.json` | Full frequencies, pool, raw and retained results, LP statistics, input audit, arguments and source/input hashes |
| `budget_coverage.png` | Retained direct-demand coverage versus budget, created with `--plot` |

`HeuristicResult.feasible` means both shared frequency feasibility and budget feasibility. It does not mean full passenger-routing feasibility. Important statuses are:

| Status | Meaning |
|---|---|
| `feasible` | Frequency and budget checks passed |
| `construction_failed` | No admissible greedy repair increment remained |
| `pool_infeasible` | A required edge has no candidate line |
| `lp_infeasible` | The continuous cost model is infeasible |
| `budget_below_lp_bound` | The budget is below the optimal continuous cost |

For another method such as LNS, use `best_feasible.frequencies` together with the serialized pool. `best_feasible` may be null. JSON dictionary keys are strings, so convert line IDs back to integers when needed.

## 9. Column-generation wrapper and tests

`run_column_generation_check.py` runs the shared column-generation routine in a separate process. It terminates the process if the external wall-clock limit expires and records that status. A completed run concerns a continuous cost LP; the wrapper does not provide branch-and-price or guarantee an integer solution.

The 20 tests in `test_heuristics.py` cover fractional LP repair, a small enumerated integer optimum, overlapping coverage without double counting, budget and upper bounds, missing required edges, invalid paths and inputs, zero-cost behaviour, deterministic budget sweeps, fallback reporting and the real-input audit. One test explicitly checks that coverage must not be interpreted as capacity certification.

## 10. Recorded status and remaining work

The supplied package records toy results of cost 703.80 and coverage 86.9565% for both methods at the four tested budgets. Mandl and Sioux Falls outputs remain historical diagnostics because of the documented frequency-input problem. These are recorded results, not new runs performed when adding this guide.

Before drawing final benchmark conclusions, correct the frequency inputs, agree the intended service metric, and rerun comparisons using identical candidate pools, costs and bounds. Capacity-aware passenger service requires additional modelling beyond the current coverage proxy. The guide documents existing code; no solver logic was changed.
