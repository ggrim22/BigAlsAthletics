"""Out-of-band alerts for events that need a human to look now.

Delivery rides on the SendGrid SMTP connection that is already configured, so
there is no extra service or cost.  Texts work by addressing a carrier's
email-to-SMS gateway (e.g. 5551234567@vtext.com); see ALERT_SMS_RECIPIENTS.

Nothing in here is allowed to raise.  These calls sit inside the Stripe webhook
and the post-payment path, where an exception would turn a delivery problem into
a failed order.
"""

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

# Carrier gateways split anything longer into multiple texts.
SMS_MAX_LENGTH = 140


def _recipients(setting_name):
    return [address for address in getattr(settings, setting_name, []) if address]


def send_alert(summary, detail="", urgent=False):
    """Email the alert, and text it too when `urgent`.

    `summary` is the subject line and the body of the text, so keep it short and
    self-contained.  `detail` only goes to email.

    Returns True if at least one message was handed to the mail backend.
    """
    delivered = False

    email_to = _recipients("ALERT_EMAIL_RECIPIENTS")
    if email_to:
        delivered |= _send(
            subject=summary,
            body=detail or summary,
            recipients=email_to,
            channel="email",
        )

    if urgent:
        sms_to = _recipients("ALERT_SMS_RECIPIENTS")
        if sms_to:
            delivered |= _send(
                # Carrier gateways prepend the subject to the message body, so
                # it stays empty and the whole text lives in the body.
                subject="",
                body=summary[:SMS_MAX_LENGTH],
                recipients=sms_to,
                channel="sms",
            )

    if not delivered:
        logger.warning("Alert not delivered (no recipients configured): %s", summary)

    return delivered


def _send(subject, body, recipients, channel):
    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
        logger.info("Alert sent via %s to %d recipient(s)", channel, len(recipients))
        return True
    except Exception:
        # Never propagate: the caller is usually already handling a failure.
        logger.exception("Could not deliver %s alert", channel)
        return False
