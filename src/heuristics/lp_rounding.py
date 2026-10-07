"""Round the team's COST LP, repair, and add direct-demand coverage.

This is not the LP of Student 2's budget model (which was not supplied).
Gurobi/SCIP call the supplied solve_cost_mip(integer=False). The optional
SciPy backend expresses exactly those same frequency constraints.
"""

from dataclasses import dataclass
from math import floor, isfinite
from time import perf_counter

from .greedy_pool import PoolProblem, TOL, greedy_select, make_result


@dataclass
class LPResult:
    status: str
    frequencies: dict
    cost_lower_bound: float | None
    runtime_seconds: float
    solver: str


def solve_cost_relaxation(ptn, pool, solver="scipy", time_limit=60.0):
    """An optimal cost LP is a LOWER bound on feasible integer operating cost."""
    started = perf_counter()
    if not isfinite(time_limit) or time_limit <= 0:
        raise ValueError("Time limit must be finite and positive.")
    problem = PoolProblem(ptn, pool)
    if any(lo > 0 and not any(e in line.edges for line in problem.pool.values())
           for e, (lo, _) in problem.bounds.items()):
        return LPResult("infeasible", {}, None, perf_counter()-started, solver)
    if not pool:
        return LPResult("optimal", {}, 0.0, perf_counter()-started, solver)
    if solver in ("gurobi", "scip", "auto"):
        from ..models.cost_mip import solve_cost_mip
        freqs, obj, _, status, _ = solve_cost_mip(
            ptn, problem.pool, solver=solver, time_limit=time_limit, integer=False)
        return LPResult(status, freqs, float(obj) if status == "optimal" else None,
                        perf_counter()-started, solver)
    if solver != "scipy":
        raise ValueError("Solver must be scipy, gurobi, scip or auto.")
    import numpy as np
    from scipy.optimize import linprog
    from scipy.sparse import coo_matrix

    ids = list(problem.pool)
    rows, cols, vals, rhs = [], [], [], []
    for eid, (lo, hi) in problem.bounds.items():
        for sign, bound in [(-1, -lo)] + ([(1, hi)] if hi > 0 else []):
            row = len(rhs)
            rhs.append(bound)
            for col, lid in enumerate(ids):
                if eid in problem.pool[lid].edges:
                    rows.append(row); cols.append(col); vals.append(sign)
    matrix = coo_matrix((vals, (rows, cols)), shape=(len(rhs), len(ids))).tocsr()
    result = linprog(np.array([problem.pool[i].cost for i in ids]),
                     A_ub=matrix, b_ub=np.array(rhs), bounds=(0, None),
                     method="highs", options={"time_limit": time_limit})
    status = {0: "optimal", 1: "limit", 2: "infeasible", 3: "unbounded", 4: "solver_error"}[result.status]
    frequencies = {i: max(0.0, float(x)) for i, x in zip(ids, result.x)} if result.x is not None else {}
    return LPResult(status, frequencies, float(result.fun) if result.success else None,
                    perf_counter()-started, solver)


def lp_rounding(ptn, pool, budget, solver="scipy", time_limit=60.0, relaxation=None):
    """Floor LP frequencies, repair greedily, then fill remaining budget.

    If rounding leads into a dead end, try greedy construction from zero and
    record that fallback. Floor rounding can violate minimum frequencies;
    it never certifies integer feasibility on its own.
    A supplied relaxation must belong to exactly the same instance and pool.
    """
    started = perf_counter()
    if not isfinite(budget) or budget < 0:
        raise ValueError("Budget must be finite and nonnegative.")
    problem = PoolProblem(ptn, pool)
    lp = relaxation or solve_cost_relaxation(ptn, pool, solver, time_limit)
    details = {"lp_status": lp.status, "lp_cost_lower_bound": lp.cost_lower_bound,
               "lp_runtime_seconds": lp.runtime_seconds, "lp_reused": relaxation is not None,
               "fallback_used": False}
    if lp.status == "infeasible":
        return make_result(problem, {}, budget, "lp_rounding", "lp_infeasible", started,
                           "The continuous cost model is infeasible for this pool.", details)
    if lp.status == "optimal" and lp.cost_lower_bound is not None and lp.cost_lower_bound > budget + TOL:
        # Empty frequencies might satisfy zero lower bounds in other problems;
        # here the positive LP cost proves there is no budget-feasible plan.
        return make_result(problem, {}, budget, "lp_rounding", "budget_below_lp_bound", started,
                           "Budget is below the optimal continuous cost lower bound.", details)
    if lp.status == "optimal":
        if set(lp.frequencies) - set(pool):
            raise ValueError("Cached relaxation references an unknown line.")
        # Plain floor is conservative around solver tolerances; repair restores
        # a 0.999999999 value to 1 if needed, without risking upper-bound overflow.
        seed = {lid: floor(max(0.0, value)) for lid, value in lp.frequencies.items()
                if value >= 1.0}
        result = greedy_select(ptn, pool, budget, seed)
    else:
        result = None
    if result is None or not result.feasible:
        details["fallback_used"] = True
        if result is not None:
            details["rounding_attempt_status"] = result.status
        result = greedy_select(ptn, pool, budget)
    result.method = "lp_rounding"
    result.runtime_seconds = perf_counter() - started
    result.details.update(details)
    return result
