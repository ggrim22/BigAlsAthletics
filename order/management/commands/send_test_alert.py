"""Send a test alert so the email and SMS wiring can be verified without
placing a real order.

    python manage.py send_test_alert           # uses the configured backend
    python manage.py send_test_alert --real    # force real SMTP even in DEBUG

Locally DEBUG=True routes mail to the console backend, so --real is what
actually puts a text on your phone from a dev machine.
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.test.utils import override_settings

from core.notify import send_alert


class Command(BaseCommand):
    help = "Send a test operational alert to the configured email/SMS recipients."

    def add_arguments(self, parser):
        parser.add_argument(
            "--real",
            action="store_true",
            help="Force the SMTP backend even when DEBUG routes mail to the console.",
        )

    def handle(self, *args, **options):
        emails = settings.ALERT_EMAIL_RECIPIENTS
        sms = settings.ALERT_SMS_RECIPIENTS

        self.stdout.write(f"Email recipients: {emails or '(none configured)'}")
        self.stdout.write(f"SMS recipients:   {sms or '(none configured)'}")

        if not emails and not sms:
            self.stdout.write(self.style.ERROR(
                "Nothing configured. Set ALERT_EMAILS and/or ALERT_SMS."
            ))
            return

        summary = "Big Al's test alert - if you got this, alerts work."

        if options["real"]:
            if not settings.EMAIL_HOST_PASSWORD:
                self.stdout.write(self.style.ERROR(
                    "SENDGRID_API_KEY is empty; real send would fail."
                ))
                return
            self.stdout.write("Forcing SMTP backend...")
            with override_settings(
                EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
                EMAIL_HOST="smtp.sendgrid.net",
                EMAIL_PORT=587,
                EMAIL_USE_TLS=True,
                EMAIL_HOST_USER="apikey",
            ):
                delivered = send_alert(summary=summary, detail=summary, urgent=True)
        else:
            delivered = send_alert(summary=summary, detail=summary, urgent=True)

        if delivered:
            self.stdout.write(self.style.SUCCESS("Alert handed to the mail backend."))
            if not options["real"] and settings.DEBUG:
                self.stdout.write(
                    "DEBUG is on, so that went to the console above, not your phone. "
                    "Re-run with --real to send for real."
                )
        else:
            self.stdout.write(self.style.ERROR(
                "Delivery failed - check the logged exception above."
            ))
