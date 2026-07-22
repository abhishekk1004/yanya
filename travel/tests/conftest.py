"""Shared pytest fixtures."""
import pytest
from rest_framework.test import APIClient

from travel.models import Category, Destination, DestinationCategory, Province, User
from travel.constants import CATEGORY_KEYS


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def user(db) -> User:
    return User.objects.create_user(
        username="sita", email="sita@example.com", password="trekNepal123"
    )


@pytest.fixture
def auth_api(api, user) -> APIClient:
    """An APIClient authenticated as ``user`` via JWT."""
    resp = api.post(
        "/api/auth/login",
        {"username": "sita", "password": "trekNepal123"},
        format="json",
    )
    api.credentials(HTTP_AUTHORIZATION="Bearer " + resp.json()["access"])
    return api


@pytest.fixture
def categories(db) -> dict[str, Category]:
    return {
        key: Category.objects.create(key=key, label=key.title())
        for key in CATEGORY_KEYS
    }


@pytest.fixture
def province(db) -> Province:
    return Province.objects.create(
        name="Bagmati", slug="bagmati", order=3, center_lat=27.7, center_lng=85.3
    )


def make_destination(province, categories, name, weights, **kwargs) -> Destination:
    """Create a destination and its category-weight feature vector."""
    dest = Destination.objects.create(
        name=name,
        slug=name.lower().replace(" ", "-"),
        province=province,
        lat=kwargs.get("lat", 27.7),
        lng=kwargs.get("lng", 85.3),
        cost_npr=kwargs.get("cost_npr", 5000),
        difficulty=kwargs.get("difficulty", 1),
        best_season=kwargs.get("best_season", "all"),
    )
    for key, w in weights.items():
        DestinationCategory.objects.create(
            destination=dest, category=categories[key], weight=w
        )
    return dest
