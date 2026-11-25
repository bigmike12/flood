"""
Emergency resource-allocation optimiser (Objective 2).

Given the set of open demands (people awaiting rescue) and the set of idle
responder units, decide which unit serves which demand. This is a constrained
assignment problem: minimise total severity-weighted travel time subject to
reachability over the flooded road network (Farahani et al., 2020; Zheng et al.,
2022).

Four comparable strategies are provided so the AI-optimised policy can be
benchmarked (Objective 5):
  - random             : assign idle units to random reachable demands
  - nearest            : each unit greedily takes its nearest reachable demand
  - pop_proportional   : prioritise demands in the most crowded areas
  - ai_optimised       : globally optimal assignment via the Hungarian algorithm

Two interchangeable solvers are provided for the optimal (ai_optimised) strategy,
both solving the same constrained assignment problem:
  - "hungarian" (default): scipy.optimize.linear_sum_assignment.
  - "ortools": Google OR-Tools CP-SAT. Set the environment variable
    FLOOD_SOLVER=ortools to use it. They produce the same optimal objective, so
    OR-Tools also serves as an independent check on the Hungarian result.
"""
from __future__ import annotations
import os
import numpy as np
from scipy.optimize import linear_sum_assignment

UNREACHABLE = 1e6
SOLVER = os.environ.get("FLOOD_SOLVER", "hungarian").lower()


def build_cost_matrix(units, demands, travel_from, severity_weight):
    """cost[i, j] = weighted travel time of unit i to demand j (UNREACHABLE if no path)."""
    n_u, n_d = len(units), len(demands)
    cost = np.full((n_u, n_d), UNREACHABLE, dtype=float)
    for i, u in enumerate(units):
        dist = travel_from(u.pos)          # dict: cell -> minutes
        for j, d in enumerate(demands):
            t = dist.get(d.pos)
            if t is not None:
                weight = 1.0 + (severity_weight - 1.0) * (d.severity - 1.0)
                cost[i, j] = t / max(weight, 0.1)
    return cost


def allocate(strategy, units, demands, travel_from, rng, severity_weight=2.0, radius=3):
    """Return a dict {unit_index: demand_index} for the chosen strategy.

    All strategies operate on raw travel time; only the AI strategy folds in
    demand value (severity + local cluster size) and solves the assignment
    globally, so it should dominate the greedy/blind baselines.
    """
    if not units or not demands:
        return {}
    cost = build_cost_matrix(units, demands, travel_from, severity_weight=1.0)

    if strategy == "random":
        return _random(cost, rng)
    if strategy == "nearest":
        return _nearest(cost)
    if strategy == "pop_proportional":
        return _pop_proportional(cost, demands)

    # ai_optimised: globally optimal (Hungarian) assignment that minimises total
    # travel time, with a small triage nudge toward URGENT and VULNERABLE
    # demands. Greedy "nearest" and "random" ignore how close a person is to
    # their survival deadline, so they let people expire who could have been
    # reached in time; the AI's deadline-aware priority catches those cases
    # without costly detours (the nudge is small relative to travel time).
    priority = np.array([
        (1.0 + (severity_weight - 1.0) * (d.severity - 1.0)) * (1.0 + getattr(d, "urgency", 0.0))
        for d in demands
    ])
    ai_cost = cost - 4.0 * priority[np.newaxis, :]     # minutes-scale additive nudge
    ai_cost[cost >= UNREACHABLE / 2] = UNREACHABLE
    return _optimal(ai_cost, feasible=cost)


def _ai_cluster(units, demands, cost, severity_weight, radius):
    clusters = _cluster_demands(demands, radius)   # list of (rep_demand_index, size, sev_value)
    n_u = len(units)
    n_c = len(clusters)
    C = np.full((n_u, n_c), UNREACHABLE, dtype=float)
    feasible = np.full((n_u, n_c), UNREACHABLE, dtype=float)
    for k, (dj, size, sev) in enumerate(clusters):
        # minimise travel time (the binding cost), with a mild severity discount
        # so urgent clusters are slightly preferred; cluster de-confliction is the
        # main advantage over the greedy baselines.
        value = 1.0 + 0.5 * (severity_weight - 1.0) * (sev - 1.0)
        for i in range(n_u):
            t = cost[i, dj]
            feasible[i, k] = t
            if t < UNREACHABLE / 2:
                C[i, k] = t / max(value, 0.1)
    rows, cols = linear_sum_assignment(C)
    assign = {}
    for i, k in zip(rows, cols):
        if feasible[i, k] < UNREACHABLE / 2:
            assign[int(i)] = int(clusters[k][0])
    return assign


def _cluster_demands(demands, radius):
    """Greedy spatial clustering. Returns [(representative_index, size, mean_severity)]."""
    order = sorted(range(len(demands)), key=lambda j: -demands[j].severity)
    reps = []           # list of [rep_index, member_indices]
    for j in order:
        p = demands[j].pos
        placed = False
        for rep in reps:
            rp = demands[rep[0]].pos
            if abs(p[0] - rp[0]) <= radius and abs(p[1] - rp[1]) <= radius:
                rep[1].append(j)
                placed = True
                break
        if not placed:
            reps.append([j, [j]])
    out = []
    for rep_idx, members in reps:
        sev = float(np.mean([demands[m].severity for m in members]))
        out.append((rep_idx, len(members), sev))
    return out


def _reachable_pairs(cost):
    return cost < UNREACHABLE / 2


def _random(cost, rng):
    assign = {}
    reach = _reachable_pairs(cost)
    taken = set()
    order = list(range(cost.shape[0]))
    rng.shuffle(order)
    for i in order:
        opts = [j for j in range(cost.shape[1]) if reach[i, j] and j not in taken]
        if opts:
            j = int(rng.choice(opts))
            assign[i] = j
            taken.add(j)
    return assign


def _nearest(cost):
    assign = {}
    taken = set()
    # process units in ascending order of their single best option
    order = sorted(range(cost.shape[0]), key=lambda i: cost[i].min())
    for i in order:
        js = np.argsort(cost[i])
        for j in js:
            if cost[i, j] >= UNREACHABLE / 2:
                break
            if j not in taken:
                assign[i] = int(j)
                taken.add(int(j))
                break
    return assign


def _pop_proportional(cost, demands):
    """Bias toward demands in the busiest neighbourhoods (highest local density)."""
    density = _local_density([d.pos for d in demands])
    # cheaper effective cost for high-density demands, then greedily assign
    adj = cost / (1.0 + density[np.newaxis, :])
    assign = {}
    taken = set()
    order = sorted(range(cost.shape[0]), key=lambda i: adj[i].min())
    for i in order:
        for j in np.argsort(adj[i]):
            if cost[i, j] >= UNREACHABLE / 2:
                break
            if j not in taken:
                assign[i] = int(j)
                taken.add(int(j))
                break
    return assign


def _optimal(cost, feasible=None):
    """Globally optimal assignment. `feasible` is the raw reachability/cost matrix
    used to reject unreachable pairs when `cost` has been rescaled by demand value.
    Dispatches to OR-Tools CP-SAT when FLOOD_SOLVER=ortools, otherwise to the
    Hungarian algorithm (SciPy)."""
    check = feasible if feasible is not None else cost
    if SOLVER == "ortools":
        res = _optimal_ortools(cost, check)
        if res is not None:
            return res
        # OR-Tools unavailable or failed: fall back to Hungarian
    rows, cols = linear_sum_assignment(cost)
    assign = {}
    for i, j in zip(rows, cols):
        if check[i, j] < UNREACHABLE / 2:
            assign[int(i)] = int(j)
    return assign


def _optimal_ortools(cost, check):
    """Same assignment problem solved with Google OR-Tools (CP-SAT): a 0/1 variable
    x[i,j] for each feasible unit-demand pair, each unit and each demand used at
    most once, maximising the number of assignments and then minimising total
    cost. Returns {unit_index: demand_index}, or None if OR-Tools is not installed."""
    try:
        from ortools.sat.python import cp_model
    except Exception:
        return None
    n_u, n_d = cost.shape
    model = cp_model.CpModel()
    SCALE = 1000
    REWARD = SCALE * 100000           # large enough to prefer assigning a unit over saving cost
    x = {}
    for i in range(n_u):
        for j in range(n_d):
            if check[i, j] < UNREACHABLE / 2:
                x[(i, j)] = model.NewBoolVar(f"x_{i}_{j}")
    if not x:
        return {}
    for i in range(n_u):
        vi = [x[(i, j)] for j in range(n_d) if (i, j) in x]
        if vi:
            model.Add(sum(vi) <= 1)
    for j in range(n_d):
        vj = [x[(i, j)] for i in range(n_u) if (i, j) in x]
        if vj:
            model.Add(sum(vj) <= 1)
    model.Minimize(sum((int(round(float(cost[i, j]) * SCALE)) - REWARD) * var
                       for (i, j), var in x.items()))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 2.0
    solver.parameters.num_search_workers = 1
    if solver.Solve(model) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    return {int(i): int(j) for (i, j), var in x.items() if solver.Value(var) == 1}


def _local_density(positions, radius=3):
    dens = np.zeros(len(positions))
    for i, (r1, c1) in enumerate(positions):
        for (r2, c2) in positions:
            if abs(r1 - r2) <= radius and abs(c1 - c2) <= radius:
                dens[i] += 1
    return dens
