from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import redirect, render

from core.mail import send_email

from .forms import EmailLoginForm, SignUpForm


def signup(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            send_email(
                subject=f"Welcome to {settings.SITE_NAME}",
                template="emails/welcome.txt",
                context={"user": user, "site_url": settings.SITE_URL, "site_name": settings.SITE_NAME},
                to=user.email,
            )
            return redirect(settings.LOGIN_REDIRECT_URL)
    else:
        form = SignUpForm()
    return render(request, "accounts/signup.html", {"form": form})


class SignInView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailLoginForm
    redirect_authenticated_user = True


class SignOutView(LogoutView):
    next_page = settings.LOGOUT_REDIRECT_URL
