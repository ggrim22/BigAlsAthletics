"""
Tests for operational alerts.

The alert helper runs inside the Stripe webhook and the post-payment path, so
the behaviour that matters most is that it never raises: a mail problem must not
turn into a failed order.
"""
import pytest
from unittest.mock import patch

from django.core import mail
from django.test import override_settings
from django.urls import reverse

from core.notify import SMS_MAX_LENGTH, send_alert


@pytest.mark.django_db
class TestSendAlert:

    @override_settings(ALERT_EMAIL_RECIPIENTS=["ops@test.com"], ALERT_SMS_RECIPIENTS=[])
    def test_emails_the_alert(self):
        assert send_alert("Something happened", "the details") is True

        assert len(mail.outbox) == 1
        assert mail.outbox[0].subject == "Something happened"
        assert mail.outbox[0].body == "the details"
        assert mail.outbox[0].to == ["ops@test.com"]

    @override_settings(ALERT_EMAIL_RECIPIENTS=["ops@test.com"], ALERT_SMS_RECIPIENTS=[])
    def test_non_urgent_alert_sends_no_text(self):
        send_alert("Routine thing", "details", urgent=False)

        assert len(mail.outbox) == 1  # email only

    @override_settings(
        ALERT_EMAIL_RECIPIENTS=["ops@test.com"],
        ALERT_SMS_RECIPIENTS=["5551234567@vtext.com"],
    )
    def test_urgent_alert_also_texts(self):
        send_alert("Order failed", "long detail body", urgent=True)

        assert len(mail.outbox) == 2
        sms = [m for m in mail.outbox if m.to == ["5551234567@vtext.com"]][0]
        # Carrier gateways prepend the subject, so it has to stay empty.
        assert sms.subject == ""
        assert sms.body == "Order failed"

    @override_settings(
        ALERT_EMAIL_RECIPIENTS=[],
        ALERT_SMS_RECIPIENTS=["5551234567@vtext.com"],
    )
    def test_text_is_truncated_to_one_message(self):
        send_alert("x" * 500, urgent=True)

        assert len(mail.outbox[0].body) == SMS_MAX_LENGTH

    @override_settings(ALERT_EMAIL_RECIPIENTS=[], ALERT_SMS_RECIPIENTS=[])
    def test_no_recipients_is_not_an_error(self):
        """An unconfigured install must not crash the caller"""
        assert send_alert("Nobody is listening", urgent=True) is False
        assert len(mail.outbox) == 0

    @override_settings(ALERT_EMAIL_RECIPIENTS=["ops@test.com"], ALERT_SMS_RECIPIENTS=[])
    def test_blank_recipients_are_skipped(self):
        with override_settings(ALERT_EMAIL_RECIPIENTS=["", None, "ops@test.com"]):
            send_alert("Hi")
        assert mail.outbox[0].to == ["ops@test.com"]

    @override_settings(ALERT_EMAIL_RECIPIENTS=["ops@test.com"], ALERT_SMS_RECIPIENTS=[])
    @patch("core.notify.send_mail", side_effect=Exception("SMTP is down"))
    def test_delivery_failure_is_swallowed(self, mock_send):
        """A mail outage must never propagate into the order path"""
        assert send_alert("Order failed", urgent=True) is False

    @override_settings(
        ALERT_EMAIL_RECIPIENTS=["ops@test.com"],
        ALERT_SMS_RECIPIENTS=["5551234567@vtext.com"],
    )
    def test_email_still_sent_when_sms_fails(self):
        def fail_on_sms(subject, message, from_email, recipient_list, **kwargs):
            if recipient_list == ["5551234567@vtext.com"]:
                raise Exception("gateway rejected")
            return 1

        with patch("core.notify.send_mail", side_effect=fail_on_sms):
            assert send_alert("Order failed", urgent=True) is True


@pytest.mark.django_db
class TestAlertsOnCriticalPaths:
    """The paths where the customer has already been charged"""

    @override_settings(
        ALERT_EMAIL_RECIPIENTS=["ops@test.com"],
        ALERT_SMS_RECIPIENTS=["5551234567@vtext.com"],
    )
    @patch("order.views.create_order_from_checkout_session", side_effect=Exception("boom"))
    def test_payment_success_failure_raises_an_alert(self, mock_record, client):
        response = client.get(reverse("order:payment-success"), {"session_id": "cs_broken"})

        assert response.status_code == 200
        alerts = [m for m in mail.outbox if "NOT RECORDED" in (m.subject or m.body)]
        assert alerts, "expected an alert when a paid order could not be saved"
        assert any(m.to == ["5551234567@vtext.com"] for m in mail.outbox)

    @override_settings(ALERT_EMAIL_RECIPIENTS=[], ALERT_SMS_RECIPIENTS=[])
    @patch("order.views.create_order_from_checkout_session", side_effect=Exception("boom"))
    def test_payment_success_still_renders_without_alert_config(self, mock_record, client):
        """Unconfigured alerts must not break the customer's page"""
        response = client.get(reverse("order:payment-success"), {"session_id": "cs_broken"})

        assert response.status_code == 200

    @override_settings(ALERT_EMAIL_RECIPIENTS=["ops@test.com"], ALERT_SMS_RECIPIENTS=[])
    @patch("order.views.create_order_from_checkout_session", side_effect=Exception("boom"))
    @patch("core.notify.send_mail", side_effect=Exception("SMTP down"))
    def test_payment_success_survives_alert_delivery_failure(
        self, mock_mail, mock_record, client
    ):
        """Mail being down must not turn into a 500 for the customer"""
        response = client.get(reverse("order:payment-success"), {"session_id": "cs_broken"})

        assert response.status_code == 200


@pytest.mark.django_db
class TestWebhookSignatureDiagnostics:
    """An unsigned scan is noise; a signed request that fails is a real fault."""

    def _post(self, client, headers=None):
        return client.post(
            reverse("stripe-webhook"),
            data=b"{}",
            content_type="application/json",
            **(headers or {}),
        )

    def test_unsigned_post_is_a_warning_not_an_error(self, client, caplog):
        """Bots scanning the URL must not raise a Sentry issue"""
        import logging
        with caplog.at_level(logging.WARNING, logger="order.webhooks"):
            response = self._post(client)

        assert response.status_code == 400
        records = [r for r in caplog.records if r.name == "order.webhooks"]
        assert records, "expected a log record"
        assert records[0].levelno == logging.WARNING
        assert "no Stripe-Signature header" in records[0].getMessage()

    def test_bad_signature_is_an_error_with_context(self, client, caplog):
        """A signed-but-invalid request means the secret is wrong - alert on it"""
        import logging
        with caplog.at_level(logging.ERROR, logger="order.webhooks"):
            response = self._post(client, {"HTTP_STRIPE_SIGNATURE": "t=1,v1=deadbeef"})

        assert response.status_code == 400
        records = [r for r in caplog.records if r.name == "order.webhooks"]
        assert records, "expected a log record"
        assert records[0].levelno == logging.ERROR
        message = records[0].getMessage()
        assert "signature verification failed" in message
        # The message must say enough to act on without opening the code.
        assert "STRIPE_WEBHOOK_SECRET" in message
