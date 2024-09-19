from auditlog.models import LogEntry
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response


class AuditLogBridgeMixin:
    HISTORY_OPTION_ALL = "all"
    HISTORY_OPTION_ALONE = "alone"

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, *args, **kwargs):
        self._check_configuration()
        correlation_ids = self._get_correlation_ids()
        page = self.paginate_queryset(correlation_ids)
        if page is not None:
            expedient_history = self.history_generator_model().generate(
                logs=LogEntry.objects.select_related("actor")
                .filter(cid__in=page)
                .order_by("-timestamp")
            )
            import ipdb

            ipdb.set_trace()
            return self.get_paginated_response(expedient_history)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def _get_correlation_ids(self):
        instance = self.get_object()
        filters = {}
        if self.history_option == self.HISTORY_OPTION_ALONE:
            content_type = ContentType.objects.get_for_model(instance)
            filters = {
                "object_id": instance.id,
                "content_type": content_type,
            }
        elif self.history_option == self.HISTORY_OPTION_ALL:
            filters = {f"additional_data__{self.history_generator_filter}": instance.id}

        return list(
            dict.fromkeys(
                LogEntry.objects.filter(**filters)
                .order_by("-timestamp")
                .values_list("cid", flat=True)
            )
        )

    def _check_configuration(self):
        if not hasattr(self, "history_generator_model"):
            raise NotImplementedError(
                "HistoryModelMixin requires a history_generator_model attribute."
            )
        if not hasattr(self, "history_option"):
            raise NotImplementedError(
                "HistoryModelMixin requires a history_option attribute."
            )
        if self.history_option not in (
            self.HISTORY_OPTION_ALL,
            self.HISTORY_OPTION_ALONE,
        ):
            raise ValueError(f"Invalid history_option value: {self.history_option}.")
        if self.history_option == self.HISTORY_OPTION_ALL and not hasattr(
            self, "history_generator_filter"
        ):
            raise NotImplementedError(
                "HistoryModelMixin requires a history_generator_filter attribute."
            )
