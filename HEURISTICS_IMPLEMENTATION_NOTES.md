# Code walkthrough and handoff notes

These notes explain the delivered code. They are not an assessed report section.

## Follow the code in this order

1. `parser.py`: `PTNInstance` stores the graph, OD matrix, config and line pool.
   A line ID identifies a path; a frequency dictionary says how often it runs.
2. `utils.py`: inspect `effective_frequency_bounds` and `compute_line_cost`.
   All compared methods must use the same resolved bounds and costs.
3. `greedy_pool.py`: `PoolProblem` resolves path nodes, rejects invalid input and
   builds sets of OD pairs covered by each line. A set prevents double counting.
4. `greedy_select`: repair deficient edge frequencies first. One increment on a
   line supplies one extra frequency to every edge on that line. A candidate must
   fit both the remaining budget and all effective upper bounds.
5. When all minimum frequencies hold, remove redundant frequency units above
   one per active line. This preserves coverage and saves budget where possible.
6. The service loop adds the inactive line with the largest additional covered
   demand per unit cost. Covered OD demand is recomputed marginally. Extra copies
   of an already active line do not increase the supplied validator's metric.
7. `lp_rounding.py`: the LP permits fractional frequencies. Floor them, then call
   the same repair routine. Rounding alone does not make a solution feasible.
8. `budget_sweep.py`: solve the cost LP once; run both methods at each budget;
   retain a previous feasible result if a fresh trial is worse or fails.

## Test case to trace by hand

The triangle regression case has three edges, minimum frequency one per edge,
and three candidate lines, each using two edges at cost one. Frequency 0.5 on
each line covers every edge once at cost 1.5. Integer frequencies require at least
two lines, costing 2. Floor rounding initially produces zeros, so repair is needed.
The tests enumerate all frequencies 0, 1, 2 for those three lines and confirm the
integer minimum is 2. This is a synthetic regression example, not the LinTim toy.

## Status meanings

| Status | Interpretation |
| --- | --- |
| `feasible` | Passed the shared frequency check and the separate budget check |
| `construction_failed` | Greedy found no next admissible increment; not proof of infeasibility |
| `pool_infeasible` | A required edge has no line in this pool |
| `lp_infeasible` | Continuous cost model reported infeasible, implying no integer solution under the same model |
| `budget_below_lp_bound` | Budget below the optimal continuous minimum cost |

For example, a budget of 1.6 in the triangle lies above the LP value but below
the integer optimum. The heuristic reports construction failure; it does not
turn that failure into an infeasibility certificate. The exhaustive test, not
the greedy method, establishes the integer optimum in that tiny example.

## Determinism and limitations

Tie breaking uses gain, cost and line ID. There is no random seed because these
methods are deterministic given a fixed pool. LP solvers can still choose different
optimal fractional solutions, changing rounding outcomes.

The feasibility phase can choose a cheap line that later blocks another edge
through an upper bound. There is no backtracking. LP-floor repair can suffer the
same issue; a restart from zero is recorded as `fallback_used`. There is no claimed
approximation ratio. Higher budgets can produce worse fresh greedy constructions;
the explicitly recorded incumbent makes the selected curve nondecreasing.

The implementation increments frequencies one unit at a time. Its repair loop is
bounded by the sum of remaining integer edge deficits, since each iteration
reduces at least one deficit. The service loop activates at most the pool size.
This is appropriate for the planned small/medium experiments, not a claim of
scalability to the largest benchmark networks.

The budget grid samples service levels. It does not prove that every efficient
cost/service trade-off has been found. Actual cost can be less than the budget.

## What to ask teammates when integrating

- Is an OD pair counted just by endpoints on one line, or by an explicit feasible
  passenger assignment subject to per-line capacity?
- Does minimum edge service remain mandatory at every RQ2 budget?
- Which actual file columns encode driving times and which encode frequencies?
- Are bounds from Load.giv complete, and how should zeros be interpreted?
- Must generated lines meet length/hop restrictions, including pre-existing pool lines?
- Is the cost LP the intended input to rounding, or should the budget LP be used?
- Can exact runs reuse the exact serialized pool from this sweep?

Do not compare these coverage percentages with a capacity-constrained direct
passenger optimum or label a cost-LP bound as a service optimality gap.
