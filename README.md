# Nepal Travel Management System

A travel-planning web app for Nepal with a **personalised recommendation system**
at its core. Sign up, tick your interests, and get destination recommendations
across Nepal's 7 provinces. Browse popular spots, tour an interactive map, and
build a cost-optimised trip itinerary.

Built with Django 5 + DRF, a content-based recommender (NumPy + scikit-learn),
and a server-rendered HTMX.

---

## Quick start (local, zero-config)

Local dev uses **SQLite** and needs no Postgres/Redis/Docker. Redis is optional —
without it, caching falls back to in-memory and Celery tasks run eagerly.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python manage.py migrate
python manage.py runserver
```

Open http://127.0.0.1:8000 — the home map tours all 7 provinces. Sign up to take
the interest quiz and see your "For you" list.



## Recommendation system

Content-based, kept lean — **no dense user×destination matrix**:

- Every destination is a weighted vector over six categories
  (`adventure, historic, religious, hiking, trekking, popular`), stored as
  `DestinationCategory.weight ∈ [0,1]`.
- A user's taste is one 6-vector: their **explicit** quiz weights blended with a
  **behavioural** vector (the rating-weighted average of destinations they
  liked). Behaviour is weighted more as interactions accumulate
  (`α = n/(n+K)`), so a brand-new user falls back cleanly to their quiz weights
  — solving cold start.
- Candidates are scored by **cosine similarity** after hard filters
  (budget / difficulty / season / province) and hiding already-visited places.
- Interactions (view/save/rate/visited) are logged; a nightly Celery job
  rebuilds popularity and persists behavioural taste.

Complexity: building taste is `O(interactions × 6)`; serving is one matrix–vector
product, `O(destinations × 6)`.

### Evaluation numbers

80/20 split, on the bundled synthetic dataset (`python manage.py eval_recommender`):

| Metric | Model | Baseline |
|---|---|---|
| RMSE | **0.955** | 1.281 (predict global mean) |
| MAE | **0.794** | 1.130 (predict global mean) |
| Recall@5 | **0.420** | 0.259 (random ranking) |

The model beats both baselines. See [data/README.md](data/README.md) for the
CSV path and how to swap in a real Kaggle tourism dataset (map its
`category`/`type` column via `travel/evaluation.py::CATEGORY_MAP`).

---

## Itinerary builder

Pick destinations → get a minimum-cost, budget-feasible visiting order:

- Travel-cost matrix from haversine distance × `COST_PER_KM`.
- **Nearest-neighbour** construction + **2-opt** improvement.
- If the total (travel + visit costs) busts the budget, greedily drop the stop
  that saves the most and re-optimise until feasible.

The planner draws the route on the map and saves trips.

---

## API surface (JWT or session auth)

```
POST /api/auth/signup · login · refresh
GET/PUT /api/me · /api/me/preferences
GET  /api/provinces?include=spots
GET  /api/destinations  (?province= &category= &q= &page=)
GET  /api/destinations/{id}                 (logs a view)
POST /api/destinations/{id}/interact        (save/rate/visited)
GET  /api/destinations/popular              (?province= &category=)
GET  /api/recommendations                   (?province= &top_n=)
POST /api/itineraries/optimize              (destination_ids[], budget?, start?)
GET/POST /api/itineraries · GET/PUT/DELETE /api/itineraries/{id}
```

The browser app uses Django **session** auth; the same API also accepts **JWT**
(`Authorization: Bearer …`) for programmatic use.

---

## Production / Docker

The same code runs against **PostgreSQL + Redis** in Docker; only environment
variables change (`DATABASE_URL`, `REDIS_URL`, `DEBUG=False`, `SECRET_KEY`).

```bash
docker compose up --build
```

Brings up `web`, `worker` (Celery), `beat` (Celery Beat), `db` (PostGIS) and
`redis`. The `web` service runs `migrate` + `seed_provinces` on start. Prod
settings enable SSL redirect, HSTS, secure cookies, and WhiteNoise static
serving when `DEBUG=False`.

> Note: local dev uses plain `lat`/`lng` float columns + haversine (no PostGIS
> dependency). The Docker image and compose file use the `postgis` image so
> spatial features (pgvector, GeoDjango) can be added later without a rebuild.

---

## Management commands

```bash
python manage.py seed_provinces        # 7 provinces + famous spots (idempotent)
python manage.py generate_synthetic    # write a Kaggle-schema dataset to data/
python manage.py eval_recommender      # RMSE/MAE + Recall@K vs baselines
python manage.py load_boundaries FILE  # real province GeoJSON for the map
```

Nightly Celery tasks: `travel.tasks.refresh_popularity`,
`travel.tasks.rebuild_behavioural_taste` (scheduled in `main/celery.py`).

---

## Project layout

```
main/      settings, urls, wsgi/asgi, celery app + beat schedule
travel/    one app: models, admin, DRF api, HTMX views, forms, serializers,
           recommender.py, itinerary.py, evaluation.py, tasks.py,
           management/commands/, tests/
templates/ base + pages (home, destinations, quiz, recommendations, planner…)
static/    css/app.css (flag theme), js/map.js, js/planner.js
```
