import pytest
from django.test import Client

from travel.fuzzy import infer, recommend_hotels
from travel.models import Hotel, TransportMode, User
from travel.transport import recommend_transport

pytestmark = pytest.mark.django_db


@pytest.fixture
def hotels(province):
    return [
        Hotel.objects.create(name="Cheap Gem", province=province, city="A",
                             price_npr=2500, star_rating=4.5, lat=27.7, lng=85.3),
        Hotel.objects.create(name="Pricey Basic", province=province, city="B",
                             price_npr=14000, star_rating=2.5, lat=27.7, lng=85.3),
    ]


@pytest.fixture
def modes(db):
    TransportMode.objects.create(name="Local bus", base_fare_npr=100, per_km_npr=4,
                                 speed_kmph=35, comfort=2, min_km=0)
    TransportMode.objects.create(name="Flight", base_fare_npr=6000, per_km_npr=22,
                                 speed_kmph=500, comfort=5, min_km=150)
    return TransportMode.objects.all()


def test_fuzzy_prefers_cheap_high_rated(hotels):
    ranked = recommend_hotels(hotels, budget_per_night=6000)
    assert ranked[0].hotel.name == "Cheap Gem"      
    assert ranked[0].score > ranked[1].score


def test_fuzzy_score_in_range_and_budget_sensitive():
    high = infer(price=3000, budget=8000, rating=4.5)   
    low = infer(price=3000, budget=2000, rating=4.5)    
    assert 0 <= low <= 100 and 0 <= high <= 100
    assert high > low                                   


def test_transport_excludes_flight_for_short_leg(modes):
    short = recommend_transport(modes, distance_km=50)  
    assert "Flight" not in [r["mode"].name for r in short]
    long = recommend_transport(modes, distance_km=400)  
    assert "Flight" in [r["mode"].name for r in long]


def test_transport_scores_and_orders(modes):
    rows = recommend_transport(modes, distance_km=300)
    assert rows and all(0 <= r["score"] <= 100 for r in rows)
    assert rows == sorted(rows, key=lambda r: r["score"], reverse=True)


def test_hotels_api_returns_fuzzy_scores(hotels):
    resp = Client().get("/api/hotels", {"budget": 6000})
    assert resp.status_code == 200
    body = resp.json()
    assert body and "fuzzy_score" in body[0]


def test_stays_page_renders(hotels):
    assert Client().get("/stays/").status_code == 200


def test_optimize_includes_transport_and_stays(auth_api, province, categories, hotels):
    from .conftest import make_destination
    d1 = make_destination(province, categories, "S1", {"popular": 0.5}, lat=27.7, lng=85.3)
    d2 = make_destination(province, categories, "S2", {"popular": 0.5}, lat=28.2, lng=84.0)
    TransportMode.objects.create(name="Bus", base_fare_npr=100, per_km_npr=5,
                                 speed_kmph=40, comfort=3, min_km=0)
    resp = auth_api.post("/api/itineraries/optimize",
                         {"destination_ids": [d1.id, d2.id], "budget": 200000},
                         format="json")
    body = resp.json()
    assert "transport" in body and "stays" in body
    assert len(body["transport"]) >= 1
