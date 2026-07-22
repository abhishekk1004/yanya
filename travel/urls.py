"""URL routes for the travel app: the JSON API under /api/ and the HTMX pages.

Endpoints are wired phase by phase. Phase 0 ships auth + /api/me.
"""
from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import api, views

api_urlpatterns = [
    # Auth
    path("auth/signup", api.SignupView.as_view(), name="api-signup"),
    path("auth/login", TokenObtainPairView.as_view(), name="api-login"),
    path("auth/refresh", TokenRefreshView.as_view(), name="api-refresh"),
    # Me
    path("me", api.MeView.as_view(), name="api-me"),
    path("me/preferences", api.PreferencesView.as_view(), name="api-preferences"),
    # Provinces (home map)
    path("provinces", api.ProvinceListView.as_view(), name="api-provinces"),
    # Destinations — `popular` first so it isn't shadowed by <int:pk>.
    path("destinations/popular", api.PopularDestinationsView.as_view(),
         name="api-destinations-popular"),
    path("destinations", api.DestinationListView.as_view(), name="api-destinations"),
    path("destinations/<int:pk>", api.DestinationDetailView.as_view(),
         name="api-destination-detail"),
    path("destinations/<int:pk>/interact", api.InteractView.as_view(),
         name="api-destination-interact"),
    # Recommendations
    path("recommendations", api.RecommendationsView.as_view(), name="api-recommendations"),
    # Itineraries
    path("itineraries/optimize", api.ItineraryOptimizeView.as_view(),
         name="api-itinerary-optimize"),
    path("itineraries", api.ItineraryListCreateView.as_view(), name="api-itineraries"),
    path("itineraries/<int:pk>", api.ItineraryDetailView.as_view(),
         name="api-itinerary-detail"),
]

# HTMX / server-rendered page routes.
page_urlpatterns = [
    path("", views.home, name="home"),
    path("destinations/", views.destinations, name="destinations"),
    path("signup/", views.signup, name="signup"),
    path("quiz/", views.quiz, name="quiz"),
    path("profile/", views.profile, name="profile"),
    path("recommendations/", views.recommendations, name="recommendations"),
    path("planner/", views.planner, name="planner"),
]

urlpatterns = page_urlpatterns
