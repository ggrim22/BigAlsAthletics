"""Inspect and clear SendGrid suppression entries for an address.

SendGrid remembers addresses that bounced and silently drops later mail to them
("event": "dropped"), even after the underlying problem is fixed.  Carrier SMS
gateways land on these lists easily, so an address can stay dead long after the
cause is gone.

    python manage.py sendgrid_suppressions 7657448452@vtext.com
    python manage.py sendgrid_suppressions 7657448452@vtext.com --delete
    python manage.py sendgrid_suppressions --number 7657448452 --delete
"""

import requests
from decouple import config
from django.core.management.base import BaseCommand

API_ROOT = "https://api.sendgrid.com/v3/suppression"

# The lists SendGrid drops against, in the order worth checking.
LISTS = ("bounces", "blocks", "invalid_emails", "spam_reports")

CARRIER_DOMAINS = (
    "vtext.com", "vzwpix.com", "txt.att.net", "mms.att.net",
    "tmomail.net", "msg.fi.google.com",
)


class Command(BaseCommand):
    help = "Show (and optionally remove) SendGrid suppressions blocking an address."

    def add_arguments(self, parser):
        parser.add_argument("email", nargs="?", help="Address to check.")
        parser.add_argument(
            "--number",
            help="10-digit number: checks that number at every carrier gateway.",
        )
        parser.add_argument(
            "--delete",
            action="store_true",
            help="Remove the address from any list it appears on.",
        )

    def handle(self, *args, **options):
        api_key = config("SENDGRID_API_KEY", default="")
        if not api_key:
            self.stdout.write(self.style.ERROR(
                "SENDGRID_API_KEY is not set in this environment."
            ))
            return

        addresses = []
        if options.get("number"):
            digits = "".join(c for c in options["number"] if c.isdigit())[-10:]
            addresses = [f"{digits}@{d}" for d in CARRIER_DOMAINS]
        elif options.get("email"):
            addresses = [options["email"]]
        else:
            self.stdout.write(self.style.ERROR("Give an email address or --number."))
            return

        headers = {"Authorization": f"Bearer {api_key}"}
        found_any = False

        for address in addresses:
            for list_name in LISTS:
                url = f"{API_ROOT}/{list_name}/{address}"
                try:
                    response = requests.get(url, headers=headers, timeout=15)
                except requests.RequestException as exc:
                    self.stdout.write(self.style.ERROR(f"  {address}: request failed ({exc})"))
                    continue

                if response.status_code == 404 or not response.json():
                    continue

                found_any = True
                entries = response.json()
                reason = ""
                if isinstance(entries, list) and entries:
                    reason = entries[0].get("reason", "") or entries[0].get("status", "")
                self.stdout.write(self.style.WARNING(
                    f"  SUPPRESSED  {address}  [{list_name}] {reason[:90]}"
                ))

                if options["delete"]:
                    deleted = requests.delete(url, headers=headers, timeout=15)
                    if deleted.status_code in (200, 204):
                        self.stdout.write(self.style.SUCCESS(
                            f"    removed from {list_name}"
                        ))
                    else:
                        self.stdout.write(self.style.ERROR(
                            f"    could not remove ({deleted.status_code}): {deleted.text[:120]}"
                        ))

        if not found_any:
            self.stdout.write(self.style.SUCCESS(
                "No suppressions found - nothing is blocking these addresses."
            ))
        elif not options["delete"]:
            self.stdout.write("\nRe-run with --delete to clear these.")
