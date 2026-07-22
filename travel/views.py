"""HTMX / server-rendered page views. The browser app uses Django session auth;
the JSON API additionally accepts JWT. Data is read straight from the ORM with
select_related/prefetch_related to keep vector reads off the N+1 path.
"""
from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch
from django.shortcuts import redirect, render

from .constants import CATEGORY_KEYS, CATEGORY_LABELS
from .forms import SignupForm
from .models import Category, Destination, DestinationCategory, Province
from .recommender import recommend

_WEIGHTS_PREFETCH = Prefetch(
    "category_weights",
    queryset=DestinationCategory.objects.select_related("category"),
)


def home(request):
    return render(request, "home.html")


def destinations(request):  
    qs = (
        Destination.objects.select_related("province")
        .prefetch_related(_WEIGHTS_PREFETCH)
        .order_by("-popularity", "name")
    )
    province = request.GET.get("province", "")
    category = request.GET.get("category", "")
    q = request.GET.get("q", "").strip()
    if province:
        qs = qs.filter(province__slug=province)
    if category:
        qs = qs.filter(category_weights__category__key=category).distinct()
    if q:
        qs = qs.filter(name__icontains=q)

    context = {
        "destinations": qs[:60],
        "provinces": Province.objects.all(),
        "categories": Category.objects.all(),
        "selected": {"province": province, "category": category, "q": q},
    }
   
    template = "partials/destination_grid.html" if request.htmx else "destinations.html"
    return render(request, template, context)



def signup(request):
   
    if request.user.is_authenticated:
        return redirect("home")
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Welcome! Tell us what you love to explore.")
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
        messages.success(request, "Preferences saved. Here's what we'd explore.")
        return redirect("recommendations")

    sliders = [
        {"key": key, "label": CATEGORY_LABELS[key],
         "value": int(round(pref.weights.get(key, 0.0) * 100))}
        for key in CATEGORY_KEYS
    ]
    return render(request, "quiz.html", {"sliders": sliders, "preference": pref})


@login_required
def profile(request):
    return render(request, "profile.html", {"preference": request.user.preference})



@login_required
def recommendations(request):
   
    province = request.GET.get("province") or None
    scored = recommend(request.user, province=province, top_n=12)
    recs = [s.destination for s in scored]
    return render(
        request,
        "recommendations.html",
        {"recommendations": recs, "provinces": Province.objects.all(),
         "selected_province": province or ""},
    )


@login_required
def planner(request):
    
    dests = (
        Destination.objects.select_related("province").order_by("province__order", "name")
    )
    return render(
        request,
        "planner.html",
        {"destinations": dests, "budget_default": request.user.preference.budget_npr},
    )
