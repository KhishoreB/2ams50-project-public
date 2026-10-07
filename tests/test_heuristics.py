"""Synthetic regression cases, not LinTim benchmark results."""

import itertools
import math
import unittest

from src.parser import Stop, Edge, Line, PTNInstance
from src.heuristics.greedy_pool import PoolProblem, greedy_select
from src.heuristics.lp_rounding import LPResult, lp_rounding, solve_cost_relaxation
from src.heuristics.budget_sweep import run_budget_sweep
from src.validator import evaluate_line_plan
from src.heuristics.input_audit import audit_lintim_frequency_inputs


def triangle():
    stops = {i: Stop(i, str(i), str(i), float(i), 0) for i in (1, 2, 3)}
    edges = {1: Edge(1, 1, 2, 1, 1, 2), 2: Edge(2, 2, 3, 1, 1, 2),
             3: Edge(3, 3, 1, 1, 1, 2)}
    ptn = PTNInstance("synthetic_triangle", stops, edges, {(1, 3): 100, (3, 1): 20},
                      {"gen_passengers_per_vehicle": "10"})
    pool = {1: Line(1, [1, 2], 2, 1, [1, 2, 3]),
            2: Line(2, [2, 3], 2, 1, [2, 3, 1]),
            3: Line(3, [3, 1], 2, 1, [3, 1, 2])}
    return ptn, pool


def independent_edges():
    stops = {i: Stop(i, str(i), str(i), i, 0) for i in range(1, 5)}
    ptn = PTNInstance("synthetic_independent", stops,
                      {1: Edge(1, 1, 2, 1, 0, 2), 2: Edge(2, 3, 4, 1, 0, 2)},
                      {(1, 2): 10, (3, 4): 100}, {"gen_passengers_per_vehicle": "10"})
    return ptn, {1: Line(1, [1], 1, 1, [1, 2]), 2: Line(2, [2], 1, 1, [3, 4])}


class HeuristicsTests(unittest.TestCase):
    def test_real_input_guard_rejects_missing_loads(self):
        ptn, _ = triangle()
        with self.assertRaisesRegex(ValueError, "travel-time"):
            audit_lintim_frequency_inputs(ptn)
        self.assertTrue(audit_lintim_frequency_inputs(ptn, True)["legacy_diagnostic"])

    def test_real_input_guard_accepts_complete_positive_load_bounds(self):
        ptn, _ = triangle()
        ptn.loads = {eid: (10, 1, 2) for eid in ptn.edges}
        self.assertTrue(audit_lintim_frequency_inputs(ptn)["frequency_inputs_verified_for_shared_helper"])

    def test_real_input_guard_rejects_ambiguous_zero_bounds(self):
        ptn, _ = triangle()
        ptn.loads = {eid: (0, 0, 2) for eid in ptn.edges}
        with self.assertRaises(ValueError):
            audit_lintim_frequency_inputs(ptn)

    def test_lp_fractionality_and_integer_repair(self):
        ptn, pool = triangle()
        lp = solve_cost_relaxation(ptn, pool)
        self.assertEqual(lp.status, "optimal")
        self.assertAlmostEqual(lp.cost_lower_bound, 1.5)
        self.assertTrue(all(abs(f - .5) < 1e-7 for f in lp.frequencies.values()))
        result = lp_rounding(ptn, pool, 2, relaxation=lp)
        self.assertTrue(result.feasible)
        self.assertEqual(result.cost, 2)
        self.assertTrue(all(isinstance(f, int) for f in result.frequencies.values()))

    def test_exhaustive_integer_optimum_matches_lp_bound_direction(self):
        ptn, pool = triangle()
        feasible_costs = []
        for values in itertools.product(range(3), repeat=3):
            report = evaluate_line_plan(ptn, pool, dict(zip(pool, values)))
            if report.is_feasible:
                feasible_costs.append(report.total_cost)
        self.assertEqual(min(feasible_costs), 2)
        self.assertLessEqual(solve_cost_relaxation(ptn, pool).cost_lower_bound, min(feasible_costs))

    def test_no_double_counting_overlapping_lines(self):
        ptn, pool = triangle()
        result = greedy_select(ptn, pool, 3)
        self.assertEqual(result.direct_demand_coverage, 120)
        self.assertEqual(result.coverage_percentage, 100)

    def test_high_demand_selected_first(self):
        ptn, pool = independent_edges()
        result = greedy_select(ptn, pool, 1)
        self.assertEqual(result.frequencies, {2: 1})

    def test_budget_below_lp_bound(self):
        ptn, pool = triangle()
        result = lp_rounding(ptn, pool, 1.4)
        self.assertEqual(result.status, "budget_below_lp_bound")
        self.assertFalse(result.feasible)

    def test_integer_failure_is_not_an_infeasibility_proof(self):
        ptn, pool = triangle()
        result = lp_rounding(ptn, pool, 1.6)
        self.assertEqual(result.status, "construction_failed")
        self.assertFalse(result.feasible)

    def test_uncovered_required_edge(self):
        ptn, pool = triangle()
        result = greedy_select(ptn, {1: pool[1]}, 10)
        self.assertEqual(result.status, "pool_infeasible")

    def test_effective_load_upper_bounds_enforced(self):
        ptn, pool = triangle()
        ptn.loads = {eid: (0, 1, 1) for eid in ptn.edges}
        result = greedy_select(ptn, pool, 10)
        self.assertFalse(result.feasible)
        ef = PoolProblem(ptn, pool).edge_frequencies(result.frequencies)
        self.assertTrue(all(f <= 1 for f in ef.values()))

    def test_zero_budget_zero_cost_terminates(self):
        ptn, pool = independent_edges()
        pool[2].cost = 0
        result = greedy_select(ptn, pool, 0)
        self.assertTrue(result.feasible)
        self.assertEqual(result.frequencies, {2: 1})

    def test_invalid_inputs_rejected(self):
        ptn, pool = triangle()
        for budget in (-1, math.inf, math.nan):
            with self.assertRaises(ValueError):
                greedy_select(ptn, pool, budget)
        for frequencies in ({999: 1}, {1: -.1}, {1: .5}, {1: 20}):
            with self.assertRaises(ValueError):
                greedy_select(ptn, pool, 2, frequencies)
        pool[1].cost = -1
        with self.assertRaises(ValueError):
            greedy_select(ptn, pool, 2)

    def test_stale_node_lists_are_resolved_without_mutating_input(self):
        ptn, pool = triangle()
        pool[1].nodes = []
        result = greedy_select(ptn, pool, 2)
        self.assertTrue(result.feasible)
        self.assertEqual(result.direct_demand_coverage, 120)
        self.assertEqual(pool[1].nodes, [])

    def test_invalid_path_rejected(self):
        ptn, pool = independent_edges()
        pool[1].edges = [1, 2]
        with self.assertRaises(ValueError):
            greedy_select(ptn, pool, 3)

    def test_empty_pool_can_serve_zero_requirements(self):
        ptn, _ = independent_edges()
        self.assertTrue(greedy_select(ptn, {}, 0).feasible)
        self.assertEqual(solve_cost_relaxation(ptn, {}).cost_lower_bound, 0)

    def test_unknown_solver_rejected(self):
        ptn, pool = triangle()
        with self.assertRaises(ValueError):
            solve_cost_relaxation(ptn, pool, "typo")

    def test_budget_sweep_monotone_and_reproducible(self):
        ptn, pool = independent_edges()
        result = run_budget_sweep(ptn, pool, [2, 0, 1, 1])
        for method in ("greedy", "lp_rounding"):
            rows = [r for r in result["records"] if r["method"] == method]
            self.assertEqual([r["budget"] for r in rows], [0, 1, 2])
            coverage = [r["best_feasible"]["direct_demand_coverage"] for r in rows]
            self.assertEqual(coverage, [0, 100, 110])
        self.assertEqual(greedy_select(ptn, pool, 1).frequencies,
                         greedy_select(ptn, pool, 1).frequencies)

    def test_lp_failure_falls_back_transparently(self):
        ptn, pool = triangle()
        result = lp_rounding(ptn, pool, 2,
                             relaxation=LPResult("limit", {}, None, .1, "test"))
        self.assertTrue(result.feasible)
        self.assertTrue(result.details["fallback_used"])

    def test_full_capacity_is_not_claimed(self):
        ptn, pool = independent_edges()
        result = greedy_select(ptn, pool, 1)
        # 100 demand and 10 capacity: validates intentional coverage-only scope.
        self.assertEqual(result.direct_demand_coverage, 100)
        self.assertIn("coverage proxy", result.message)


if __name__ == "__main__":
    unittest.main()
