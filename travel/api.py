
from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.db.models import Prefetch
from rest_framework import generics, permissions
from rest_framework.response import Response

from django.db import transaction
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from .itinerary import Point, optimize
from .models import (
    Category,
    Destination,
    DestinationCategory,
    Interaction,
    Itinerary,
    ItineraryStop,
    Province,
    UserPreference,
)
from .recommender import recommend
from .serializers import (
    DestinationSerializer,
    InteractionSerializer,
    ItinerarySerializer,
    PreferenceSerializer,
    ProvinceSerializer,
    ProvinceWithSpotsSerializer,
    SignupSerializer,
    UserSerializer,
)


_WEIGHTS_PREFETCH = Prefetch(
    "category_weights",
    queryset=DestinationCategory.objects.select_related("category"),
)


def _destination_qs():
    return (
        Destination.objects.select_related("province")
        .prefetch_related(_WEIGHTS_PREFETCH)
    )


def _bump_reco_version(user_id: int) -> None:
    key = f"reco_ver:{user_id}"
    cache.set(key, cache.get(key, 0) + 1)


class SignupView(generics.CreateAPIView):


    serializer_class = SignupSerializer
    permission_classes = [permissions.AllowAny]


class MeView(generics.RetrieveUpdateAPIView):


    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class PreferencesView(generics.RetrieveUpdateAPIView):


    serializer_class = PreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self) -> UserPreference:
        pref, _ = UserPreference.objects.get_or_create(user=self.request.user)
        return pref

    def perform_update(self, serializer) -> None:
        serializer.save(quiz_completed=True)



class ProvinceListView(generics.ListAPIView):


    permission_classes = [permissions.AllowAny]
    pagination_class = None  

    def get_serializer_class(self):
        if self.request.query_params.get("include") == "spots":
            return ProvinceWithSpotsSerializer
        return ProvinceSerializer

    def get_queryset(self):
        qs = Province.objects.all()

        if self.request.query_params.get("include") == "spots":
            spots = Destination.objects.order_by("-popularity", "name")
            qs = qs.prefetch_related(
                Prefetch("destinations", queryset=spots, to_attr="famous_spots")
            )
        return qs


class DestinationListView(generics.ListAPIView):
    """GET /api/destinations?province=&category=&q=&page= — paginated catalog."""

    serializer_class = DestinationSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = _destination_qs()
        params = self.request.query_params
        if province := params.get("province"):
           
            if province.isdigit():
                qs = qs.filter(province_id=int(province))
            else:
                qs = qs.filter(province__slug=province)
        if category := params.get("category"):
            qs = qs.filter(category_weights__category__key=category).distinct()
        if q := params.get("q"):
            qs = qs.filter(name__icontains=q)
        return qs


class DestinationDetailView(generics.RetrieveAPIView):
    """GET /api/destinations/{id} — detail; logs a view for authed users."""

    serializer_class = DestinationSerializer
    permission_classes = [permissions.AllowAny]
    queryset = _destination_qs()

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        if request.user.is_authenticated:
            Interaction.objects.create(
                user=request.user, destination=self.get_object(), event=Interaction.VIEW
            )
        return response


class PopularDestinationsView(generics.ListAPIView):
    

    serializer_class = DestinationSerializer
    permission_classes = [permissions.AllowAny]
    pagination_class = None

    def get_queryset(self):
        params = self.request.query_params
        qs = _destination_qs().order_by("-popularity", "name")
        if province := params.get("province"):
            if province.isdigit():
                qs = qs.filter(province_id=int(province))
            else:
                qs = qs.filter(province__slug=province)
        if category := params.get("category"):
            qs = qs.filter(category_weights__category__key=category).distinct()
        return qs[:20]

    def list(self, request, *args, **kwargs):
        params = request.query_params
        cache_key = f"popular:{params.get('province','')}:{params.get('category','')}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        data = self.get_serializer(self.get_queryset(), many=True).data
        cache.set(cache_key, data, settings.CACHE_TTL_POPULAR)
        return Response(data)


class InteractView(generics.CreateAPIView):
   

    serializer_class = InteractionSerializer
    permission_classes = [permissions.IsAuthenticated]

    def create(self, request, *args, **kwargs):
        destination = generics.get_object_or_404(Destination, pk=kwargs["pk"])
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user, destination=destination)
        # Bump the user's reco cache version so all cached variants are stale.
        _bump_reco_version(request.user.id)
        return Response(serializer.data, status=201)


class RecommendationsView(generics.GenericAPIView):
    serializer_class = DestinationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        province = request.query_params.get("province")
        try:
            top_n = min(50, max(1, int(request.query_params.get("top_n", 10))))
        except (TypeError, ValueError):
            top_n = 10
        version = cache.get(f"reco_ver:{request.user.id}", 0)
        cache_key = f"reco:{request.user.id}:{version}:{province or ''}:{top_n}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        scored = recommend(request.user, province=province, top_n=top_n)
        data = [
            {**self.get_serializer(s.destination).data, "score": round(s.score, 4)}
            for s in scored
        ]
        cache.set(cache_key, data, settings.CACHE_TTL_RECOMMENDATIONS)
        return Response(data)


def _build_route(user, destination_ids, budget_npr, start):

    dests = list(
        Destination.objects.select_related("province").filter(id__in=destination_ids)
    )
    if len(dests) < 2:
        raise ValidationError("Pick at least two destinations to optimise a route.")
    by_id = {d.id: d for d in dests}
    points = [Point(id=d.id, lat=d.lat, lng=d.lng, visit_cost=d.cost_npr) for d in dests]

    start_index = 0
    if start and int(start) in by_id:
        start_index = next(i for i, p in enumerate(points) if p.id == int(start))
    else:
        pref = getattr(user, "preference", None)
        if pref and pref.home_province_id:
            hp = pref.home_province
            points.insert(0, Point(id=-1, lat=hp.center_lat, lng=hp.center_lng, visit_cost=0))
            start_index = 0

    route = optimize(points, budget_npr=budget_npr, start_index=start_index)
    return route, by_id


class ItineraryOptimizeView(APIView):


    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        ids = request.data.get("destination_ids") or []
        budget = request.data.get("budget")
        budget = int(budget) if budget not in (None, "") else None
        route, by_id = _build_route(request.user, ids, budget, request.data.get("start"))
        ordered = [
            {"order": i + 1, "destination": DestinationSerializer(by_id[d]).data,
             "leg_cost_npr": route.leg_costs[i]}
            for i, d in enumerate(route.order)
        ]
        return Response({
            "order": ordered,
            "travel_cost_npr": route.travel_cost_npr,
            "visit_cost_npr": route.visit_cost_npr,
            "total_cost_npr": route.total_cost_npr,
            "dropped": route.dropped,
            "budget_npr": budget,
            "within_budget": budget is None or route.total_cost_npr <= budget,
        })


class ItineraryListCreateView(generics.ListCreateAPIView):

    serializer_class = ItinerarySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Itinerary.objects.filter(user=self.request.user)
            .prefetch_related("stops__destination")
        )

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        ids = request.data.get("destination_ids") or []
        budget = request.data.get("budget")
        budget = int(budget) if budget not in (None, "") else None
        route, by_id = _build_route(request.user, ids, budget, request.data.get("start"))

        itinerary = Itinerary.objects.create(
            user=request.user,
            name=request.data.get("name") or "My trip",
            budget_npr=budget or 0,
            total_cost_npr=route.total_cost_npr,
        )
        ItineraryStop.objects.bulk_create([
            ItineraryStop(itinerary=itinerary, destination=by_id[d],
                          order=i + 1, leg_cost_npr=route.leg_costs[i])
            for i, d in enumerate(route.order)
        ])
        itinerary.refresh_from_db()
        return Response(self.get_serializer(itinerary).data, status=201)


class ItineraryDetailView(generics.RetrieveUpdateDestroyAPIView):
  
    serializer_class = ItinerarySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Itinerary.objects.filter(user=self.request.user)
            .prefetch_related("stops__destination")
        )
