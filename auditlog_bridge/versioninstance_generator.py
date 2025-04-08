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
    def _get_version_instance(cls, log: LogEntry):
        fields = []
        m2m_fields = (
                len(log.changes) == 1
                and isinstance(list(log.changes.values())[0], dict)
                and list(log.changes.values())[0].get("type") == "m2m"
        )
        if m2m_fields:
            added = False
            for field_name, value in log.changes.items():
                field_name = field_name.lower().replace(" ", "_")
                if field_name in cls.excluded_fields:
                    continue
                if value["operation"] == "add":
                    added = True
                    fields.append(
                        VersionField(
                            field_name=field_name,
                            old_value=None,
                            new_value=value["objects"],
                        )
                    )
                elif value["operation"] == "delete":
                    fields.append(
                        VersionField(
                            field_name=field_name,
                            old_value=value["objects"],
                            new_value=None,
                        )
                    )
            return VersionInstance(
                content_type=log.content_type,
                instance_id=log.object_id,
                action=VersionInstance.CREATE if added else VersionInstance.DELETE,
                fields=fields,
            )
        else:
            for field_name, values in log.changes_display_dict.items():
                normalized_field_name = field_name.lower().replace(" ", "_")
                if normalized_field_name in cls.excluded_fields:
                    continue
                fields.append(
                    VersionField(
                        field_name=normalized_field_name,
                        old_value=cls._clean_none_values(values[0]),
                        new_value=cls._clean_none_values(values[1]),
                    )
                )
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
