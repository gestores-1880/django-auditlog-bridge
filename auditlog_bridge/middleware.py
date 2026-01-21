import logging
import typing
import uuid

from auditlog.cid import correlation_id, get_cid
from auditlog.context import set_actor
from auditlog.middleware import AuditlogMiddleware
from django.conf import settings
from django.core import signing

if typing.TYPE_CHECKING:
    from django.core.handlers.wsgi import WSGIRequest
    from django.http import HttpResponse

logger = logging.getLogger(__name__)


class AuditlogBridgeMiddleware(AuditlogMiddleware):
    def __call__(self, request):
        remote_addr = self._get_remote_addr(request)
        user = self._get_actor(request)

        correlation_id.set(uuid.uuid4().hex)

        with set_actor(actor=user, remote_addr=remote_addr):
            return self.get_response(request)


class AuditlogBridgeCorrelationIdHeaderMiddleware(AuditlogBridgeMiddleware):
    def __init__(self, get_response: typing.Callable | None = None) -> None:
        super().__init__(get_response)
        self.signer = signing.TimestampSigner()

    def __call__(self, request: WSGIRequest) -> HttpResponse:
        """
        Check for correlation ID in the request headers.

        Set the correlation ID in the response headers and set the actor context.
        """
        remote_addr = self._get_remote_addr(request)
        user = self._get_actor(request)
        self._set_cid(request)
        with set_actor(actor=user, remote_addr=remote_addr):
            response = self.get_response(request)
            response[settings.AUDITLOG_CID_HEADER] = self.signer.sign(get_cid())
            return response

    def _set_cid(self, request: WSGIRequest) -> None:
        header = settings.AUDITLOG_CID_HEADER
        cid = request.headers.get(header) or request.META.get(header)

        if not cid:
            correlation_id.set(uuid.uuid4().hex)
            return

        try:
            raw_cid = self.signer.unsign(
                cid,
                max_age=settings.CORRELATION_ID_MAX_AGE_SECONDS,
            )
        except (signing.BadSignature, signing.SignatureExpired) as exc:
            logger.warning("Failed to validate cid: %s", exc)
            raw_cid = uuid.uuid4().hex

        correlation_id.set(raw_cid)
