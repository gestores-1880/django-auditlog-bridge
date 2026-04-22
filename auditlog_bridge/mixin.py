from auditlog.models import LogEntry
from auditlog.context import auditlog_value
from auditlog.middleware import AuditlogMiddleware
from django.contrib.contenttypes.models import ContentType
from django.db.models import Min, Case, When, Q
from django.http import HttpRequest, HttpResponse
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from .constants import HISTORY_MODEL_OPTIONS, HISTORY_MODEL_OPTION_GROUPED, HISTORY_MODEL_OPTION_SINGLE
from .history_generator import HistoryGenerator



class AuditLogBridgeMixin:
    history_option = HISTORY_MODEL_OPTION_SINGLE
    exclude_cid_starting_with = None

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, *args, **kwargs):
        self._check_configuration()
        correlation_ids = self._get_correlation_ids()
        cids_in_page = self.paginate_queryset(correlation_ids)
        if cids_in_page is not None:
            filters = Q(cid__in=cids_in_page) & self._get_filters()
            ordering = Case(*[When(cid=cid, then=pos) for pos, cid in enumerate(cids_in_page)])
            expedient_history = self.history_generator_model().generate(
                logs=LogEntry.objects.select_related("actor")
                .filter(filters)
                .order_by(ordering, "-timestamp"),
                context=self._get_auditlog_bridge_context(),
            )
            return self.get_paginated_response(expedient_history)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _get_auditlog_bridge_context(self):
        return {}

    def _get_correlation_ids(self):
        filters = self._get_filters()
        logentry_qs = LogEntry.objects.filter(filters)

        if self.exclude_cid_starting_with:
            logentry_qs = logentry_qs.exclude(cid__startswith=self.exclude_cid_starting_with)

        return list(
            logentry_qs.values('cid').annotate(
                min_timestamp=Min('timestamp')
            ).order_by('-min_timestamp').values_list('cid', flat=True)
        )

    def _get_filters(self) -> Q:
        """
        Obtiene los filtros para el queryset basados en la opción de historial.
        Devuelve un objeto Q de Django.
        """
        instance = self.get_object()
        content_type = ContentType.objects.get_for_model(model=instance.__class__)
        
        object_filter_component = Q(object_id=instance.id, content_type=content_type)

        if self.history_option == HISTORY_MODEL_OPTION_SINGLE:
            return object_filter_component
        
        if self.history_option == HISTORY_MODEL_OPTION_GROUPED:
            filter_key = f"additional_data__{self.history_generator_filter}"
            grouped_filter_component = Q(**{filter_key: str(instance.id)})
            return grouped_filter_component | object_filter_component
        
        return Q()

    def _check_configuration(self):

        if not hasattr(self, "history_generator_model"):
            raise NotImplementedError(
                "AuditLogBridgeMixin requires a history_generator_model attribute."
            )
        if not issubclass(self.history_generator_model, HistoryGenerator):
            raise ValueError(
                "history_generator_model must be an instance of HistoryGenerator."
            )
        if self.history_option not in HISTORY_MODEL_OPTIONS:
            raise ValueError(f"Invalid history_option value: {self.history_option}.")
        if self.history_option == HISTORY_MODEL_OPTION_GROUPED and not hasattr(
                self, "history_generator_filter"
        ):
            raise NotImplementedError(
                "AuditLogBridgeMixin requires a history_generator_filter attribute."
            )


class AuditlogBridgeJWTAuthViewMixin:
    """
    Mixin for views that sets auditlog actor context for JWT-authenticated requests.

    This mixin is used when JWT authentication is configured in DRF, where the
    standard auditlog middleware cannot capture the authenticated user because
    JWT authentication happens after middleware processing.

    Usage:
        class MyView(AuditlogBridgeJWTAuthViewMixin, APIView):
            ...
    """

    def initial(self, request: HttpRequest, *args: Any, **kwargs: Any) -> None:  # noqa: ANN401
        """
        Initialize the view with auditlog actor context set.
        """
        super().initial(request, *args, **kwargs)  # type: ignore[misc]

        context = auditlog_value.get()
        context["actor"] = AuditlogMiddleware._get_actor(request)
        auditlog_value.set(context)
