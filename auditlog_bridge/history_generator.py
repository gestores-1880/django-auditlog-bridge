from collections import defaultdict, OrderedDict
from typing import Union

from auditlog.models import LogEntry

from .entities import HistoricAction
from .versioninstance_generator import VersionInstanceGenerator


class HistoryGenerator:
    version_instance_generator_by_model = {}
    version_instance_generator_default = VersionInstanceGenerator
    version_instance_ordering_by_model = {}
    main_model = None

    @classmethod
    def generate(
        cls,
        logs: list[LogEntry],
        context: dict = None,
    ):
        """
        Generate a list of serialized historic actions from log entries.

        Args:
            logs (list[LogEntry]): A list of log entries to process.
            context (dict): Additional context for generating historic actions.

        Returns:
            list: A list of serialized historic actions.
        """
        cls._check_configuration()
        historic_actions = cls._get_historic_actions(
            logs=logs,
            context=context,
        )
        historic_actions = cls._order_version_instances_in_actions(
            historic_actions=historic_actions
        )
        return [action.serialize() for action in historic_actions]

    @classmethod
    def _get_historic_actions(
        cls,
        logs: list[LogEntry] = None,
        context: dict = None,
    ) -> list[HistoricAction]:
        if context is None:
            context = {}
        logs_by_cid = OrderedDict()
        for log in logs:
            logs_by_cid.setdefault(log.cid, []).append(log)
        historic_actions = []
        for logs in logs_by_cid.values():
            historic_actions.append(
                cls._create_historic_action(
                    log_entries=logs,
                    context=context,
                )
            )
        return historic_actions

    @classmethod
    def _order_version_instances_in_actions(
        cls, historic_actions: list[HistoricAction]
    ) -> list[HistoricAction]:
        for action in historic_actions:
            action.instances = sorted(
                action.instances,
                key=lambda instance: cls.version_instance_ordering_by_model.get(
                    instance.content_type.model_class(), 999
                ),
            )
        return historic_actions

    @classmethod
    def _get_author_name(cls, log_entries: list[LogEntry]) -> str:
        return f"{log_entries[0].actor.first_name} {log_entries[0].actor.last_name}"

    @classmethod
    def _action_created(cls, log_entries: list[LogEntry]) -> bool:
        if cls.main_model is None:
            return log_entries[0].action == LogEntry.Action.CREATE
        action_created = False
        for log in log_entries:
            if log.content_type.model_class() == cls.main_model:
                action_created |= log.action == LogEntry.Action.CREATE
        return action_created

    @classmethod
    def _create_historic_action(
        cls, log_entries: list[LogEntry], context: dict
    ) -> HistoricAction | None:
        """
        Create a historic action from a list of log entries.
        Args:
            log_entries (list[LogEntry]): A list of log entries to process.
            context (dict): Additional context for generating historic actions.
        Returns:
            Union[HistoricAction, None]: The generated historic action or None if no log entries are provided.
        """
        if not log_entries:
            return None
        action = HistoricAction(
            author=cls._get_author_name(log_entries=log_entries),
            date_created=log_entries[-1].timestamp,
            created=cls._action_created(log_entries=log_entries),
        )
        for log in log_entries:
            version_instance_generator = cls.version_instance_generator_by_model.get(
                log.content_type.model_class(), cls.version_instance_generator_default
            )
            action.instances.append(
                version_instance_generator.generate(log=log, context=context)
            )
        action = cls._join_instances(action=action)
        return action

    @classmethod
    def _join_instances(cls, action: HistoricAction) -> HistoricAction:
        """
        Join instances with the same content type and instance ID in a single instance.

        Args:
            action (HistoricAction): The historic action to join instances.
        returns:
            HistoricAction: The historic action with joined instances.
        """
        instances_by_content_type = defaultdict(list)
        for instance in action.instances:
            instances_by_content_type[
                f"{instance.content_type.model}-{instance.instance_id}"
            ].append(instance)
        action.instances = []
        for instances in instances_by_content_type.values():
            joinables = [inst for inst in instances if inst.allow_join]
            non_joinables = [inst for inst in instances if not inst.allow_join]
            action.instances.extend(non_joinables)
            if len(joinables) == 0:
                continue
            joined_instance = joinables[0]
            for instance in joinables[1:]:
                field_names = {field.field_name for field in joined_instance.fields}
                for field in instance.fields:
                    if field.field_name in field_names:
                        updated_field = joined_instance.get_field(
                            field_name=field.field_name
                        )
                        updated_field.old_value = field.old_value
                    else:
                        joined_instance.fields.append(field)
            action.instances.append(joined_instance)
        return action

    @classmethod
    def _check_configuration(cls):
        version_instance_generators = cls.version_instance_generator_by_model.values()
        for version_instance_generator in version_instance_generators:
            if not issubclass(version_instance_generator, VersionInstanceGenerator):
                raise ValueError(
                    f"{version_instance_generator} must be subclasses of VersionInstanceGenerator."
                )

