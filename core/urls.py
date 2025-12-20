from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from accounts import views as accounts_views
urlpatterns = [
    path("", views.home, name="home"),

    path("login/", auth_views.LoginView.as_view(template_name="auth/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("signup/", accounts_views.register, name="signup"),
    path("manage-sellers/", views.manage_sellers, name="manage_sellers"),
]
