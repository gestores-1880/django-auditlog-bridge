from django.conf import settings

settings.CORRELATION_ID_MAX_AGE_SECONDS = getattr(
    settings, "CORRELATION_ID_MAX_AGE_SECONDS", 10
)

settings.REGISTER_ADMIN_LOGS = getattr(settings, "REGISTER_ADMIN_LOGS", True)

settings.ADMIN_URL = getattr(settings, "ADMIN_URL", "admin/")
