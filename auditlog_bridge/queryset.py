from django.db.models import QuerySet
from django.db.models.signals import post_save, pre_save


class SignalQuerySet(QuerySet):
    def bulk_create_with_signal(self, instances: list, **kwargs):
        """
        Bulk create instances and send post_save signal for each instance
        """
        created_instances = super().bulk_create(instances, **kwargs)
        for instance in created_instances:
            post_save.send(
                sender=instance.__class__, instance=instance, created=True, using=None
            )

    def bulk_update_with_signal(self, instances: list, fields: list, batch_size=None):
        """
        Bulk update instances and send post_save signal for each instance
        """
        for instance in instances:
            pre_save.send(
                sender=instance.__class__,
                instance=instance,
                using=None,
            )
        return super().bulk_update(instances, fields, batch_size)


    def update_with_signal(self, **kwargs) -> int:  # noqa: ANN401
        """
        Update queryset and manually trigger pre_save signals.
        """
        instances = list(self)

        for instance in instances:
            for key, value in kwargs.items():
                setattr(instance, key, value)

            pre_save.send(
                sender=instance.__class__,
                instance=instance,
                raw=False,
                using=self.db,
                update_fields=list(kwargs.keys()),
            )

        return super().update(**kwargs)
