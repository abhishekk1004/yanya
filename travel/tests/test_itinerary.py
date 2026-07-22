"""Phase 4 — itinerary optimiser: 2-opt lowers cost, budget respected, and the
optimize endpoint returns an ordered, budget-feasible route."""
import pytest

from travel.itinerary import (
    Point,
    cost_matrix,
    optimize,
    _route_travel,
    two_opt,
)
from travel.models import User
from .conftest import make_destination

pytestmark = pytest.mark.django_db


def _square_points():
    # Unit-square corners; the crossing order 0-2-1-3 is suboptimal.
    return [Point(0, 27.0, 85.0, 0), Point(1, 27.0, 85.1, 0),
            Point(2, 27.1, 85.1, 0), Point(3, 27.1, 85.0, 0)]


def test_two_opt_reduces_or_keeps_route_cost():
    pts = _square_points()
    m = cost_matrix(pts)
    bad = [0, 2, 1, 3]
    improved = two_opt(bad, m)
    assert _route_travel(improved, m) <= _route_travel(bad, m)
    # Strictly better for this crossing case.
    assert _route_travel(improved, m) < _route_travel(bad, m)


def test_route_within_budget_drops_stops():
    pts = [
        Point(1, 27.0, 85.0, 20000),
        Point(2, 27.0, 85.2, 20000),
        Point(3, 27.2, 85.2, 20000),
        Point(4, 27.2, 85.0, 20000),
    ]
    route = optimize(pts, budget_npr=45000, start_index=0)
    # Two 20k visits already hit 40k; a third busts 45k → at least two dropped.
    assert route.total_cost_npr <= 45000
    assert len(route.order) <= 2
    assert route.dropped


def test_four_places_route_under_budget(province, categories):
    dests = [
        make_destination(province, categories, f"P{i}", {"popular": 0.5},
                         lat=27.0 + i * 0.05, lng=85.0 + i * 0.05, cost_npr=4000)
        for i in range(4)
    ]
    pts = [Point(d.id, d.lat, d.lng, d.cost_npr) for d in dests]
    route = optimize(pts, budget_npr=50000, start_index=0)
    assert len(route.order) == 4
    assert route.total_cost_npr <= 50000
    assert route.order[0] == dests[0].id  # start is fixed


def test_optimize_endpoint(auth_api, province, categories):
    dests = [
        make_destination(province, categories, f"S{i}", {"popular": 0.5},
                         lat=27.0 + i * 0.05, lng=85.0 + i * 0.05, cost_npr=4000)
        for i in range(4)
    ]
    ids = [d.id for d in dests]
    resp = auth_api.post(
        "/api/itineraries/optimize", {"destination_ids": ids, "budget": 60000},
        format="json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["order"]) == 4
    assert body["within_budget"] is True
    assert [o["order"] for o in body["order"]] == [1, 2, 3, 4]


def test_optimize_needs_two_destinations(auth_api, province, categories):
    d = make_destination(province, categories, "Solo", {"popular": 0.5})
    resp = auth_api.post(
        "/api/itineraries/optimize", {"destination_ids": [d.id]}, format="json"
    )
    assert resp.status_code == 400
