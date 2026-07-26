import pytest
from django.test import Client

from travel.models import Interaction, User
from travel.recommender import similar_destinations
from .conftest import make_destination

pytestmark = pytest.mark.django_db


@pytest.fixture
def three(province, categories):
    return [
        make_destination(province, categories, "Temple One", {"religious": 1.0, "historic": 0.6}),
        make_destination(province, categories, "Temple Two", {"religious": 0.9, "popular": 0.5}),
        make_destination(province, categories, "Big Trek", {"trekking": 1.0, "adventure": 0.9},
                         cost_npr=40000, difficulty=4),
    ]


def test_favourites_shows_saved(three):
    u = User.objects.create_user("fav", "fav@x.com", "trekNepal123")
    Interaction.objects.create(user=u, destination=three[0], event=Interaction.SAVE)
    c = Client(); c.force_login(u)
    html = c.get("/choices/").content.decode()
    assert "Temple One" in html
    assert "Plan these in Vasatyayam" in html


def test_autosuggest_returns_matches(three):
    c = Client()
    html = c.get("/destinations/suggest/", {"q": "temple"}).content.decode()
    assert "Temple One" in html and "Temple Two" in html
    assert "Big Trek" not in html


def test_similar_destinations_are_thematic(three):
    sims = similar_destinations([three[0].id], top_n=2)
    names = [s.destination.name for s in sims]
    assert "Temple Two" in names


def test_vasatyayam_optimize_has_breakdown(auth_api, three):
    ids = [three[0].id, three[1].id]
    resp = auth_api.post("/api/itineraries/optimize",
                         {"destination_ids": ids, "budget": 200000}, format="json")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("days", "distance_km", "lodging_food_npr", "grand_total_npr", "suggestions"):
        assert key in body
    assert body["days"] >= 1


def test_home_and_vasatyayam_pages_render(three):
    u = User.objects.create_user("pg", "pg@x.com", "trekNepal123")
    c = Client(); c.force_login(u)
    assert c.get("/").status_code == 200
    assert c.get("/vasatyayam/").status_code == 200
    assert c.get("/destinations/").status_code == 200


def test_save_toggle_adds_then_removes(three):
    u = User.objects.create_user("tg", "tg@x.com", "trekNepal123")
    c = Client(); c.force_login(u)
    d = three[0]
    r1 = c.post(f"/destinations/{d.id}/save/")
    assert r1.status_code == 200 and b"Saved" in r1.content
    assert Interaction.objects.filter(user=u, destination=d, event=Interaction.SAVE).count() == 1
    r2 = c.post(f"/destinations/{d.id}/save/")
    assert b"Save" in r2.content and b"Saved" not in r2.content
    assert Interaction.objects.filter(user=u, destination=d, event=Interaction.SAVE).count() == 0


def test_optimize_accepts_custom_place(auth_api, three):
    resp = auth_api.post("/api/itineraries/optimize", {
        "destination_ids": [three[0].id],
        "custom": [{"name": "Tilicho Lake", "lat": 28.68, "lng": 83.85, "cost": 3000}],
        "budget": 200000,
    }, format="json")
    assert resp.status_code == 200
    names = [o["destination"]["name"] for o in resp.json()["order"]]
    assert "Tilicho Lake" in names


def test_from_to_endpoints_are_pinned(auth_api, three):
    resp = auth_api.post("/api/itineraries/optimize", {
        "destination_ids": [three[0].id, three[1].id],
        "from_place": {"name": "Kathmandu", "lat": 27.70, "lng": 85.32},
        "to_place": {"name": "Pokhara", "lat": 28.21, "lng": 83.98},
        "budget": 300000,
    }, format="json")
    assert resp.status_code == 200
    body = resp.json()
    names = [o["destination"]["name"] for o in body["order"]]
    assert names[0] == "Kathmandu" and names[-1] == "Pokhara"
    assert "transport_rate_npr_per_km" in body


def test_save_trip_persists_custom_place(auth_api, three):
    from travel.models import Destination, Itinerary
    resp = auth_api.post("/api/itineraries", {
        "destination_ids": [three[0].id, three[1].id],
        "custom": [{"name": "Bandipur", "lat": 27.93, "lng": 84.41, "cost": 2000}],
        "budget": 300000, "name": "Custom trip",
    }, format="json")
    assert resp.status_code == 201
    assert Destination.objects.filter(name="Bandipur", is_featured=False).exists()
    trip = Itinerary.objects.get(name="Custom trip")
    assert trip.stops.count() == 3
