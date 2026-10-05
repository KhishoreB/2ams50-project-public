# Research Summary: "Line planning in public transportation: models and methods" (Schöbel, 2012)

*Reference: Schöbel, A. (2012). Line planning in public transportation: models and methods. OR Spectrum, 34(3), 491–510.*

This survey is the standard reference on the Line Planning Problem (LPP). It establishes the taxonomy, notation, complexity boundaries, and modeling paradigms used across public transport optimization literature and in the LinTim benchmark suite.

---

## 1. Context in the Public Transport Planning Pipeline

Line planning is the second phase of the classical sequential transit planning hierarchy:

$$\text{Network Design} \longrightarrow \mathbf{\text{Line Planning (LPP)}} \longrightarrow \text{Timetabling (PESP)} \longrightarrow \text{Vehicle Scheduling} \longrightarrow \text{Crew Scheduling}$$

1. **Network Design**: Fixes physical infrastructure (stops $V$, tracks/streets $E$).
2. **Line Planning (LPP)**: Decides routes (sequences of stops) and frequencies (how often per period $I$, e.g., 1 hour).
3. **Timetabling**: Determines exact arrival and departure times at every stop (usually periodic, e.g., via the Periodic Event Scheduling Problem / PESP).
4. **Vehicle Scheduling**: Chains trips into vehicle rotations to minimize fleet size and deadhead kilometers.
5. **Crew Scheduling**: Assigns drivers to vehicle duties subject to labor regulations.

> **Key takeaway for the project**: Line planning operates without knowing exact vehicle timetables or driver rosters. Consequently, operational costs and passenger travel times in line planning models are necessarily *approximations*.

---

## 2. Formal Problem Definition & Notation

- **Public Transportation Network (PTN)**: Undirected or directed graph $G = (V, E)$, where $V$ represents stops/stations and $E$ represents direct physical links (tracks/corridors).
- **Line $l$**: A simple path in $G$.
- **Line Pool $\mathcal{L}_0$**: A set of candidate lines.
- **Frequency $f_l$**: An integer $f_l \in \mathbb{N}_0$ specifying how many times line $l$ operates within planning period $I$.
- **Line Concept $(L, f)$**: A subset of lines $L \subseteq \mathcal{L}_0$ together with their frequencies $f = (f_l)_{l \in L}$.
- **Origin-Destination (OD) Matrix $(W_{uv})_{u,v \in V}$**: Passenger demand per period $I$ from station $u$ to station $v$.
- **Edge Load $w_e$**: Number of passengers traversing edge $e \in E$ during period $I$.

---

## 3. Taxonomy of Objectives and Constraints

Line planning balances two competing interests: **operator cost** and **passenger convenience**.

```
                           Line Planning Models
                                    │
         ┌──────────────────────────┴──────────────────────────┐
         ▼                                                     ▼
   Cost-Oriented                                       Passenger-Oriented
   Goal: Min operator expenses                         Goal: Max service quality
   Subject to: Demand satisfaction                     Subject to: Budget / Capacity
   (LEF, CAP, CON)                                     (BUD, UEF)
```

### 3.1 Cost Functions

Operating expenses typically combine fixed costs per line and variable costs per frequency run:

$$c(L, f) = \sum_{l \in L} \text{cost}_l \cdot f_l$$

where $\text{cost}_l$ depends on:
- Line length in kilometers ($c_{\text{length}} \cdot \text{length}(l)$).
- Running time along the line ($c_{\text{time}} \cdot \text{time}(l)$).
- Fixed vehicle preparation / dispatch costs ($c_{\text{fix}}$).

In passenger-oriented models, costs are constrained by a **budget constraint**:
$$\text{(BUD)} \quad \sum_{l \in L} \text{cost}_l \cdot f_l \le B$$

### 3.2 Passenger Quality Objectives

| Metric | Code in Paper | Definition & Character |
| :--- | :--- | :--- |
| **Direct Travelers** | `Pass-DT` | Maximize passengers traveling between origin $u$ and destination $v$ without transfers. |
| **Riding Time** | `Pass-RT` | Minimize total in-vehicle time across all passengers (ignores transfer waits). |
| **Traveling Time** | `Pass-TT` | Minimize total travel time = in-vehicle riding time + penalty for each transfer. |

*Note on Transfer Penalties*: Because timetables do not yet exist at the line planning stage, transfer wait times cannot be computed exactly. Models approximate transfer inconvenience by assigning a fixed penalty (e.g., 5–10 minutes) per line change.

### 3.3 Feasibility Constraints

| Code | Name | Mathematical Form | Purpose |
| :--- | :--- | :--- | :--- |
| **(LEF)** | Lower Edge Frequency | $\sum_{l: e \in l} f_l \ge f_e^{\min}$ | Guarantees minimum service level on edge $e$. |
| **(UEF)** | Upper Edge Frequency | $\sum_{l: e \in l} f_l \le f_e^{\max}$ | Reflects safety headways, track capacity, noise limits. |
| **(CAP)** | Capacity Constraint | $\sum_{l: e \in l} \text{cap}_l \cdot f_l \ge w_e$ | Ensures enough seats/capacity for edge load $w_e$. |
| **(CAP')** | Single-Line Capacity | $\text{cap}_l \cdot f_l \ge w_e^l$ | Per-line capacity requirement for direct travelers. |
| **(LNF)** | Lower Node Frequency | $\sum_{l: v \in l} f_l \ge f_v^{\min}$ | Minimum visits at important interchange stations. |
| **(UNF)** | Upper Node Frequency | $\sum_{l: v \in l} f_l \le f_v^{\max}$ | Platform capacity limit at station $v$. |
| **(CON)** | Connectivity | Connected path for each $(u,v)$ with $W_{uv} > 0$ | Every OD pair can complete a trip. |

---

## 4. The "Chicken-and-Egg" Problem and the Change & Go Graph

A central theoretical insight in Schöbel (2012) is the feedback loop between passenger routing and line planning:

```
Passenger Demand (OD) ───[Traffic Assignment]───> Edge Loads (w_e)
        ▲                                                │
        │                                                ▼
Re-routed Passengers <───[Line Planning]──────── Line Concept (L, f)
```

1. **Classical Two-Stage Approach**:
   - Distribute passengers onto the PTN using shortest paths *before* lines are chosen $\rightarrow$ creates static edge loads $w_e$.
   - Solve cost-minimization covering problem using $f_e^{\min} = \lceil w_e / \text{cap} \rceil$.
   - *Flaw*: Passengers do not travel on edge-shortest paths if an alternative path allows a direct trip with zero transfers. Static loads $w_e$ misrepresent actual demand flows.

2. **Integrated Routing Approach (The Change & Go Graph)**:
   - Schöbel & Scholl (2006a) construct an auxiliary state-expanded graph $\mathcal{G}_{\text{CG}} = (\mathcal{V}_{\text{CG}}, \mathcal{E}_{\text{CG}})$:
     * Nodes: pairs $(v, l)$ where station $v$ is served by candidate line $l$.
     * In-vehicle edges: $((u, l), (v, l))$ if $u$ and $v$ are consecutive stations along line $l$. Edge weight = driving time.
     * Transfer edges: $((v, l_1), (v, l_2))$ representing a transfer between line $l_1$ and line $l_2$ at station $v$. Edge weight = transfer penalty time.
   - Passengers route freely on $\mathcal{G}_{\text{CG}}$ via shortest paths simultaneously as line decisions $f_l$ are optimized.

---

## 5. Complexity Landscape

Schöbel synthesizes NP-hardness proofs for the core variants:

| Model Variant | Objective / Constraints | Complexity | Reduction From |
| :--- | :--- | :--- | :--- |
| **(LP-basic)** | Feasible line concept with $f_e^{\min} \le \sum f_l \le f_e^{\max}$ | **NP-hard** | Exact Cover by 3-Sets (X3C), even when $f_e^{\min} = f_e^{\max} = 1$ |
| **(LP-cost)** | Min cost with (LEF) and (UEF) | **NP-hard** | Set Covering / Multi-covering |
| **(LP-cost)** without UEF | Min cost, $f_e^{\max} = \infty$ | **NP-hard** | Set Covering (even if all $c_l = 1$ and $f_e^{\min} = 1$) |
| **(LP-cost)** all paths allowed | Min cost, any path in $G$ can be a line | **NP-hard** | Hamiltonian Path |
| **(LP-cost)** with (CAP) | Min cost subject to edge passenger capacity | **NP-hard** | Vertex Cover (Claessens et al. 1998) |
| **(Direct-travelers)** | Max direct travelers subject to (UEF), (LEF) | **NP-hard** | Contains (LP-basic) as special case |
| **(Traveling-time)** | Min total passenger travel time subject to (BUD) | **NP-hard** | NP-hard even on a linear graph with unit costs |

### Polynomially Solvable Special Cases
- **(LP-basic) without upper bounds ($f_e^{\max} = \infty$)**: Feasible if and only if every edge with $f_e^{\min} > 0$ is covered by at least one line in $\mathcal{L}_0$. Can be solved greedily in polynomial time.
- **Single-edge lines allowed**: If every single edge $e \in E$ is an admissible line, setting $f_e = f_e^{\min}$ gives a trivial polynomial solution (though practically useless due to excessive transfers).
- **Tree networks with a shared terminal**: Torres et al. (2008b) showed polynomial solvability for feeder line planning on trees when all lines start at the same central terminal.

---

## 6. Major Methodologies in Literature

### 6.1 Integer Programming & Branch-and-Cut (Cost Models)
- **Claessens, van Dijk, Zwaneveld (1998)**: Cost-optimal railway line allocation for Dutch Railways (NS). Incorporated train types, car lengths, and frequencies into a non-linear integer program linearized by expanding decision variables to $X_{l}^{t, f, c}$.
- **Bussieck, Lindner, Lübbecke (2004)**: Developed fast branch-and-cut algorithms with valid inequalities and lower bounding techniques for Dutch and German rail networks.
- **Goossens, van Hoesel, Kroon (2004, 2006)**: Multi-type railway line planning where different train categories (Intercity vs. Regional) have different stopping patterns, modeled as multi-commodity flow.

### 6.2 Column Generation & Branch-and-Price (Dynamic Line Generation)
- **Borndörfer, Grötschel, Pfetsch (2007)**: Formulated line planning as a multi-commodity flow problem where both passenger paths and line paths are determined dynamically.
  * Instead of pre-fixing a pool $\mathcal{L}_0$, lines are generated dynamically.
  * Master problem handles capacity and demand covering.
  * Pricing subproblem finds paths with negative reduced cost (constrained shortest path). Proved the pricing subproblem is NP-hard.
  * Tested on the city bus network of Potsdam, Germany.

### 6.3 Direct Travelers Approaches
- **Dienst (1978)**: First IP formulation of the direct travelers problem; solved via greedy branch-and-bound adding lines one by one.
- **Bussieck, Kreuzer, Zimmermann (1996) & Bussieck (1998)**: Polyhedral analysis of direct travelers with line capacities. Cutting-plane algorithms applied to German and Swiss rail instances.

### 6.4 Heuristic Line Generation & Transit Route Network Design (TRNDP)
- **Constructive insertion**: Lampkin & Saalmans (1967) sequentially insert uncovered stops to minimize insertion cost.
- **Skeleton method**: Silman et al. (1974) pick high-demand endpoints and connect intermediate hubs via shortest paths.
- **Iterative improvement**: Mandl (1980) starts with a feasible line concept and applies local search (exchanging line segments, adding/removing stations). Mandl's 15-stop Swiss network remains the most cited benchmark in transit network design.
- **Dual-set method**: Pape et al. (1995) identify high-demand core corridors first, then add secondary coverage lines.

---

## 7. Direct Implications for the 2AMS50 Project

| Section in Schöbel (2012) | Project Requirement | How Our Project Addresses It |
| :--- | :--- | :--- |
| **Section 2.1 (Table 1 & 2)** | Problem Formulation | We formulate Model A (Cost-minimal edge covering) and Model B (Direct-traveler maximization under budget). |
| **Section 2.2** | Complexity Analysis | We cite Bussieck's X3C proof for (LP-basic) and the reduction from Set Covering for cost models to explain why our models are NP-hard. |
| **Section 3.1 & 3.2** | Literature Survey | Provides the theoretical lineage for Student 1 (MIP baseline), Student 2 (Cuts / Claessens), and Student 3 (Column Generation / Borndörfer). |
| **Section 3.5** | Heuristic Methods | Directly motivates Student 4 (demand-driven greedy pool generator / Pape et al.) and Student 5 (Large Neighborhood Search / Mandl 1980). |
| **Section 4 & 5 (Conclusion)** | Research Question / Bicriteria Frontier | Schöbel explicitly calls for combining cost and passenger quality into a **bicriteria Pareto model** — exactly our **Option A** research direction! |
| **LinTim Genesis (Section 5)** | Data Files & Benchmarks | Schöbel's research group created LinTim (Goerigk, Schachtebeck, Schöbel 2011), the exact source of our benchmark instances (`toy`, `mandl`, `grid`, `sioux_falls`, `athens`). |

---

## 8. Key Discussion Points for the Final Report

1. **The Athens Discrepancy (39.7% Direct Travelers)**:
   Schöbel notes that pure cost minimization (Model A) leads to tree-like, non-overlapping line plans where passengers are forced to transfer frequently. Our empirical result on Athens (39.7% direct travelers at cost-optimal frequency) perfectly demonstrates this theoretical limitation.
2. **Fixed vs. Variable Line Costs**:
   Equation (1) in Schöbel ($c(L,f) = \sum \text{cost}_l f_l$) captures frequency-dependent costs. However, dispatching a line has a fixed infrastructure/fleet cost ($c_{\text{fix}}$). Using binary activation variables $x_l \in \{0, 1\}$ alongside integer frequencies $f_l$ links directly to Chapter 4 integer programming formulations.
3. **The Static Edge Load Assumption**:
   Our baseline cost model assumes edge loads are predetermined from `Load.giv`. In our report's critique section, we can cite Schöbel's discussion of the Change & Go graph to explain why joint routing-and-line planning represents the state-of-the-art advancement over static covering models.
