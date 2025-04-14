from auditlog.cid import correlation_id
from auditlog.context import set_actor
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save

from celery import shared_task

from auditlog_bridge.queryset import SignalQuerySet


class CelerySignalQueryset(SignalQuerySet):
    """
    This class extends the SignalQuerySet to add the ability to send signals asynchronously using Celery.
    """
    def bulk_create_with_async_auditlog(
        self,
        objs,
        user_id,
        log_cid,
        batch_size=None,
        ignore_conflicts=False,
        update_conflicts=False,
        update_fields=None,
        unique_fields=None,
    ):
        """
        Bulk create instances and send post_save signal for each instance
        """
        created_instances = super().bulk_create(
            objs,
            batch_size=batch_size,
            ignore_conflicts=ignore_conflicts,
            update_conflicts=update_conflicts,
            update_fields=update_fields,
            unique_fields=unique_fields,
        )
        auditlog_registered_model_created.delay(
            ids=[instance.id for instance in created_instances],
            app_label=self.model._meta.app_label,
            model_name=self.model._meta.model_name,
            actor_id=user_id,
            log_cid=log_cid,
        )
        return created_instances


@shared_task
def auditlog_registered_model_created(
    ids: list, app_label: str, model_name: str, actor_id: int, log_cid: str
):
    correlation_id.set(log_cid)
    Model = apps.get_model(app_label=app_label, model_name=model_name)
    User = get_user_model()
    created_instances = Model.objects.filter(id__in=ids)
    with set_actor(actor=User.objects.get(id=actor_id)):
        for instance in created_instances:
            post_save.send(
                sender=instance.__class__, instance=instance, created=True, using=None
            )
