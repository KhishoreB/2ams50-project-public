# Public Transport Line Planning — Project Plan

Group project for 2AMS50 Optimization for Data Science, TU/e. Five students, due October 19.

> [!IMPORTANT]
> **AI policy**: The course allows AI only for coding support (Copilot-style). AI cannot generate your mathematical models, algorithms, or report text. This document is a planning reference. You must formulate, implement, and understand everything you submit.
>
> **Defense**: Every student faces an individual defense in weeks 7–8. Every student must develop at least one solution method. The role assignments below are designed so each person owns an algorithm.

## 1. The problem

Line planning decides which sequences of stops public transport vehicles will serve, and how often. Given a transit network graph $G = (V, E)$, passenger demand between stops (OD matrix), and operational constraints, find a set of lines and frequencies that balance operator cost against passenger service quality.

In the broader transit planning pipeline, line planning sits between network design (which stops and tracks exist) and timetabling (when vehicles depart). This project focuses only on line planning.

### Input data

- **Network** $G = (V, E)$: stops $V$, direct links $E$. Each edge $e$ has length $d_e$ and frequency bounds $[f_e^{\min}, f_e^{\max}]$.
- **OD demand**: matrix $D = (d_{uv})$ — passengers wanting to travel from $u$ to $v$.
- **Line pool** $\mathcal{L}$: candidate simple paths in $G$. Each line $l$ has cost $c_l = c_{\text{fix}} + c_{\text{var}} \cdot \text{length}(l)$ and vehicle capacity $\text{Cap}_l$.
- **Decisions**: frequencies $f_l \in \mathbb{Z}_{\ge 0}$ for each line, and (optionally) passenger routing.

### Two competing objectives

1. **Operator cost**: minimize $\sum_{l} c_l f_l$. Fewer lines, lower frequencies, shorter routes.
2. **Passenger quality**: maximize direct travelers (no transfers), minimize travel time.

These conflict. Cost-minimizing plans force transfers. Passenger-maximizing plans need many overlapping lines. The literature (Schöbel 2012, Goerigk et al. 2013) studies the Pareto frontier between them.

### Key references

- Schöbel (2012), "Line planning in public transportation: models and methods." OR Spectrum 34(3), 491–527. Survey paper covering cost and passenger models.
- Borndörfer, Grötschel, Pfetsch (2007), "A column-generation approach to line planning in public transport." Transportation Science 41(1), 123–132. Column generation applied to this problem.
- Goerigk, Schöbel (2016), "Algorithm engineering in public transit: the LinTim perspective." Annals of OR 236(2), 365–392. Describes the LinTim benchmarks.
- Bussieck, Lindner, Lübbecke (2004), "A fast algorithm for line planning in public transport." Math Methods of OR 60(3), 441–463.

## 2. Available datasets

All datasets come from [OpenLinTim on GitLab](https://gitlab.com/lintim/openlintim). Already downloaded to `line_planning/data/`.

| Dataset | $|V|$ | $|E|$ | OD pairs | Total demand | Has line pool? | Notes |
| :--- | ---: | ---: | ---: | ---: | :---: | :--- |
| `toy` | 8 | 8 | 46 | 2,622 | Yes (8 lines) | Tiny. Use for unit tests and verifying correctness. |
| `mandl` | 15 | 21 | 172 | 15,570 | No | Classic benchmark from Mandl (1980). Dense demand. |
| `sioux_falls` | 24 | 38 | 552 | 4,115 | No | Standard transportation network from the literature. |
| `grid` | 25 | 40 | 567 | 2,546 | No | Artificial 5×5 grid. Regular topology. |
| `athens` | 51 | 52 | 2,385 | 63,323 | Yes (59 lines) | Real Athens metro network. Sparse, tree-like. |

Other datasets in the repo (`goevb` 257 stops, `lowersaxony`, `helsinki`, `BOMHarbour`, `ring`) can be used for scalability testing.

### Data format

LinTim uses semicolon-delimited `.giv` files in a `basis/` subdirectory:
- `Stop.giv`: `stop-id; short-name; long-name; x-coord; y-coord`
- `Edge.giv`: `edge-id; left-stop; right-stop; length; lower-bound; upper-bound`
- `OD.giv`: `origin; destination; passengers`
- `Load.giv` (optional): `edge-id; load; min-frequency; max-frequency` — demand-derived bounds
- `Pool.giv` + `Pool-Cost.giv` (optional): pre-computed candidate lines

**Important distinction**: `Edge.giv` bounds are infrastructure limits (how many vehicles the track supports). `Load.giv` bounds are demand-derived (how many vehicles are needed to carry the passengers). When `Load.giv` exists, its bounds should override `Edge.giv` bounds for frequency planning. The Mandl dataset has `lower == upper` on every edge because the load calculation already determined exact required frequencies.

## 3. Research direction — pick one

The assignment asks for formulations, solution methods, and computational results. The research questions below are **options**. Pick one primary direction; the others can appear briefly in the literature review or discussion. Trying to do all four will spread the team too thin.

### Option A: Cost vs. passenger quality trade-off (recommended)

> How much extra does it cost to improve direct passenger connectivity, and where do diminishing returns set in?

**What you'd do**: Implement a cost-minimizing MIP (Model A below) and a direct-traveler-maximizing MIP (Model B). Use ε-constraint method to trace the Pareto frontier on `mandl` and `athens`. Compare heuristic solutions against exact frontier.

**Why it's a good fit**: Connects to multicriteria optimization. The baseline results already show the gap: cost minimization on Athens gives only 39.7% direct travelers. On Mandl, 94.9%. The comparison tells a clear story. Every team member can contribute a different method to generate points on or near the frontier.

**Course topics**: LP/IP formulation (Ch 1–2), duality and sensitivity for interpreting trade-offs (Ch 2), valid inequalities optional (Ch 4.3).

### Option B: Column generation vs. static pools

> Can dynamic line generation via Dantzig-Wolfe decomposition find better line plans than pre-enumerated candidate pools?

**What you'd do**: Implement a static-pool MIP, then a column generation version where the pricing subproblem generates lines on the fly (constrained shortest path with modified edge weights from dual prices). Compare solution quality and runtime as pool size grows.

**Why it's a good fit**: Column generation is Chapter 3 of the course. The pricing subproblem is a shortest-path problem with side constraints — concrete and implementable. Scales better than enumerating all paths.

**Course topics**: Column generation / Dantzig-Wolfe (Ch 3), LP duality (Ch 2).

### Option C: Formulation strength and cutting planes

> How much does formulation strength matter? Does adding valid inequalities close the LP-IP gap faster than branching?

**What you'd do**: Implement two formulations (compact edge-load vs. path-based multicommodity), compare their LP relaxation bounds, then add cutting planes (cover cuts, clique cuts on station capacities) to the weaker one. Measure B&B node counts and solve times.

**Course topics**: Formulation strength (Ch 4.4), cutting planes (Ch 4.3), branch-and-bound (Ch 4.2).

### Option D: Exact vs. heuristic scaling

> How close to optimal can heuristics get, and how much faster are they?

**What you'd do**: Solve small instances exactly (MIP), then implement constructive heuristics (greedy demand-driven selection, LP rounding) and improvement heuristics (LNS, simulated annealing). Compare optimality gaps and runtimes across all dataset sizes.

**Course topics**: IP formulation (Ch 4.1), heuristic design (not directly in lectures, but required by the assignment).

## 4. Mathematical formulations

### Model A: Cost minimization (edge-frequency covering)

$$\min \sum_{l \in \mathcal{L}} c_l f_l$$

$$\sum_{l: e \in l} f_l \ge f_e^{\min} \quad \forall e \in E \qquad \text{(serve demand)}$$

$$\sum_{l: e \in l} f_l \le f_e^{\max} \quad \forall e \in E \qquad \text{(track capacity)}$$

$$f_l \in \mathbb{Z}_{\ge 0} \quad \forall l \in \mathcal{L}$$

The lower bounds $f_e^{\min}$ come from demand: $f_e^{\min} = \lceil W_e / C_{\text{veh}} \rceil$ where $W_e$ is the passenger load on edge $e$.

**Known limitation**: This model treats edge loads $W_e$ as fixed input. But edge loads depend on how passengers route through the network, which depends on which lines exist. Changing the line plan changes the routing, which changes the loads. Schöbel (2012) calls this the "chicken-and-egg problem." Model A ignores this feedback. Discuss it in the report.

### Model B: Direct-traveler maximization with budget

$$\max \sum_{u,v \in V} d_{uv} \, y_{uv}$$

$$y_{uv} \le \sum_{l: u,v \in l} x_l \quad \forall u,v \in V \qquad \text{(need a line covering both stops)}$$

$$\sum_{l \in \mathcal{L}} c_l x_l \le B \qquad \text{(budget cap)}$$

$$\sum_{l: e \in l} x_l \le f_e^{\max} \quad \forall e \in E$$

$$x_l \in \{0,1\}, \quad 0 \le y_{uv} \le 1$$

Varying the budget $B$ via ε-constraint traces the Pareto frontier.

### Model C: Column generation master

Same structure as Model A, but start with a small subset $\mathcal{L}' \subset \mathcal{L}$ and solve the LP relaxation. Dual prices $\pi_e \ge 0$ (from covering constraints) give modified edge weights. The pricing subproblem finds the simple path $P$ minimizing:

$$\bar{c}_P = c_{\text{fix}} + \sum_{e \in P}(c_e - \pi_e)$$

If $\bar{c}_P < 0$, add $P$ to $\mathcal{L}'$ and re-solve. Stop when no negative reduced cost path exists.

## 5. Team roles

Every student must own a solution method for their defense. The roles below work regardless of which research direction you pick.

| Student | Owns | Builds | Defense topic |
| :--- | :--- | :--- | :--- |
| **1** | Data pipeline + baseline MIP | Parser, validator, baseline cost MIP (Model A), evaluation scripts | Problem definition, graph modeling, baseline results |
| **2** | Formulation work | Stronger formulation or valid inequalities (cover/clique cuts), LP relaxation comparison | Formulation strength, LP-IP gap, dual bounds |
| **3** | Decomposition method | Column generation: RMP + pricing subproblem (shortest path with dual weights) | Reduced cost theory, convergence, shadow price interpretation |
| **4** | Constructive heuristic | Demand-driven line pool generator, greedy selection, LP rounding with repair | Heuristic design, speed vs. quality trade-off |
| **5** | Improvement heuristic | LNS or simulated annealing: destroy operators (remove underused lines) + repair (greedy re-insertion) | Neighborhood operators, escape from local optima, scaling |

Students 2 and 3 are the "exact methods" pair. Students 4 and 5 are the "heuristics" pair. Student 1 builds the shared infrastructure everyone uses.

If you pick Option A (bicriteria), Student 1 also implements the ε-constraint loop, and everyone's method contributes points to the Pareto plot. If Option B, Student 3's column generation is the centerpiece and others compare against it.

## 6. Known issues in the current codebase

These need fixing before the team builds on top.

### 6.1 Direct-traveler metric ignores capacity

`validator.py` checks whether both OD stops appear in any active line's node sequence. It counts all demand as "direct" if the path exists, regardless of whether the line has enough capacity. For a binary connectivity metric (can you travel without transfer, yes/no) this is fine — Schöbel (2012) uses this definition. But document the choice in the report. If you want a capacity-weighted metric, you need to solve a passenger assignment subproblem.

### 6.2 Pool generator doesn't scale

The BFS in `pool_generator.py` enumerates paths from every OD pair without a hard cap on total pool size. On the 25-node grid it already produces 1,134 candidates. On `goevb` (257 stops) it will blow up. Fixes: (a) only generate lines for top-$k$ OD pairs by demand, (b) use Yen's algorithm instead of full BFS, (c) cap total pool size.

### 6.3 Edge bound semantics

`Edge.giv` columns 5–6 are infrastructure limits. `Load.giv` columns 3–4 are demand-derived frequency bounds. The parser now uses `Load.giv` bounds when available, which is correct. But `run_benchmarks.py` also manually inflates upper bounds for Mandl and Sioux Falls (`e.upper_bound = max(e.upper_bound, e.lower_bound + 6)`). This is a workaround, not a fix. The proper approach: separate infrastructure capacity from demand-derived frequency requirements in the data model, and let the MIP use both.

## 7. Report structure

1. **Introduction**: What line planning is, where it fits in transit planning, what this report studies.
2. **Literature review**: 4–6 papers. Cost vs. passenger models. Techniques used (IP, column generation, heuristics). Complexity results if available.
3. **Problem formulations**: Notation table. At least two formulations. Discuss their trade-offs (size, tightness, what they model vs. what they ignore).
4. **Solution methods**: What each team member implemented. At least one exact method and one heuristic.
5. **Computational results**: Instance table with $|V|$, $|E|$, pool size. Per-method: objective value, optimality gap (if known), runtime. Plots: Pareto frontier or convergence curves or scaling behavior (pick what fits your research direction).
6. **Discussion**: What worked, what didn't, what the numbers mean for real transit planning.
7. **Individual contributions**: Table mapping each student to their formulations, code, and report sections.

## 8. Timeline

| Week | What happens |
| :--- | :--- |
| 1 (now) | Download data (done). Set up shared repo. Each student reads Schöbel (2012). Agree on research direction. |
| 2 | Student 1 finishes baseline MIP + validator. Student 4 builds pool generator. Verify on `toy`. |
| 3–4 | Students 2, 3, 5 implement their methods. Test on `toy` and `mandl`. |
| 5 | Run all methods across all datasets. Collect results tables. Start writing. |
| 6 (Oct 12–19) | Write report. Internal review. Mock defense practice. Submit by Oct 19 23:59. |

## 9. Verification checklist

- All methods produce the same (or provably optimal) cost on the `toy` instance.
- `validate_solution()` checks: min edge frequencies met, max capacities not exceeded, every line is a valid simple path in $G$.
- For exact methods: LP relaxation ≤ IP optimum (minimization). Column generation terminates with all reduced costs ≥ 0.
- For heuristics: report the gap to the best known lower bound.
