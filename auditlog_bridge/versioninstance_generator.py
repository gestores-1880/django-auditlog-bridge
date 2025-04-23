from auditlog.models import LogEntry
from django.core.validators import EMPTY_VALUES

from .entities import (
    VersionField,
    VersionInstance,
)


class VersionInstanceGenerator:
    excluded_fields = ("id",)
    soft_deleted_field = "deleted_at"

    @classmethod
    def _clean_none_values(cls, value: str):
        if value == "None":
            return None
        return value

    @classmethod
    def _get_version_instance(cls, log: LogEntry) -> VersionInstance:
        if cls._is_m2m(log):
            return cls._build_m2m_instance(log=log)
        return cls._build_standard_instance(log=log)

    @classmethod
    def _is_m2m(cls, log: LogEntry) -> bool:
        if len(log.changes) != 1:
            return False
        first = next(iter(log.changes.values()))
        return isinstance(first, dict) and first.get("type") == "m2m"

    @classmethod
    def _build_m2m_instance(cls, log: LogEntry) -> VersionInstance:
        fields = []
        added = False

        for raw_name, data in log.changes.items():
            name = raw_name.lower().replace(" ", "_")
            if name in cls.excluded_fields:
                continue

            objs = data["objects"]
            if data["operation"] == "add":
                added = True
                old, new = None, objs
            else:  # delete
                old, new = objs, None

            fields.append(VersionField(
                field_name=name,
                old_value=old,
                new_value=new,
            ))

        action = VersionInstance.CREATE if added else VersionInstance.DELETE
        return VersionInstance(
            content_type=log.content_type,
            instance_id=log.object_id,
            action=action,
            fields=fields,
            allow_join=False,
        )

    @classmethod
    def _build_standard_instance(cls, log: LogEntry) -> VersionInstance:
        fields = []

        for display_name, (old_val, new_val) in log.changes_display_dict.items():
            name = display_name.lower().replace(" ", "_")
            if name in cls.excluded_fields:
                continue

            fields.append(VersionField(
                field_name=name,
                old_value=cls._clean_none_values(old_val),
                new_value=cls._clean_none_values(new_val),
            ))

        return VersionInstance(
            content_type=log.content_type,
            instance_id=log.object_id,
            action=log.get_action_display(),
            fields=fields,
        )

    @classmethod
    def _set_deleted_instance(cls, instance: VersionInstance) -> VersionInstance:
        for field in instance.fields:
            if field.field_name != cls.soft_deleted_field:
                continue
            if field.new_value is not None:
                instance.action = VersionInstance.DELETE
                break
        return instance

    @classmethod
    def _remove_empty_fields_diff(cls, instance: VersionInstance) -> VersionInstance:
        fields = []
        for field in instance.fields:
            if (
                field.old_value not in EMPTY_VALUES
                or field.new_value not in EMPTY_VALUES
            ):
                fields.append(field)
        instance.fields = fields
        return instance

    @classmethod
    def _custom_generator(
        cls, log: LogEntry, instance: VersionInstance, context: dict
    ) -> VersionInstance:
        return instance

    @classmethod
    def generate(cls, log: LogEntry, context: dict) -> VersionInstance:
        version_instance = cls._get_version_instance(log=log)
        version_instance = cls._remove_empty_fields_diff(instance=version_instance)
        version_instance = cls._set_deleted_instance(instance=version_instance)
        return cls._custom_generator(
            log=log, instance=version_instance, context=context
        )
