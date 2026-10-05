# Walkthrough: Public Transport Line Planning (Phase 1 & Baseline Setup)

We have completed the foundational architecture, LinTim benchmark data ingestion, line pool generator, solution evaluation engine, and baseline MIP solver for the **2AMS50 Public Transport Line Planning** project.

---

## 1. Project Directory Architecture

The project codebase is organized under [`line_planning/`](file:///Users/andy/Documents/TU_e/Y1/Q1/2AMS50%20Optimization%20for%20Data%20Science/opencode/line_planning/):

- [`src/parser.py`](file:///Users/andy/Documents/TU_e/Y1/Q1/2AMS50%20Optimization%20for%20Data%20Science/opencode/line_planning/src/parser.py): Ingests LinTim `.giv` and `.cnf` files into typed dataclasses (`Stop`, `Edge`, `Line`, `PTNInstance`).
- [`src/pool_generator.py`](file:///Users/andy/Documents/TU_e/Y1/Q1/2AMS50%20Optimization%20for%20Data%20Science/opencode/line_planning/src/pool_generator.py): Generates candidate line pools via $k$-shortest simple paths and edge-coverage guarantees.
- [`src/utils.py`](file:///Users/andy/Documents/TU_e/Y1/Q1/2AMS50%20Optimization%20for%20Data%20Science/opencode/line_planning/src/utils.py): Graph adjacency, path reconstruction, and LinTim cost functions ($c_l = c_{\text{fix}} + c_{\text{len}} \cdot \text{len} + c_{\text{edge}} \cdot |E|$).
- [`src/validator.py`](file:///Users/andy/Documents/TU_e/Y1/Q1/2AMS50%20Optimization%20for%20Data%20Science/opencode/line_planning/src/validator.py): Computes feasibility, total operating cost, active lines, and direct traveler connectivity percentage.
- [`src/models/cost_mip.py`](file:///Users/andy/Documents/TU_e/Y1/Q1/2AMS50%20Optimization%20for%20Data%20Science/opencode/line_planning/src/models/cost_mip.py): Baseline Cost-Minimizing Line Planning MIP using `pyscipopt` (SCIP 10) with automatic Gurobi fallback.
- [`scripts/run_benchmarks.py`](file:///Users/andy/Documents/TU_e/Y1/Q1/2AMS50%20Optimization%20for%20Data%20Science/opencode/line_planning/scripts/run_benchmarks.py): End-to-end benchmark script testing all 5 instances and generating a LaTeX table.
- [`README.md`](file:///Users/andy/Documents/TU_e/Y1/Q1/2AMS50%20Optimization%20for%20Data%20Science/opencode/line_planning/README.md): Quick start guide and role distribution for the 5-member team.

---

## 2. Benchmark Datasets Downloaded & Ingested

We fetched 5 benchmark networks covering all scales from the official OpenLinTim repository:

| Dataset | Stops ($|V|$) | Edges ($|E|$) | OD Pairs | Total Passenger Demand | Benchmark Role |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`toy`** | 8 | 8 | 46 | 2,622.0 | Micro unit test / exact verification |
| **`mandl`** | 15 | 21 | 172 | 15,570.0 | Literature gold standard (Swiss network) |
| **`sioux_falls`**| 24 | 38 | 552 | 4,114.6 | Classic transit grid benchmark |
| **`grid`** | 25 | 40 | 567 | 2,546.0 | Regular artificial grid (topology testing) |
| **`athens`** | 51 | 52 | 2,385 | 63,323.0 | Real-world metro network |

---

## 3. Computational Benchmark Results

Running [`scripts/run_benchmarks.py`](file:///Users/andy/Documents/TU_e/Y1/Q1/2AMS50%20Optimization%20for%20Data%20Science/opencode/line_planning/scripts/run_benchmarks.py) via `.venv/bin/python` solves all 5 instances to proven optimality:

```
=========================================================================================================
Dataset      | |V|  | |E|  | Pool   | Status    | Cost       | Lines  | Direct %  | Time (s)
=========================================================================================================
toy          | 8    | 8    | 8      | optimal   | 51.20      | 5      | 85.43   % | 0.0006  
mandl        | 15   | 21   | 315    | optimal   | 1281.64    | 13     | 94.86   % | 0.0057  
sioux_falls  | 24   | 38   | 1104   | optimal   | 2244.46    | 30     | 83.38   % | 0.4748  
grid         | 25   | 40   | 1134   | optimal   | 712.45     | 14     | 82.29   % | 0.1879  
athens       | 51   | 52   | 59     | optimal   | 408.17     | 16     | 39.70   % | 0.0019  
=========================================================================================================
```

### LaTeX Table for Report:
```latex
\begin{table}[htbp]
  \centering
  \caption{Baseline Cost-Minimizing Line Planning Performance across LinTim Benchmarks}
  \label{tab:baseline_results}
  \begin{tabular}{lrrrrrrrr}
    \toprule
    Dataset & $|V|$ & $|E|$ & $|\mathcal{L}|$ & Status & Cost & Active Lines & Direct (\%) & CPU (s) \\
    \midrule
    toy & 8 & 8 & 8 & FEAS & 51.20 & 5 & 85.4\% & 0.0006 \\
    mandl & 15 & 21 & 315 & FEAS & 1281.64 & 13 & 94.9\% & 0.0057 \\
    sioux_falls & 24 & 38 & 1104 & FEAS & 2244.46 & 30 & 83.4\% & 0.4748 \\
    grid & 25 & 40 & 1134 & FEAS & 712.45 & 14 & 82.3\% & 0.1879 \\
    athens & 51 & 52 & 59 & FEAS & 408.17 & 16 & 39.7\% & 0.0019 \\
    \bottomrule
  \end{tabular}
\end{table}
```

---

## 4. Key Findings & Insights for Group Work

1. **Trade-off between Operator Cost & Direct Passenger Connectivity**:
   - On `mandl`, cost-minimal line planning achieves a remarkable **94.86%** direct travelers, because the network is dense and compact.
   - On `athens`, cost-minimal line planning only achieves **39.70%** direct travelers, because metro line planning along tree-like or sparse corridors forces transfers unless multi-line direct services are explicitly prioritized. This motivates our **Bicriteria Research Question (RQ3)**!
2. **Line Pool Combinatorics**:
   - Even on a 25-stop grid, standard $k$-shortest paths create over 1,100 candidate lines. This directly justifies:
     * **Student 2**: Adding Cutting Planes (clique / capacity cover cuts) to strengthen the formulation (Lecture Ch 4.3 & 4.4).
     * **Student 3**: Column Generation (Branch-and-Price) to dynamically generate only improving lines rather than storing 1,000+ columns (Lecture Ch 3).
     * **Students 4 & 5**: Heuristics (Greedy selection and Large Neighborhood Search) to find near-optimal line concepts rapidly on large networks.
