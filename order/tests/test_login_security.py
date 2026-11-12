"""
Tests for login brute-force throttling and the login page.

The admin credentials guard every customer record, and the login view had no
attempt limiting at all - passwords could be guessed at unlimited speed.
"""
import io

import pytest
from django.core.cache import cache
from django.urls import reverse

from core.views import LOGIN_ATTEMPT_LIMIT


@pytest.fixture(autouse=True)
def clear_rate_limit_cache():
    cache.clear()
    yield
    cache.clear()


def attempt(client, username="admin", password="wrong"):
    return client.post(reverse("login"), {"username": username, "password": password})


@pytest.mark.django_db
class TestLoginThrottling:

    def test_wrong_password_is_rejected_but_allowed(self, client, admin_user):
        response = attempt(client)
        assert response.status_code == 200  # re-renders the form
        assert not response.wsgi_request.user.is_authenticated

    def test_repeated_failures_get_blocked(self, client, admin_user):
        for _ in range(LOGIN_ATTEMPT_LIMIT):
            assert attempt(client).status_code == 200

        blocked = attempt(client)
        assert blocked.status_code == 429

    def test_blocked_response_still_renders_the_login_page(self, client, admin_user):
        for _ in range(LOGIN_ATTEMPT_LIMIT):
            attempt(client)

        blocked = attempt(client)
        content = blocked.content.decode()

        # Not a bare "Too Many Requests" body.
        assert "Sign in" in content
        assert 'name="username"' in content
        assert "Too many login attempts" in content

    def test_correct_password_still_works_below_the_limit(self, client, admin_user):
        for _ in range(LOGIN_ATTEMPT_LIMIT - 1):
            attempt(client)

        response = client.post(
            reverse("login"), {"username": "admin", "password": "adminpass123"}
        )
        assert response.status_code == 302
        assert response.wsgi_request.user.is_authenticated

    def test_successful_login_clears_the_budget(self, client, admin_user):
        """A good login must not leave the account one failure from lockout"""
        for _ in range(LOGIN_ATTEMPT_LIMIT - 1):
            attempt(client)

        client.post(reverse("login"), {"username": "admin", "password": "adminpass123"})
        client.logout()

        # Budget reset, so a fresh run of failures is allowed again.
        for _ in range(LOGIN_ATTEMPT_LIMIT):
            assert attempt(client).status_code == 200

    def test_get_requests_are_never_throttled(self, client, admin_user):
        """Being locked out of POST must not break loading the page"""
        for _ in range(LOGIN_ATTEMPT_LIMIT + 3):
            attempt(client)

        assert client.get(reverse("login")).status_code == 200

    def test_throttle_is_per_ip(self, client, admin_user):
        for _ in range(LOGIN_ATTEMPT_LIMIT):
            attempt(client)
        assert attempt(client).status_code == 429

        # A different source address has its own budget.
        other = client.post(
            reverse("login"),
            {"username": "admin", "password": "wrong"},
            REMOTE_ADDR="203.0.113.42",
        )
        assert other.status_code == 200

    def test_unknown_username_also_counts(self, client, admin_user):
        """Username enumeration attempts are throttled the same way"""
        for i in range(LOGIN_ATTEMPT_LIMIT):
            assert attempt(client, username=f"guess{i}").status_code == 200

        assert attempt(client, username="guess99").status_code == 429


@pytest.mark.django_db
class TestLoginPageTheme:

    def test_page_uses_the_charcoal_theme(self, client):
        content = client.get(reverse("login")).content.decode()

        assert "bg-zinc-950" in content
        assert "bg-light" not in content, "Bootstrap's light background should be gone"
        assert "btn-primary" not in content, "should use the site's light CTA"

    def test_subtitle_copy_is_gone(self, client):
        content = client.get(reverse("login")).content.decode()
        assert "Manage orders" not in content

    def test_card_is_not_cramped(self, client):
        """The form was too narrow at max-w-sm."""
        content = client.get(reverse("login")).content.decode()
        assert "max-w-md" in content
        assert "max-w-sm" not in content

    def test_form_labels_are_legible_on_dark(self, client):
        """Bootstrap's default label colour is near-black and would vanish"""
        content = client.get(reverse("login")).content.decode()
        assert ".login-form .form-label" in content

    def test_stylesheet_uses_the_cache_busting_tag(self, client):
        """static_v only appends ?v= under DEBUG, so assert on the template."""
        with io.open("templates/login.html", encoding="utf-8") as handle:
            source = handle.read()
        assert "{% load static_version %}" in source
        assert "{% static_v 'css/style.css' %}" in source

        # And the page still links a stylesheet at all.
        assert "css/style" in client.get(reverse("login")).content.decode()
