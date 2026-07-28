
from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.db.models import Prefetch
from rest_framework import generics, permissions
from rest_framework.response import Response

from django.db import transaction
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView

from .fuzzy import recommend_hotels
from .itinerary import COST_PER_KM, Point, optimize
from .recommender import similar_destinations
from .transport import recommend_transport

PER_DIEM_NPR = 3000  


def _route_breakdown(route, budget):
    distance_km = round(route.travel_cost_npr / COST_PER_KM)
    n = len(route.order)
    days = max(1, round(n * 0.75 + distance_km / 300))
    lodging_food = days * PER_DIEM_NPR
    grand_total = route.total_cost_npr + lodging_food
    return {
        "distance_km": distance_km,
        "days": days,
        "transport_rate_npr_per_km": COST_PER_KM,
        "per_diem_npr": PER_DIEM_NPR,
        "lodging_food_npr": lodging_food,
        "grand_total_npr": grand_total,
        "within_budget": budget is None or grand_total <= budget,
    }
from .models import (
    Category,
    Destination,
    DestinationCategory,
    Hotel,
    Interaction,
    Itinerary,
    ItineraryStop,
    Province,
    TransportMode,
    UserPreference,
)
from .recommender import recommend
from .serializers import (
    DestinationSerializer,
    HotelSerializer,
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
            spots = (
                Destination.objects.order_by("-popularity", "name")
                .prefetch_related("category_weights__category")
            )
            qs = qs.prefetch_related(
                Prefetch("destinations", queryset=spots, to_attr="famous_spots")
            )
        return qs


class DestinationListView(generics.ListAPIView):

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
        _bump_reco_version(request.user.id)
        return Response(serializer.data, status=201)


class RecommendationsView(generics.GenericAPIView):
    serializer_class = DestinationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        from .collaborative import collaborative_recommend, hybrid_recommend

        province = request.query_params.get("province")
        method = request.query_params.get("method", "hybrid")
        try:
            top_n = min(50, max(1, int(request.query_params.get("top_n", 10))))
        except (TypeError, ValueError):
            top_n = 10
        version = cache.get(f"reco_ver:{request.user.id}", 0)
        cache_key = f"reco:{request.user.id}:{version}:{method}:{province or ''}:{top_n}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        if method == "cf":
            scored = collaborative_recommend(request.user, top_n=top_n)
        elif method == "content":
            scored = recommend(request.user, province=province, top_n=top_n)
        else: 
            scored = hybrid_recommend(request.user, top_n=top_n)
        data = [
            {**self.get_serializer(s.destination).data, "score": round(s.score, 4)}
            for s in scored
        ]
        cache.set(cache_key, data, settings.CACHE_TTL_RECOMMENDATIONS)
        return Response(data)


def _nearest_province(lat, lng):

    from .itinerary import haversine_km

    p = Point(id=0, lat=lat, lng=lng, visit_cost=0)
    provinces = list(Province.objects.all())
    return min(
        provinces,
        key=lambda pr: haversine_km(p, Point(0, pr.center_lat, pr.center_lng, 0)),
        default=None,
    )


def _valid_place(p):

    try:
        float(p["lat"]); float(p["lng"])
        return True
    except (KeyError, TypeError, ValueError):
        return False


def _collect_points(user, destination_ids, custom, start, from_place=None, to_place=None):

    def place_point(pid, place, meta):
        lat, lng, cost = float(place["lat"]), float(place["lng"]), int(place.get("cost") or 0)
        meta[pid] = {"destination": None, "name": (place.get("name") or "Stop")[:120],
                     "lat": lat, "lng": lng, "cost": cost}
        return Point(id=pid, lat=lat, lng=lng, visit_cost=cost)

    dests = list(
        Destination.objects.select_related("province").filter(id__in=destination_ids)
    )
    meta: dict[int, dict] = {}
    points: list[Point] = []
    for d in dests:
        points.append(Point(id=d.id, lat=d.lat, lng=d.lng, visit_cost=d.cost_npr))
        meta[d.id] = {"destination": d, "name": d.name, "lat": d.lat, "lng": d.lng,
                      "cost": d.cost_npr}
    for i, c in enumerate(custom or []):
        if not _valid_place(c):
            continue
        key = -(1000 + i)
        points.append(place_point(key, c, meta))


    start_id = None
    if _valid_place(from_place):
        points.append(place_point(-2, from_place, meta))
        start_id = -2
    elif start and str(start).lstrip("-").isdigit() and int(start) in meta:
        start_id = int(start)
    else:
        pref = getattr(user, "preference", None)
        if pref and pref.home_province_id:
            hp = pref.home_province
            points.append(Point(id=-1, lat=hp.center_lat, lng=hp.center_lng, visit_cost=0))
            meta[-1] = {"destination": None, "name": f"Start: {hp.name}",
                        "lat": hp.center_lat, "lng": hp.center_lng, "cost": 0}
            start_id = -1


    end_id = None
    if _valid_place(to_place):
        points.append(place_point(-3, to_place, meta))
        end_id = -3

    if len(points) < 2:
        raise ValidationError("Add at least two places to build a route.")
    if start_id is None:
        start_id = points[0].id

    start_index = next(i for i, p in enumerate(points) if p.id == start_id)
    end_index = next((i for i, p in enumerate(points) if p.id == end_id), None) if end_id else None
    return points, start_index, end_index, meta


def _stop_payload(key, meta):
    m = meta[key]
    if m["destination"] is not None:
        return DestinationSerializer(m["destination"]).data
    return {"id": None, "name": m["name"], "province_name": "Custom stop",
            "lat": m["lat"], "lng": m["lng"], "cost_npr": m["cost"],
            "image_url": "", "custom": True}


class ItineraryOptimizeView(APIView):


    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        ids = request.data.get("destination_ids") or []
        custom = request.data.get("custom") or []
        budget = request.data.get("budget")
        budget = int(budget) if budget not in (None, "") else None
        points, start_index, end_index, meta = _collect_points(
            request.user, ids, custom, request.data.get("start"),
            request.data.get("from_place"), request.data.get("to_place"),
        )
        route = optimize(points, budget_npr=budget, start_index=start_index,
                         end_index=end_index)
        ordered = [
            {"order": i + 1, "destination": _stop_payload(d, meta),
             "leg_cost_npr": route.leg_costs[i]}
            for i, d in enumerate(route.order)
        ]
        breakdown = _route_breakdown(route, budget)

        suggestions = [
            DestinationSerializer(s.destination).data
            for s in similar_destinations([k for k in route.order if k > 0], top_n=4)
        ]

        transport = [
            {"name": r["mode"].name, "emoji": r["mode"].emoji, "cost_npr": r["cost_npr"],
             "hours": r["hours"], "score": r["score"]}
            for r in recommend_transport(TransportMode.objects.all(), breakdown["distance_km"])[:4]
        ]

        province_id = next(
            (meta[k]["destination"].province_id for k in route.order
             if meta[k]["destination"] is not None), None
        )
        nightly = int((budget or route.total_cost_npr) / max(breakdown["days"], 1))
        stays = []
        if province_id:
            hotels = Hotel.objects.filter(province_id=province_id).select_related("province")
            stays = [
                {**HotelSerializer(hs.hotel).data, "fuzzy_score": hs.score}
                for hs in recommend_hotels(hotels, nightly, top_n=4)
            ]
        return Response({
            "order": ordered,
            "travel_cost_npr": route.travel_cost_npr,
            "visit_cost_npr": route.visit_cost_npr,
            "total_cost_npr": route.total_cost_npr,
            "dropped": route.dropped,
            "budget_npr": budget,
            "suggestions": suggestions,
            "transport": transport,
            "stays": stays,
            "nightly_budget_npr": nightly,
            **breakdown,
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
        from django.utils.crypto import get_random_string
        from django.utils.text import slugify

        ids = request.data.get("destination_ids") or []
        custom = request.data.get("custom") or []
        budget = request.data.get("budget")
        budget = int(budget) if budget not in (None, "") else None
        points, start_index, end_index, meta = _collect_points(
            request.user, ids, custom, request.data.get("start"),
            request.data.get("from_place"), request.data.get("to_place"),
        )
        route = optimize(points, budget_npr=budget, start_index=start_index,
                         end_index=end_index)


        for key in route.order:
            m = meta[key]
            if m["destination"] is None:
                prov = _nearest_province(m["lat"], m["lng"])
                m["destination"] = Destination.objects.create(
                    name=m["name"],
                    slug=f"{slugify(m['name']) or 'stop'}-{get_random_string(5).lower()}",
                    province=prov, lat=m["lat"], lng=m["lng"],
                    cost_npr=m["cost"], is_featured=False,
                )

        itinerary = Itinerary.objects.create(
            user=request.user,
            name=request.data.get("name") or "My trip",
            budget_npr=budget or 0,
            total_cost_npr=route.total_cost_npr,
        )
        ItineraryStop.objects.bulk_create([
            ItineraryStop(itinerary=itinerary, destination=meta[d]["destination"],
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


class GeocodeView(APIView):


    permission_classes = [permissions.AllowAny]

    def get(self, request):
        import json as _json
        import ssl
        import urllib.parse
        import urllib.request

        import certifi

        q = (request.query_params.get("q") or "").strip()
        if len(q) < 3:
            return Response([])
        cache_key = f"geocode:{q.lower()}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        params = urllib.parse.urlencode(
            {"q": q, "countrycodes": "np", "format": "json", "limit": 5,
             "accept-language": "en"}  
        )
        url = f"https://nominatim.openstreetmap.org/search?{params}"
        results = []
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Yanya/1.0"})
            ctx = ssl.create_default_context(cafile=certifi.where())
            with urllib.request.urlopen(req, timeout=4, context=ctx) as resp:
                for row in _json.loads(resp.read().decode()):
                    results.append({
                        "name": row.get("display_name", q).split(",")[0],
                        "full_name": row.get("display_name", q),
                        "lat": float(row["lat"]),
                        "lng": float(row["lon"]),
                    })
        except Exception:
            results = []
        cache.set(cache_key, results, 60 * 60)
        return Response(results)


class HotelRecommendView(APIView):

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        province = request.query_params.get("province")
        try:
            budget = int(request.query_params.get("budget", 6000))
        except (TypeError, ValueError):
            budget = 6000
        hotels = Hotel.objects.select_related("province")
        if province:
            hotels = hotels.filter(province__slug=province) if not province.isdigit() \
                else hotels.filter(province_id=int(province))
        data = [
            {**HotelSerializer(hs.hotel).data, "fuzzy_score": hs.score}
            for hs in recommend_hotels(list(hotels), budget)
        ]
        return Response(data)
