"""Phase 2 — catalog API: destinations, popular, provinces?include=spots."""
import pytest

from .conftest import make_destination

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded(province, categories):
    make_destination(province, categories, "Temple A", {"religious": 1.0, "popular": 0.9},
                     cost_npr=5000, difficulty=1)
    make_destination(province, categories, "Trek B", {"trekking": 1.0, "adventure": 0.9},
                     cost_npr=90000, difficulty=5)
    return province


def test_provinces_include_spots(api, seeded):
    resp = api.get("/api/provinces?include=spots")
    assert resp.status_code == 200
    body = resp.json()
    assert isinstance(body, list) and len(body) == 1
    assert "spots" in body[0] and len(body[0]["spots"]) == 2


def test_destinations_filter_by_category(api, seeded):
    resp = api.get("/api/destinations?category=trekking")
    assert resp.status_code == 200
    names = [d["name"] for d in resp.json()["results"]]
    assert names == ["Trek B"]


def test_destinations_search(api, seeded):
    resp = api.get("/api/destinations?q=temple")
    assert [d["name"] for d in resp.json()["results"]] == ["Temple A"]


def test_popular_orders_by_popularity(api, seeded):
    # Popularity baseline is set by seed_provinces; here set it explicitly.
    from travel.models import Destination
    Destination.objects.filter(name="Temple A").update(popularity=90)
    Destination.objects.filter(name="Trek B").update(popularity=10)
    resp = api.get("/api/destinations/popular")
    names = [d["name"] for d in resp.json()]
    assert names[0] == "Temple A"


def test_destination_detail_logs_view_for_authed_user(auth_api, seeded):
    from travel.models import Destination, Interaction
    dest = Destination.objects.get(name="Temple A")
    resp = auth_api.get(f"/api/destinations/{dest.id}")
    assert resp.status_code == 200
    assert Interaction.objects.filter(destination=dest, event=Interaction.VIEW).count() == 1
