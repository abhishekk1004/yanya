"""Phase 3 — recommender: cold start, differentiation, behavioural blend,
hard filters, and the offline evaluation beating the baselines."""
import pytest

from travel.evaluation import evaluate, synth_dataset
from travel.models import Interaction, User
from travel.recommender import recommend
from .conftest import make_destination

pytestmark = pytest.mark.django_db


@pytest.fixture
def catalog(province, categories):
    return {
        "temple": make_destination(province, categories, "Temple",
                                   {"religious": 1.0, "historic": 0.6, "popular": 0.7},
                                   cost_npr=5000, difficulty=1),
        "trek": make_destination(province, categories, "Trek",
                                 {"trekking": 1.0, "adventure": 0.9, "hiking": 0.8},
                                 cost_npr=40000, difficulty=4),
        "museum": make_destination(province, categories, "Museum",
                                   {"historic": 1.0, "popular": 0.4},
                                   cost_npr=3000, difficulty=1),
    }


def _mkuser(name, weights):
    u = User.objects.create_user(name, f"{name}@x.com", "trekNepal123")
    u.preference.weights = weights
    u.preference.save()
    return u


def test_cold_start_uses_quiz_weights(catalog):
    pilgrim = _mkuser("pil", {"religious": 1.0, "historic": 0.5, "trekking": 0.0,
                              "adventure": 0.0, "hiking": 0.0, "popular": 0.3})
    top = recommend(pilgrim, top_n=1)
    assert top[0].destination.name == "Temple"


def test_different_quizzes_give_different_lists(catalog):
    pilgrim = _mkuser("pil", {"religious": 1.0, "historic": 0.4, "popular": 0.3,
                              "trekking": 0.0, "adventure": 0.0, "hiking": 0.0})
    trekker = _mkuser("trek", {"trekking": 1.0, "adventure": 0.9, "hiking": 0.8,
                               "religious": 0.0, "historic": 0.0, "popular": 0.0})
    assert recommend(pilgrim, top_n=1)[0].destination.name == "Temple"
    assert recommend(trekker, top_n=1)[0].destination.name == "Trek"


def test_no_taste_falls_back_to_popularity(catalog):
    catalog["trek"].popularity = 99
    catalog["trek"].save()
    blank = User.objects.create_user("blank", "blank@x.com", "trekNepal123")
    # No quiz weights, no interactions -> popularity ordering, non-empty.
    top = recommend(blank, top_n=3)
    assert top and top[0].destination.name == "Trek"


def _score_of(user, name):
    return next(s.score for s in recommend(user, top_n=10)
               if s.destination.name == name)


def test_behaviour_shifts_taste(catalog):
    # Start trek-leaning; religious/historic signals should raise the temple's
    # score (behaviour is weighted more as interactions accumulate).
    u = _mkuser("mix", {"trekking": 0.6, "adventure": 0.5, "religious": 0.1,
                        "historic": 0.0, "hiking": 0.3, "popular": 0.2})
    before = _score_of(u, "Temple")
    for _ in range(3):
        Interaction.objects.create(user=u, destination=catalog["temple"],
                                   event=Interaction.RATE, rating=5)
    Interaction.objects.create(user=u, destination=catalog["museum"],
                               event=Interaction.SAVE)
    after = _score_of(u, "Temple")
    assert after > before


def test_visited_hidden_and_budget_filter(catalog):
    u = _mkuser("b", {"trekking": 1.0, "adventure": 0.9, "hiking": 0.8,
                     "religious": 0.0, "historic": 0.0, "popular": 0.0})
    u.preference.budget_npr = 10000  # excludes the 40000 trek
    u.preference.save()
    names = [s.destination.name for s in recommend(u, top_n=10)]
    assert "Trek" not in names  # busted budget
    # Visit the temple -> it disappears from future recommendations.
    Interaction.objects.create(user=u, destination=catalog["temple"],
                               event=Interaction.VISITED)
    assert "Temple" not in [s.destination.name for s in recommend(u, top_n=10)]


def test_evaluation_beats_baselines():
    m = evaluate(synth_dataset(n_users=120, seed=42), k=5, seed=42)
    assert m.rmse < m.baseline_rmse
    assert m.mae < m.baseline_mae
    assert m.recall_at_k > m.random_recall_at_k
