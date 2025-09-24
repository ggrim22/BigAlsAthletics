from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.messages.views import SuccessMessageMixin


class CustomLoginView(SuccessMessageMixin, LoginView):
    template_name = "login.html"
    redirect_authenticated_user = True
    success_message = "Successfully logged in"


class CustomLogoutView(LogoutView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.success(request, "Successfully logged out")
        return response
