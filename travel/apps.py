from django.apps import AppConfig


class TravelConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'travel'

    def ready(self):
        from . import signals  # noqa: F401  (register post_save handlers)
