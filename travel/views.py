from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Prefetch
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .constants import CATEGORY_KEYS, CATEGORY_LABELS
from .forms import SignupForm
from .media import GALLERY
from .models import Category, Destination, DestinationCategory, Interaction, Province
from .recommender import recommend, similar_destinations

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


    picked = []
    if request.user.is_authenticated and not (province or category or q):
        picked = [s.destination for s in recommend(request.user, top_n=6)]

    grid = list(qs.order_by("-popularity", "name")[:60])
    saved = _saved_ids(request.user)
    for d in grid + picked:
        d.is_saved = d.id in saved

    context = {
        "destinations": grid,
        "picked": picked,
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
    key = f"reco_ver:{request.user.id}"
    cache.set(key, cache.get(key, 0) + 1)
    return render(request, "partials/save_button.html", {"d": dest, "saved": saved})



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
