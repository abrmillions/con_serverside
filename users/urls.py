from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RegisterView, MeView, LogoutView, UserViewSet, CheckEmailView, EmailVerificationRequestView, EmailVerificationConfirmView, FlexibleTokenObtainPairView, TokenLoginView, GoogleLoginView, GoogleCallbackView
from rest_framework_simplejwt.views import TokenRefreshView
from .views import PasswordResetRequestView, PasswordResetConfirmView

router = DefaultRouter()
router.register(r'manage', UserViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("register/", RegisterView.as_view(), name="register"),
    path("me/", MeView.as_view(), name="me"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("token/", TokenLoginView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password_reset"),
    path("password-reset/confirm/", PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("check-email/", CheckEmailView.as_view(), name="check_email"),
    path("email-verification/request/", EmailVerificationRequestView.as_view(), name="email_verification_request"),
    path("email-verification/confirm/", EmailVerificationConfirmView.as_view(), name="email_verification_confirm"),
    path("google/login/", GoogleLoginView.as_view(), name="google_login"),
    path("google/callback/", GoogleCallbackView.as_view(), name="google_callback"),
]
