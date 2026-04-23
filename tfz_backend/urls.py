from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView
from main import views

router = DefaultRouter()
router.register(r"worker-profiles", views.WorkerProfileViewSet, basename="worker-profile")

urlpatterns = [
    # swagger
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/schema/swagger-ui/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),

    # аутентификация
    path("api/auth/login/", views.loginView, name="login"),
    path("api/auth/logout/", views.logoutView, name="logout"),
    path("api/auth/refresh/", views.CookieTokenRefreshView.as_view(), name="token-refresh"),
    path("api/profile/", views.current_user_view, name="current-user"),

    # регистрация
    path("api/auth/register/worker/", views.WorkerRegisterView.as_view(), name="register-worker"),
    path("api/auth/register/admin/", views.AdminRegisterView.as_view(), name="register-admin"),
    path("api/auth/register/superadmin/", views.SuperAdminRegisterView.as_view(), name="register-superadmin"),

    # профили сотрудников
    path("api/", include(router.urls)),

    # пациенты
    path("api/patients/", views.PatientListCreateView.as_view(), name="patient-list-create"),
    path("api/patients/<int:pk>/", views.PatientDetailView.as_view(), name="patient-detail"),

    # расчёты
    path("api/patients/<int:patient_id>/calculate/", views.calculate_view, name="calculate"),
    path("api/patients/<int:patient_id>/calculations/", views.PatientCalculationHistoryView.as_view(), name="patient-calculations"),
    path("api/calculations/<int:pk>/", views.CalculationDetailView.as_view(), name="calculation-detail"),
]
