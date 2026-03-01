from django.views.decorators.csrf import csrf_exempt
from rest_framework import viewsets, permissions, response, decorators, status, generics
from rest_framework.views import APIView
from rest_framework_simplejwt import tokens, views as jwt_views, serializers as jwt_serializers, exceptions as jwt_exceptions
from django.contrib.auth import authenticate
from django.middleware import csrf
from django.core.cache import cache
from rest_framework import exceptions as rest_exceptions
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiTypes

from .models import *
from .permissions import IsSuperAdmin, IsAdminOrSuperAdmin
from .serializers import *
from .services.calculator import run_calculation

Account = get_user_model()


def get_user_tokens(user):
    refresh = tokens.RefreshToken.for_user(user)
    return {"refresh_token": str(refresh), "access_token": str(refresh.access_token)}


def _get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


@extend_schema(tags=["Auth"], request=LoginSerializer, responses={200: TokenResponseSerializer})
@decorators.api_view(["POST"])
@decorators.permission_classes([])
def loginView(request):
    ip = _get_client_ip(request)
    cache_key = f"login_attempts_{ip}"
    attempts = cache.get(cache_key, 0)
    if attempts >= 5:
        return response.Response(
            {"detail": "Слишком много попыток входа. Подождите минуту."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    email = request.data.get("email")
    password = request.data.get("password")
    if not email or not password:
        raise rest_exceptions.ValidationError({"detail": "Email and password required"})

    user = authenticate(email=email, password=password)
    if not user:
        cache.set(cache_key, attempts + 1, timeout=60)
        raise rest_exceptions.AuthenticationFailed("Email or password is incorrect!")
    if not user.is_active:
        raise rest_exceptions.AuthenticationFailed("Account is disabled.")

    cache.delete(cache_key)

    tokens_dict = get_user_tokens(user)
    res = response.Response(tokens_dict)

    res.set_cookie(
        key=settings.SIMPLE_JWT['AUTH_COOKIE'],
        value=tokens_dict["access_token"],
        expires=settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'],
        secure=settings.SIMPLE_JWT.get('AUTH_COOKIE_SECURE', False),
        httponly=settings.SIMPLE_JWT.get('AUTH_COOKIE_HTTP_ONLY', True),
        samesite=settings.SIMPLE_JWT.get('AUTH_COOKIE_SAMESITE', 'Lax')
    )
    res.set_cookie(
        key=settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'],
        value=tokens_dict["refresh_token"],
        expires=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'],
        secure=settings.SIMPLE_JWT.get('AUTH_COOKIE_SECURE', False),
        httponly=settings.SIMPLE_JWT.get('AUTH_COOKIE_HTTP_ONLY', True),
        samesite=settings.SIMPLE_JWT.get('AUTH_COOKIE_SAMESITE', 'Lax')
    )
    res.set_cookie(
        key="user_role",
        value="admin" if user.is_staff else "worker",
        max_age=settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'],
        secure=settings.SIMPLE_JWT.get('AUTH_COOKIE_SECURE', False),
        httponly=True,
        samesite='Lax'
    )
    res["X-CSRFToken"] = csrf.get_token(request)
    return res


@extend_schema(tags=["Auth"], responses={200: {"type": "object", "properties": {"detail": {"type": "string"}}}})
@csrf_exempt
@decorators.api_view(["POST"])
@decorators.permission_classes([permissions.AllowAny])
def logoutView(request):
    try:
        refresh_token = request.COOKIES.get(settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'])
        if refresh_token:
            token = tokens.RefreshToken(refresh_token)
            token.blacklist()
    except Exception:
        pass

    res = response.Response({"detail": "Logged out successfully"}, status=status.HTTP_200_OK)

    for key in [settings.SIMPLE_JWT['AUTH_COOKIE'], settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'], "user_role", "is_staff"]:
        res.delete_cookie(key=key, path=settings.SIMPLE_JWT.get('AUTH_COOKIE_PATH', '/'),
                          samesite=settings.SIMPLE_JWT.get('AUTH_COOKIE_SAMESITE', 'Lax'))

    for key in [settings.CSRF_COOKIE_NAME, "X-CSRFToken"]:
        res.delete_cookie(key=key, path='/', samesite=settings.CSRF_COOKIE_SAMESITE)

    return res


class CookieTokenRefreshSerializer(jwt_serializers.TokenRefreshSerializer):
    refresh = None

    def validate(self, attrs):
        attrs['refresh'] = self.context['request'].COOKIES.get(settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'])
        if attrs['refresh']:
            return super().validate(attrs)
        raise jwt_exceptions.InvalidToken("No valid refresh token in cookie")


@extend_schema(tags=["Auth"])
class CookieTokenRefreshView(jwt_views.TokenRefreshView):
    serializer_class = CookieTokenRefreshSerializer

    def finalize_response(self, request, response_obj, *args, **kwargs):
        if response_obj.data.get("access"):
            response_obj.set_cookie(
                key=settings.SIMPLE_JWT['AUTH_COOKIE'], value=response_obj.data['access'],
                expires=settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'],
                secure=settings.SIMPLE_JWT.get('AUTH_COOKIE_SECURE', False),
                httponly=True, samesite=settings.SIMPLE_JWT.get('AUTH_COOKIE_SAMESITE', 'Lax')
            )
            del response_obj.data["access"]

        if response_obj.data.get("refresh"):
            response_obj.set_cookie(
                key=settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'], value=response_obj.data['refresh'],
                expires=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'],
                secure=settings.SIMPLE_JWT.get('AUTH_COOKIE_SECURE', False),
                httponly=True, samesite=settings.SIMPLE_JWT.get('AUTH_COOKIE_SAMESITE', 'Lax')
            )
            del response_obj.data["refresh"]

        response_obj["X-CSRFToken"] = request.COOKIES.get("csrftoken")
        return super().finalize_response(request, response_obj, *args, **kwargs)


@extend_schema(tags=["Auth"], responses={200: AccountSerializer})
@decorators.api_view(["GET"])
@decorators.permission_classes([permissions.IsAuthenticated])
def current_user_view(request):
    serializer = AccountSerializer(request.user)
    return response.Response(serializer.data)


@extend_schema(tags=["Auth"], request=WorkerRegistrationSerializer, responses={201: AccountSerializer})
class WorkerRegisterView(generics.CreateAPIView):
    serializer_class = WorkerRegistrationSerializer
    permission_classes = [permissions.AllowAny]


@extend_schema(tags=["Auth"], request=AdminRegistrationSerializer, responses={201: AccountSerializer})
class AdminRegisterView(generics.CreateAPIView):
    serializer_class = AdminRegistrationSerializer
    permission_classes = [IsSuperAdmin]


@extend_schema(tags=["Auth"], request=SuperAdminRegistrationSerializer, responses={201: AccountSerializer})
class SuperAdminRegisterView(generics.CreateAPIView):
    serializer_class = SuperAdminRegistrationSerializer
    permission_classes = [IsSuperAdmin]


@extend_schema(tags=["Workers"])
class WorkerProfileViewSet(viewsets.ModelViewSet):
    queryset = WorkerProfile.objects.select_related("user").all()
    serializer_class = WorkerProfileSerializer
    permission_classes = [IsAdminOrSuperAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser or user.is_staff:
            return super().get_queryset()
        return WorkerProfile.objects.filter(user=user)


@extend_schema(tags=["Patients"])
class PatientListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(responses={200: PatientSerializer(many=True)})
    def get(self, request):
        patients = Patient.objects.all().order_by("-created_at")
        serializer = PatientSerializer(patients, many=True)
        return response.Response(serializer.data)

    @extend_schema(request=PatientSerializer, responses={201: PatientSerializer})
    def post(self, request):
        serializer = PatientSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return response.Response(serializer.data, status=status.HTTP_201_CREATED)
        return response.Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(tags=["Patients"])
class PatientDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, pk):
        try:
            return Patient.objects.get(pk=pk)
        except Patient.DoesNotExist:
            return None

    @extend_schema(responses={200: PatientSerializer})
    def get(self, request, pk):
        patient = self.get_object(pk)
        if not patient:
            return response.Response({"detail": "Пациент не найден."}, status=status.HTTP_404_NOT_FOUND)
        return response.Response(PatientSerializer(patient).data)

    @extend_schema(request=PatientSerializer, responses={200: PatientSerializer})
    def patch(self, request, pk):
        patient = self.get_object(pk)
        if not patient:
            return response.Response({"detail": "Пациент не найден."}, status=status.HTTP_404_NOT_FOUND)
        serializer = PatientSerializer(patient, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return response.Response(serializer.data)
        return response.Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @extend_schema(responses={204: None})
    def delete(self, request, pk):
        patient = self.get_object(pk)
        if not patient:
            return response.Response({"detail": "Пациент не найден."}, status=status.HTTP_404_NOT_FOUND)
        patient.delete()
        return response.Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema(
    tags=["Calculator"],
    request=CalculateRequestSerializer,
    responses={201: CalculationHistorySerializer},
)
@decorators.api_view(["POST"])
@decorators.permission_classes([permissions.IsAuthenticated])
def calculate_view(request, patient_id):
    try:
        patient = Patient.objects.get(pk=patient_id)
    except Patient.DoesNotExist:
        return response.Response({"detail": "Пациент не найден."}, status=status.HTTP_404_NOT_FOUND)

    serializer = CalculateRequestSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    result = run_calculation(data)

    history_entry = CalculationHistory.objects.create(
        doctor=request.user,
        patient=patient,
        **{k: v for k, v in data.items()},
        score=result["score"],
        severity=result["severity"],
        recommendation=result["recommendation"],
    )

    return response.Response(
        {
            "id": history_entry.id,
            "patient": PatientSerializer(patient).data,
            "score": result["score"],
            "severity": result["severity"],
            "recommendation": result["recommendation"],
        },
        status=status.HTTP_201_CREATED,
    )


@extend_schema(
    tags=["Calculator"],
    parameters=[OpenApiParameter("mode", OpenApiTypes.STR, description="Фильтр по режиму: dtz или mtz")],
    responses={200: CalculationHistorySerializer(many=True)},
)
class PatientCalculationHistoryView(generics.ListAPIView):
    serializer_class = CalculationHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = CalculationHistory.objects.filter(
            patient_id=self.kwargs["patient_id"]
        ).select_related("patient", "doctor")
        mode = self.request.query_params.get("mode")
        if mode in ("dtz", "mtz"):
            qs = qs.filter(mode=mode)
        return qs


@extend_schema(tags=["Calculator"], responses={200: CalculationHistorySerializer})
class CalculationDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = CalculationHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = CalculationHistory.objects.select_related("patient", "doctor").all()