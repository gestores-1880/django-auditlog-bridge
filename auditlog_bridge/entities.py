from __future__ import annotations

import datetime
from dataclasses import dataclass, field

from auditlog.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType


UserModel = get_user_model()


@dataclass
class VersionField:
    field_name: str
    old_value: str | int | None
    new_value: str | int | None

    def serialize(self):
        return {
            "field": self.field_name,
            "from": self.old_value,
            "to": self.new_value,
        }


@dataclass
class VersionInstance:
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ACCESS = "access"

    ACTION_CHOICES = (
        (CREATE, "Create"),
        (UPDATE, "Update"),
        (DELETE, "Delete"),
        (ACCESS, "Access"),
    )

    content_type: ContentType
    action: ACTION_CHOICES
    instance_id: int | None = None
    fields: list[VersionField] = field(default_factory=list)
    representation: str | None = None

    def serialize(self):
        return {
            "fields": [_field.serialize() for _field in self.fields],
            "added": self.action == self.CREATE,
            "deleted": self.action == self.DELETE,
            "model": self.content_type.model,
            "representation": self.representation,
        }

    def get_field(self, field_name: str) -> VersionField | None:
        for field in self.fields:
            if field.field_name == field_name:
                return field
        return None


@dataclass
class HistoricAction:
    author: str
    date_created: datetime.datetime
    created: bool = False
    instances: list[VersionInstance] = field(default_factory=list)

    def serialize(self):
        return {
            "author": self.author,
            "date_created": self.date_created,
            "instances": [instance.serialize() for instance in self.instances],
            "created": self.created,
        }

    @classmethod
    def create(
        cls,
        log_entries: list[LogEntry],
        version_instance_generator_by_model: dict,
        version_instance_generator_default: object,
        **kwargs,
    ) -> HistoricAction | None:
        if not log_entries:
            return None
        author = cls._get_author(log_entries)
        action = cls(author=author, date_created=log_entries[0].timestamp)
        for log in log_entries:
            version_instance_generator = version_instance_generator_by_model.get(
                log.content_type.model_class(), version_instance_generator_default
            )
            action.instances.append(
                version_instance_generator.generate(log=log, **kwargs)
            )
            if log.action == LogEntry.Action.CREATE:
                action.created = True
        return action
