from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.messages.views import SuccessMessageMixin
from django.core.cache import cache

from core.decorators import get_client_ip

# Brute-force budget per client IP. Only failed attempts count, so a legitimate
# login never eats into it.
LOGIN_ATTEMPT_LIMIT = 5
LOGIN_ATTEMPT_WINDOW = 300  # seconds


class CustomLoginView(SuccessMessageMixin, LoginView):
    template_name = "login.html"
    redirect_authenticated_user = True
    success_message = "Successfully logged in"

    def post(self, request, *args, **kwargs):
        """Throttle repeated failed logins from the same IP.

        Implemented here rather than with the @rate_limit decorator so a blocked
        attempt still renders the real login page with a message, instead of a
        bare "Too Many Requests" body.
        """
        cache_key = self._cache_key(request)
        attempts = cache.get(cache_key, 0)

        if attempts >= LOGIN_ATTEMPT_LIMIT:
            messages.error(
                request,
                "Too many login attempts. Please wait a few minutes and try again.",
            )
            return self.render_to_response(
                self.get_context_data(form=self.get_form()), status=429
            )

        response = super().post(request, *args, **kwargs)

        if request.user.is_authenticated:
            # Clean slate once they are in.
            cache.delete(cache_key)
        else:
            self._record_failure(cache_key)

        return response

    @staticmethod
    def _cache_key(request):
        # Same naming scheme as the rate_limit decorator.
        return f"rate_limit_login_{get_client_ip(request)}"

    @staticmethod
    def _record_failure(cache_key):
        try:
            cache.incr(cache_key)
        except ValueError:
            # Key absent or expired between the read and the increment.
            cache.set(cache_key, 1, LOGIN_ATTEMPT_WINDOW)


class CustomLogoutView(LogoutView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.success(request, "Successfully logged out")
        return response
