import pytest
from django.test import Client

from travel.collaborative import collaborative_recommend, hybrid_recommend
from travel.models import Interaction, User
from .conftest import make_destination

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalog(province, categories):
    return {
        "temple": make_destination(province, categories, "Temple", {"religious": 1.0}),
        "trek": make_destination(province, categories, "Trek", {"trekking": 1.0}),
        "lake": make_destination(province, categories, "Lake", {"hiking": 1.0}),
        "museum": make_destination(province, categories, "Museum", {"historic": 1.0}),
    }


def _completed_trip(user, dest):
    from travel.models import Itinerary, ItineraryStop
    trip = Itinerary.objects.create(user=user, name="Done", completed=True)
    ItineraryStop.objects.create(itinerary=trip, destination=dest, order=1)
    return trip


def test_rating_requires_completed_trip(catalog):
    u = User.objects.create_user("r", "r@x.com", "trekNepal123")
    c = Client(); c.force_login(u)
    d = catalog["temple"]
    assert c.post(f"/destinations/{d.id}/rate/", {"stars": 4}).status_code == 403
    assert not Interaction.objects.filter(user=u, destination=d, event="rate").exists()


def test_rate_place_records_and_replaces(catalog):
    u = User.objects.create_user("r", "r@x.com", "trekNepal123")
    d = catalog["temple"]
    _completed_trip(u, d)
    c = Client(); c.force_login(u)
    r1 = c.post(f"/destinations/{d.id}/rate/", {"stars": 4})
    assert r1.status_code == 200 and b"4/5" in r1.content
    assert Interaction.objects.filter(user=u, destination=d, event="rate").count() == 1

    c.post(f"/destinations/{d.id}/rate/", {"stars": 2})
    q = Interaction.objects.filter(user=u, destination=d, event="rate")
    assert q.count() == 1 and q.first().rating == 2


def test_collaborative_recommends_from_similar_user(catalog):

    ann = User.objects.create_user("ann", "ann@x.com", "trekNepal123")
    bob = User.objects.create_user("bob", "bob@x.com", "trekNepal123")
    Interaction.objects.create(user=ann, destination=catalog["temple"], event="rate", rating=5)
    Interaction.objects.create(user=bob, destination=catalog["temple"], event="rate", rating=5)
    Interaction.objects.create(user=bob, destination=catalog["museum"], event="rate", rating=5)

    names = [s.destination.name for s in collaborative_recommend(ann, top_n=3)]
    assert "Museum" in names

    assert "Temple" not in names


def test_collaborative_cold_start_is_empty(catalog):
    loner = User.objects.create_user("lone", "lone@x.com", "trekNepal123")
    assert collaborative_recommend(loner, top_n=3) == []


def test_hybrid_falls_back_to_content_without_cf(catalog):
    u = User.objects.create_user("h", "h@x.com", "trekNepal123")
    u.preference.weights = {"religious": 1.0, "trekking": 0.0, "adventure": 0.0,
                            "historic": 0.0, "hiking": 0.0, "popular": 0.0}
    u.preference.save()

    top = hybrid_recommend(u, top_n=1)
    assert top and top[0].destination.name == "Temple"


def test_recommendations_api_methods(auth_api, catalog):
    for method in ("content", "cf", "hybrid"):
        resp = auth_api.get(f"/api/recommendations?method={method}")
        assert resp.status_code == 200
