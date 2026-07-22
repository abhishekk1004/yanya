"""Phase 0 — auth, JWT and /api/me."""
import pytest

pytestmark = pytest.mark.django_db


def test_signup_creates_user_with_profile_and_preference(api):
    resp = api.post(
        "/api/auth/signup",
        {"username": "ram", "email": "ram@example.com", "password": "trekNepal123"},
        format="json",
    )
    assert resp.status_code == 201
    from travel.models import User

    user = User.objects.get(username="ram")
    # Signal auto-provisioned the 1:1 rows.
    assert user.profile is not None
    assert user.preference is not None


def test_me_requires_auth(api):
    assert api.get("/api/me").status_code == 401


def test_login_returns_jwt_and_me_reflects_user(auth_api):
    resp = auth_api.get("/api/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "sita"
    assert "preference" in body and "weights" in body["preference"]


def test_update_preferences_marks_quiz_complete(auth_api):
    resp = auth_api.put(
        "/api/me/preferences",
        {
            "weights": {"trekking": 1.0, "adventure": 0.8},
            "budget_npr": 80000,
            "max_difficulty": 4,
        },
        format="json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["quiz_completed"] is True
    assert body["weights"]["trekking"] == 1.0
    # Unlisted categories are coerced to 0.0 over the full vocabulary.
    assert body["weights"]["religious"] == 0.0
