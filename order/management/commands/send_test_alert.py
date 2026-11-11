"""Send a test alert so the email and SMS wiring can be verified without
placing a real order.

    python manage.py send_test_alert           # uses the configured backend
    python manage.py send_test_alert --real    # force real SMTP even in DEBUG

Locally DEBUG=True routes mail to the console backend, so --real is what
actually puts a text on your phone from a dev machine.
"""

from decouple import config
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
        parser.add_argument(
            "--sms",
            default=None,
            help=(
                "Comma-separated gateway addresses to text instead of ALERT_SMS. "
                "Use this to find out which carrier a number is on by trying "
                "several gateways at once."
            ),
        )
        parser.add_argument(
            "--number",
            default=None,
            help=(
                "A 10-digit number to try against every known carrier gateway. "
                "Whichever one arrives is the carrier."
            ),
        )

    # Gateways to probe with --number.
    CARRIER_GATEWAYS = {
        "Verizon (SMS)": "vtext.com",
        "Verizon (MMS)": "vzwpix.com",
        "AT&T (SMS)": "txt.att.net",
        "AT&T (MMS)": "mms.att.net",
        "T-Mobile": "tmomail.net",
        "Google Fi": "msg.fi.google.com",
    }

    def handle(self, *args, **options):
        emails = settings.ALERT_EMAIL_RECIPIENTS
        sms = settings.ALERT_SMS_RECIPIENTS

        number = (options.get("number") or "").strip()
        if number:
            digits = "".join(c for c in number if c.isdigit())[-10:]
            sms = [f"{digits}@{domain}" for domain in self.CARRIER_GATEWAYS.values()]
            self.stdout.write("Probing every carrier gateway:")
            for label, domain in self.CARRIER_GATEWAYS.items():
                self.stdout.write(f"  {label:<16} {digits}@{domain}")
            self.stdout.write(self.style.WARNING(
                "Only the matching carrier will deliver; the rest bounce harmlessly."
            ))
        elif options.get("sms"):
            sms = [a.strip() for a in options["sms"].split(",") if a.strip()]

        self.stdout.write(f"Email recipients: {emails or '(none configured)'}")
        self.stdout.write(f"SMS recipients:   {sms or '(none configured)'}")

        if not emails and not sms:
            self.stdout.write(self.style.ERROR(
                "Nothing configured. Set ALERT_EMAILS and/or ALERT_SMS."
            ))
            return

        summary = "Big Al's test alert - if you got this, alerts work."

        overrides = {"ALERT_SMS_RECIPIENTS": sms}

        if options["real"]:
            if not settings.EMAIL_HOST_PASSWORD:
                self.stdout.write(self.style.ERROR(
                    "SENDGRID_API_KEY is empty; real send would fail."
                ))
                return
            host = config("EMAIL_HOST", default="smtp.sendgrid.net")
            self.stdout.write(f"Forcing SMTP backend via {host}...")
            self.stdout.write(f"From: {settings.DEFAULT_FROM_EMAIL}")
            with override_settings(
                EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend",
                EMAIL_HOST=host,
                EMAIL_PORT=config("EMAIL_PORT", default=587, cast=int),
                EMAIL_USE_TLS=True,
                EMAIL_HOST_USER=config("EMAIL_HOST_USER", default="apikey"),
                **overrides,
            ):
                delivered = send_alert(summary=summary, detail=summary, urgent=True)
        else:
            with override_settings(**overrides):
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
