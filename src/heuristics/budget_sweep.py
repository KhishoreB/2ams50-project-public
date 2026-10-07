"""Discrete budget experiments; not an exact Pareto-frontier algorithm."""

from dataclasses import asdict
from math import isfinite

from .greedy_pool import PoolProblem, greedy_select
from .lp_rounding import lp_rounding, solve_cost_relaxation


def run_budget_sweep(ptn, pool, budgets, solver="scipy", time_limit=60.0):
    """Return raw trials and the best feasible incumbent for each method.

    The previous budget's incumbent remains a candidate at larger budgets.
    Consequently reported coverage is nondecreasing. Raw results remain visible
    so an unsuccessful new construction is never disguised as a fresh success.
    One cost LP is shared by all rounding trials, with its time logged separately.
    """
    budgets = sorted(set(float(b) for b in budgets))
    if not budgets or any(not isfinite(b) or b < 0 for b in budgets):
        raise ValueError("Provide at least one finite, nonnegative budget.")
    problem = PoolProblem(ptn, pool)
    lp = solve_cost_relaxation(ptn, pool, solver, time_limit)
    records = []
    for method in ("greedy", "lp_rounding"):
        incumbent = None
        source_budget = None
        for budget in budgets:
            raw = (greedy_select(ptn, problem.pool, budget) if method == "greedy" else
                   lp_rounding(ptn, problem.pool, budget, relaxation=lp))
            if raw.feasible and (incumbent is None or
                    (raw.direct_demand_coverage, -raw.cost) >
                    (incumbent.direct_demand_coverage, -incumbent.cost)):
                incumbent = raw
                source_budget = budget
            records.append({
                "dataset": ptn.name, "method": method, "budget": budget,
                "raw": asdict(raw),
                "best_feasible": asdict(incumbent) if incumbent is not None else None,
                "selected_from_budget": source_budget,
                "carried_forward": incumbent is not None and source_budget != budget,
            })
    return {"metric": "uncapacitated_direct_demand_coverage",
            "constraint_policy": "uploaded_utils.effective_frequency_bounds",
            "lp": asdict(lp), "records": records}
