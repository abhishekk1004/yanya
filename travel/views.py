from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Prefetch
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .collaborative import collaborative_recommend, hybrid_recommend
from .constants import CATEGORY_KEYS, CATEGORY_LABELS
from .forms import SignupForm
from .fuzzy import recommend_hotels
from .media import GALLERY
from .models import (
    Category,
    Destination,
    DestinationCategory,
    Hotel,
    Interaction,
    Itinerary,
    Province,
)
from .recommender import similar_destinations

_WEIGHTS_PREFETCH = Prefetch(
    "category_weights", queryset=DestinationCategory.objects.select_related("category")
)


def _catalog_qs():
    return (
        Destination.objects.select_related("province").prefetch_related(_WEIGHTS_PREFETCH)
    )


def home(request):
    return render(request, "home.html", {"gallery": GALLERY})


def destinations(request):
    qs = _catalog_qs()
    province = request.GET.get("province", "")
    category = request.GET.get("category", "")
    q = request.GET.get("q", "").strip()
    if province:
        qs = qs.filter(province__slug=province)
    if category:
        qs = qs.filter(category_weights__category__key=category).distinct()
    if q:
        qs = qs.filter(name__icontains=q)


    picked, loved = [], []
    if request.user.is_authenticated and not (province or category or q):
        picked = [s.destination for s in hybrid_recommend(request.user, top_n=6)]
        loved = [s.destination for s in collaborative_recommend(request.user, top_n=6)]

    grid = list(qs.order_by("-popularity", "name")[:60])
    saved = _saved_ids(request.user)
    for d in grid + picked + loved:
        d.is_saved = d.id in saved

    context = {
        "destinations": grid,
        "picked": picked,
        "travellers_loved": loved,
        "provinces": Province.objects.all(),
        "categories": Category.objects.all(),
        "selected": {"province": province, "category": category, "q": q},
        "gallery": GALLERY,
    }
    if request.htmx and request.GET.get("grid"):
        return render(request, "partials/destination_grid.html", context)
    return render(request, "destinations.html", context)


def destination_suggest(request):
    q = request.GET.get("q", "").strip()
    matches = (
        Destination.objects.select_related("province").filter(name__icontains=q)[:6]
        if q else []
    )
    return render(request, "partials/suggestions.html", {"matches": matches})


def _saved_ids(user) -> set[int]:
    if not user.is_authenticated:
        return set()
    return set(
        Interaction.objects.filter(user=user, event=Interaction.SAVE)
        .values_list("destination_id", flat=True)
    )


@login_required
@require_POST
def save_toggle(request, pk):
    dest = get_object_or_404(Destination, pk=pk)
    qs = Interaction.objects.filter(
        user=request.user, destination=dest, event=Interaction.SAVE
    )
    if qs.exists():
        qs.delete()
        saved = False
    else:
        Interaction.objects.create(user=request.user, destination=dest, event=Interaction.SAVE)
        saved = True
    _bump_reco(request.user.id)
    return render(request, "partials/save_button.html", {"d": dest, "saved": saved})


def _bump_reco(user_id: int) -> None:
    key = f"reco_ver:{user_id}"
    cache.set(key, cache.get(key, 0) + 1)


def _user_ratings(user) -> dict[int, int]:
    if not user.is_authenticated:
        return {}
    out: dict[int, int] = {}
    for it in (
        Interaction.objects.filter(
            user=user, event=Interaction.RATE, rating__isnull=False
        ).order_by("created_at").values("destination_id", "rating")
    ):
        out[it["destination_id"]] = it["rating"] 
    return out


def _can_rate(user, dest) -> bool:
    return Itinerary.objects.filter(
        user=user, completed=True, stops__destination=dest
    ).exists()


@login_required
@require_POST
def rate_place(request, pk):

    dest = get_object_or_404(Destination, pk=pk)
    if not _can_rate(request.user, dest):
        return HttpResponseForbidden("Finish a trip with this place before rating it.")
    try:
        stars = int(request.POST.get("stars", 0))
    except (TypeError, ValueError):
        stars = 0
    stars = stars if 1 <= stars <= 5 else 0
    Interaction.objects.filter(
        user=request.user, destination=dest, event=Interaction.RATE
    ).delete()
    if stars:
        Interaction.objects.create(
            user=request.user, destination=dest, event=Interaction.RATE, rating=stars
        )
    _bump_reco(request.user.id)
    return render(request, "partials/rate_stars.html", {"d": dest, "rating": stars})



def signup(request):
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("quiz")
    else:
        form = SignupForm()
    return render(request, "signup.html", {"form": form})


@login_required
def quiz(request):
    pref = request.user.preference
    if request.method == "POST":
        weights = {}
        for key in CATEGORY_KEYS:
            try:
                weights[key] = min(1.0, max(0.0, float(request.POST.get(key, 0)) / 100))
            except (TypeError, ValueError):
                weights[key] = 0.0
        pref.weights = weights
        try:
            pref.budget_npr = int(request.POST.get("budget_npr", pref.budget_npr))
            pref.max_difficulty = int(request.POST.get("max_difficulty", pref.max_difficulty))
        except (TypeError, ValueError):
            pass
        pref.quiz_completed = True
        pref.save()
        messages.success(request, "All set — here's what we'd explore for you.")
        return redirect("destinations")

    interests = [
        {"key": k, "label": CATEGORY_LABELS[k],
         "value": int(round(pref.weights.get(k, 0.0) * 100))}
        for k in CATEGORY_KEYS
    ]
    return render(request, "quiz.html", {"interests": interests, "preference": pref})


@login_required
def profile(request):
    return render(request, "profile.html", {"preference": request.user.preference})


@login_required
def favourites(request):
    saved_ids = list(
        Interaction.objects.filter(user=request.user, event=Interaction.SAVE)
        .values_list("destination_id", flat=True).distinct()
    )
    saved = list(_catalog_qs().filter(id__in=saved_ids))
    for d in saved:
        d.is_saved = True
    also = [s.destination for s in similar_destinations(saved_ids, top_n=4)] if saved_ids else []
    saved_set = set(saved_ids)
    for d in also:
        d.is_saved = d.id in saved_set
    return render(request, "favourites.html", {"saved": saved, "also_like": also})


def stays(request):
    province = request.GET.get("province", "")
    try:
        budget = int(request.GET.get("budget", 6000))
    except (TypeError, ValueError):
        budget = 6000
    hotels = Hotel.objects.select_related("province")
    if province:
        hotels = hotels.filter(province__slug=province)
    ranked = recommend_hotels(list(hotels), budget)
    for hs in ranked:              # attach score to the hotel for the template
        hs.hotel.fuzzy_score = hs.score
    return render(request, "stays.html", {
        "hotels": [hs.hotel for hs in ranked],
        "provinces": Province.objects.all(),
        "selected": {"province": province, "budget": budget},
    })


@login_required
def trips(request):
    ratings = _user_ratings(request.user)
    trips_qs = (
        Itinerary.objects.filter(user=request.user)
        .prefetch_related("stops__destination__province")
    )
    trip_list = list(trips_qs)
    for trip in trip_list:
        for stop in trip.stops.all():
            stop.destination.user_rating = ratings.get(stop.destination_id, 0)
    return render(request, "trips.html", {"trips": trip_list})


@login_required
@require_POST
def complete_trip(request, pk):
    trip = get_object_or_404(Itinerary, pk=pk, user=request.user)
    if not trip.completed:
        trip.completed = True
        trip.completed_at = timezone.now()
        trip.save(update_fields=["completed", "completed_at"])
    return redirect("trips")


@login_required
def vasatyayam(request):
    preselect = [int(i) for i in request.GET.getlist("d") if i.isdigit()]
    dests = _catalog_qs().order_by("province__order", "name")
    return render(
        request,
        "vasatyayam.html",
        {"destinations": dests, "budget_default": request.user.preference.budget_npr,
         "preselect": preselect, "gallery": GALLERY},
    )
