import uuid

from auditlog.context import set_actor
from auditlog.middleware import AuditlogMiddleware
from auditlog.cid import correlation_id


class AuditlogBridgeMiddleware(AuditlogMiddleware):
    def __call__(self, request):
        remote_addr = self._get_remote_addr(request)
        user = self._get_actor(request)

        correlation_id.set(uuid.uuid4().hex)

        with set_actor(actor=user, remote_addr=remote_addr):
            return self.get_response(request)
