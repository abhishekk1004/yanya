"""Itinerary optimiser: order selected destinations into a minimum-cost,
budget-feasible route.

Cost model: travel cost between two points is their great-circle (haversine)
distance × COST_PER_KM; a route's total is the sum of its leg travel costs plus
the visit cost of each included destination. We build the order with a
nearest-neighbour heuristic, improve it with 2-opt, and — if the total busts the
budget — greedily drop the stop whose removal saves the most, re-optimising each
time.

Complexity: distance matrix O(n²·C=1); nearest-neighbour O(n²); one 2-opt pass
O(n²) and it converges in a few passes for the small n a traveller selects.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

COST_PER_KM = 12.0  # NPR per km of ground travel (approx.)


@dataclass
class Point:
    id: int          # destination id (or -1 for a virtual start)
    lat: float
    lng: float
    visit_cost: int  # NPR; 0 for a virtual start point


@dataclass
class OptimizedRoute:
    order: list[int]              # destination ids in visit order (excl. start)
    leg_costs: list[int]         # NPR travel cost to reach each ordered stop
    travel_cost_npr: int
    visit_cost_npr: int
    total_cost_npr: int
    dropped: list[int] = field(default_factory=list)


def haversine_km(a: Point, b: Point) -> float:
    """Great-circle distance in km between two points. O(1)."""
    r = 6371.0
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dphi = math.radians(b.lat - a.lat)
    dlmb = math.radians(b.lng - a.lng)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def cost_matrix(points: list[Point]) -> list[list[float]]:
    """Symmetric n×n travel-cost matrix (NPR). O(n²)."""
    n = len(points)
    m = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            c = haversine_km(points[i], points[j]) * COST_PER_KM
            m[i][j] = m[j][i] = c
    return m


def _route_travel(order: list[int], m: list[list[float]]) -> float:
    """Total leg travel cost of visiting indices in `order`. O(n)."""
    return sum(m[order[i]][order[i + 1]] for i in range(len(order) - 1))


def nearest_neighbour(m: list[list[float]], start: int = 0) -> list[int]:
    """Greedy nearest-neighbour tour (open path) from `start`. O(n²)."""
    n = len(m)
    unvisited = set(range(n))
    unvisited.discard(start)
    order = [start]
    current = start
    while unvisited:
        nxt = min(unvisited, key=lambda j: m[current][j])
        order.append(nxt)
        unvisited.discard(nxt)
        current = nxt
    return order


def two_opt(order: list[int], m: list[list[float]]) -> list[int]:
    """Improve an open path by reversing segments while it lowers travel cost.

    Keeps index 0 fixed (the start). Repeats passes until no improving swap is
    found. Each pass is O(n²); returns a route whose cost is ≤ the input's.
    """
    best = order[:]
    improved = True
    while improved:
        improved = False
        for i in range(1, len(best) - 1):
            for k in range(i + 1, len(best)):
                candidate = best[:i] + best[i : k + 1][::-1] + best[k + 1 :]
                if _route_travel(candidate, m) + 1e-9 < _route_travel(best, m):
                    best = candidate
                    improved = True
    return best


def _optimise_order(points: list[Point], start_idx: int) -> list[int]:
    m = cost_matrix(points)
    return two_opt(nearest_neighbour(m, start_idx), m)


def optimize(
    points: list[Point], budget_npr: int | None = None, start_index: int = 0
) -> OptimizedRoute:
    """Return a minimum-cost, budget-feasible route over `points`.

    `points[start_index]` is the fixed origin; if it is a virtual start (id -1,
    visit_cost 0) it is not reported as a stop. When the total (travel + visits)
    exceeds `budget_npr`, drop the stop whose removal saves the most and
    re-optimise, until feasible or only the start remains. O(n³) worst case for
    the drop loop (n small).
    """
    working = points[:]
    start_id = points[start_index].id
    dropped: list[int] = []

    def build(pts: list[Point]) -> tuple[list[int], list[list[float]], list[int]]:
        s = next(i for i, p in enumerate(pts) if p.id == start_id)
        order_idx = _optimise_order(pts, s)
        m = cost_matrix(pts)
        return order_idx, m, s

    order_idx, m, _ = build(working)

    def totals(order_idx, m, pts):
        travel = _route_travel(order_idx, m)
        visits = sum(pts[i].visit_cost for i in order_idx)
        return travel, visits, travel + visits

    travel, visits, total = totals(order_idx, m, working)

    # Drop stops that bust the budget, most-saving first.
    while budget_npr is not None and total > budget_npr and len(working) > 1:
        best_removal, best_saving = None, -1.0
        for p in working:
            if p.id == start_id:
                continue
            trial = [q for q in working if q.id != p.id]
            oi, tm, _ = build(trial)
            _, _, t_total = totals(oi, tm, trial)
            saving = total - t_total
            if saving > best_saving:
                best_saving, best_removal = saving, p.id
        if best_removal is None:
            break
        dropped.append(best_removal)
        working = [q for q in working if q.id != best_removal]
        order_idx, m, _ = build(working)
        travel, visits, total = totals(order_idx, m, working)

    # Assemble the result, excluding a virtual start from reported stops.
    ordered_points = [working[i] for i in order_idx]
    leg_costs: list[int] = []
    stop_ids: list[int] = []
    prev = None
    for p in ordered_points:
        leg = 0.0 if prev is None else haversine_km(prev, p) * COST_PER_KM
        prev = p
        if p.id == start_id and p.visit_cost == 0 and p.id == -1:
            continue  # virtual start: not a stop
        stop_ids.append(p.id)
        leg_costs.append(round(leg))

    return OptimizedRoute(
        order=stop_ids,
        leg_costs=leg_costs,
        travel_cost_npr=round(travel),
        visit_cost_npr=round(visits),
        total_cost_npr=round(total),
        dropped=dropped,
    )
