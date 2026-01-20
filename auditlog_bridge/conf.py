from django.conf import settings

settings.CORRELATION_ID_MAX_AGE_SECONDS = getattr(
    settings, "CORRELATION_ID_MAX_AGE_SECONDS", 10
)
