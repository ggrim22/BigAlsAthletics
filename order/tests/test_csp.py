"""
Tests for the Content Security Policy.

The policy was previously configured with django-csp's pre-4.0 CSP_* module
settings, which 4.x ignores -- so no header was sent at all. These tests assert
a header is present AND that it permits every origin the templates load, so a
tightened policy cannot silently break the site.
"""
import glob
import re

import pytest
from django.test import Client
from django.urls import reverse


def policy():
    resp = Client().get(reverse("order:index"))
    header = resp.headers.get("Content-Security-Policy")
    assert header, "no Content-Security-Policy header was sent"
    directives = {}
    for part in header.split(";"):
        part = part.strip()
        if part:
            name, _, values = part.partition(" ")
            directives[name] = values.split()
    return directives


def external_origins():
    """Every https origin referenced by a src/href in the templates."""
    found = set()
    for path in glob.glob("templates/**/*.html", recursive=True) + glob.glob(
        "order/templates/**/*.html", recursive=True
    ):
        with open(path, encoding="utf-8") as handle:
            for match in re.finditer(r'(?:src|href)="(https://[^"]+)"', handle.read()):
                url = match.group(1)
                found.add("https://" + url.split("/")[2])
    return found


@pytest.mark.django_db
class TestPolicyIsSent:

    def test_header_present(self):
        assert policy()

    def test_locks_down_the_dangerous_defaults(self):
        p = policy()
        assert p["object-src"] == ["'none'"]
        assert p["frame-ancestors"] == ["'none'"]
        assert p["base-uri"] == ["'self'"]
        assert p["default-src"] == ["'self'"]

    def test_scripts_cannot_load_from_arbitrary_origins(self):
        """The main point: an injected <script src=evil.com> is still blocked."""
        sources = policy()["script-src"]
        assert "*" not in sources
        assert "https:" not in sources
        assert "http:" not in sources

    def test_form_submissions_are_restricted(self):
        assert "'self'" in policy()["form-action"]


@pytest.mark.django_db
class TestPolicyDoesNotBreakTheSite:
    """A policy that blocks real assets is worse than none - it breaks the page."""

    def test_every_template_origin_is_allowed_somewhere(self):
        p = policy()
        allowed = set()
        for values in p.values():
            allowed.update(v for v in values if v.startswith("http"))

        for origin in external_origins():
            # Links (<a href>) are navigation, not subresource loads.
            if origin == "https://account.venmo.com":
                continue
            assert origin in allowed, (
                f"{origin} is loaded by a template but not allowed by any directive"
            )

    def test_cdn_scripts_are_allowed(self):
        sources = policy()["script-src"]
        for origin in ("https://cdn.jsdelivr.net", "https://cdn.tailwindcss.com"):
            assert origin in sources, f"{origin} would be blocked, breaking the page"

    def test_cdn_styles_and_fonts_are_allowed(self):
        p = policy()
        assert "https://cdn.jsdelivr.net" in p["style-src"]
        assert "https://cdnjs.cloudflare.com" in p["font-src"]

    def test_inline_handlers_still_permitted(self):
        """8 onclick attributes exist; a nonce would make browsers ignore
        'unsafe-inline' and break all of them."""
        sources = policy()["script-src"]
        assert "'unsafe-inline'" in sources
        assert not any(s.startswith("'nonce-") for s in sources), (
            "a nonce in script-src makes browsers ignore 'unsafe-inline', "
            "which would break the inline onclick handlers"
        )

    def test_tailwind_runtime_styles_permitted(self):
        assert "'unsafe-inline'" in policy()["style-src"]


@pytest.mark.django_db
@pytest.mark.parametrize("view_name", [
    "order:index", "order:about", "order:contact", "order:payment-cancel",
])
def test_policy_present_on_every_public_page(client, view_name):
    resp = client.get(reverse(view_name))
    assert resp.headers.get("Content-Security-Policy")
