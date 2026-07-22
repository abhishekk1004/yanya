from __future__ import annotations
import math
from dataclasses import dataclass, field

COST_PER_KM = 15.0  

@dataclass
class Point:
    id: int         
    lat: float
    lng: float
    visit_cost: int  


@dataclass
class OptimizedRoute:
    order: list[int]              
    leg_costs: list[int]         
    travel_cost_npr: int
    visit_cost_npr: int
    total_cost_npr: int
    dropped: list[int] = field(default_factory=list)


def haversine_km(a: Point, b: Point) -> float:
    r = 6371.0
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dphi = math.radians(b.lat - a.lat)
    dlmb = math.radians(b.lng - a.lng)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def cost_matrix(points: list[Point]) -> list[list[float]]:
    n = len(points)
    m = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            c = haversine_km(points[i], points[j]) * COST_PER_KM
            m[i][j] = m[j][i] = c
    return m


def _route_travel(order: list[int], m: list[list[float]]) -> float:

    return sum(m[order[i]][order[i + 1]] for i in range(len(order) - 1))


def nearest_neighbour(m: list[list[float]], start: int = 0) -> list[int]:
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


    ordered_points = [working[i] for i in order_idx]
    leg_costs: list[int] = []
    stop_ids: list[int] = []
    prev = None
    for p in ordered_points:
        leg = 0.0 if prev is None else haversine_km(prev, p) * COST_PER_KM
        prev = p
        if p.id == start_id and p.visit_cost == 0 and p.id == -1:
            continue  
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
