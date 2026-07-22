"""Admin registrations. DestinationCategory is edited inline on a destination
so curators set the feature-vector weights right where they edit the place.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    Category,
    Destination,
    DestinationCategory,
    Interaction,
    Itinerary,
    ItineraryStop,
    Profile,
    Province,
    User,
    UserPreference,
)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    pass


@admin.register(Province)
class ProvinceAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "center_lat", "center_lng")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("order",)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("key", "label")


class DestinationCategoryInline(admin.TabularInline):
    model = DestinationCategory
    extra = 1
    autocomplete_fields = ("category",)


@admin.register(Destination)
class DestinationAdmin(admin.ModelAdmin):
    list_display = (
        "name", "province", "difficulty", "cost_npr", "popularity", "is_featured",
    )
    list_filter = ("province", "difficulty", "best_season", "is_featured")
    search_fields = ("name", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [DestinationCategoryInline]


@admin.register(Interaction)
class InteractionAdmin(admin.ModelAdmin):
    list_display = ("user", "event", "destination", "rating", "created_at")
    list_filter = ("event",)
    raw_id_fields = ("user", "destination")


class ItineraryStopInline(admin.TabularInline):
    model = ItineraryStop
    extra = 0


@admin.register(Itinerary)
class ItineraryAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "budget_npr", "total_cost_npr", "created_at")
    inlines = [ItineraryStopInline]


admin.site.register(Profile)
admin.site.register(UserPreference)

# Category needs search enabled for the inline autocomplete above.
CategoryAdmin.search_fields = ("key", "label")
