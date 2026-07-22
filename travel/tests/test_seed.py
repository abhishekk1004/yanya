"""Phase 1 — seed_provinces populates the data spine and is idempotent."""
import pytest
from django.core.management import call_command

from travel.models import Category, Destination, Province

pytestmark = pytest.mark.django_db


def test_seed_creates_all_seven_provinces_and_spots():
    call_command("seed_provinces")
    assert Province.objects.count() == 7
    assert Category.objects.count() == 6
    assert Destination.objects.count() >= 21  # ~3–5 spots per province
    # Every seeded destination carries a non-empty feature vector.
    for dest in Destination.objects.all():
        assert dest.category_weights.exists()


def test_seed_is_idempotent():
    call_command("seed_provinces")
    p1, d1 = Province.objects.count(), Destination.objects.count()
    call_command("seed_provinces")
    assert (Province.objects.count(), Destination.objects.count()) == (p1, d1)
