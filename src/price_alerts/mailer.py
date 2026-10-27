"""Sending email. `Mailer` is the interface; `MailtrapMailer` sends via the Mailtrap Email API."""

from __future__ import annotations

from typing import Protocol

from .models import EmailMessage


class MailerError(Exception):
    """Sending one email failed."""


class Mailer(Protocol):
    def send(self, message: EmailMessage) -> None:
        """Send one email or raise MailerError."""
        ...


class MailtrapMailer:
    """Mailtrap Transactional stream (not the sandbox, not the bulk stream)."""

    def __init__(self, token: str, from_email: str, from_name: str) -> None:
        import mailtrap as mt

        self._mt = mt
        self._client = mt.MailtrapClient(token=token)
        self._sender = mt.Address(email=from_email, name=from_name)

    def send(self, message: EmailMessage) -> None:
        mt = self._mt
        mail = mt.Mail(
            sender=self._sender,
            to=[mt.Address(email=address) for address in message.to],
            subject=message.subject,
            text=message.text,
            html=message.html,
            category=message.category,
        )
        try:
            self._client.send(mail)
        except Exception as exc:  # the SDK raises APIError/AuthorizationError/requests errors
            # Only the exception's own message: it never contains the token.
            raise MailerError(f"{type(exc).__name__}: {_describe(exc)}") from None


def _describe(exc: Exception) -> str:
    errors = getattr(exc, "errors", None)
    if errors:
        return "; ".join(str(e) for e in errors) if isinstance(errors, list) else str(errors)
    return str(exc) or "unknown error"
