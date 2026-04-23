from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import WorkerProfile, Patient, CalculationHistory

Account = get_user_model()


# вспомогательные сериализаторы только для swagger-документации
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

class TokenResponseSerializer(serializers.Serializer):
    access_token = serializers.CharField()
    refresh_token = serializers.CharField()


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ("id", "email", "name", "surname", "patronymic", "role",
                  "is_active", "is_staff", "is_superuser", "created_at", "updated_at")
        read_only_fields = ("id", "created_at", "updated_at")


class WorkerRegistrationSerializer(serializers.ModelSerializer):
    work = serializers.CharField(write_only=True, required=True)
    position = serializers.CharField(write_only=True, required=True)
    password = serializers.CharField(write_only=True, min_length=6)
    password2 = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = Account
        fields = ("email", "name", "surname", "patronymic", "password", "password2", "work", "position")

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("password2"):
            raise serializers.ValidationError({"password": "Пароли не совпадают"})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        place = validated_data.pop("work")
        pos = validated_data.pop("position")
        password = validated_data.pop("password")
        return Account.objects.create_worker(
            email=validated_data["email"],
            name=validated_data["name"],
            surname=validated_data["surname"],
            patronymic=validated_data.get("patronymic", ""),
            password=password, work=place, position=pos
        )


class AdminRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    password2 = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = Account
        fields = ("email", "name", "surname", "patronymic", "password", "password2")

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("password2"):
            raise serializers.ValidationError({"password": "Пароли не совпадают"})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        return Account.objects.create_admin(
            email=validated_data["email"],
            name=validated_data["name"],
            surname=validated_data["surname"],
            patronymic=validated_data.get("patronymic", ""),
            password=validated_data["password"]
        )


class SuperAdminRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    password2 = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = Account
        fields = ("email", "name", "surname", "patronymic", "password", "password2")

    def validate(self, attrs):
        if attrs.get("password") != attrs.get("password2"):
            raise serializers.ValidationError({"password": "Пароли не совпадают"})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password2")
        return Account.objects.create_superuser(
            email=validated_data["email"],
            name=validated_data["name"],
            surname=validated_data["surname"],
            patronymic=validated_data.get("patronymic", ""),
            password=validated_data["password"]
        )


class WorkerProfileSerializer(serializers.ModelSerializer):
    user = AccountSerializer(read_only=True)

    class Meta:
        model = WorkerProfile
        fields = ("id", "user", "work", "position")


class PatientSerializer(serializers.ModelSerializer):
    gender_display = serializers.CharField(source="get_gender_display", read_only=True)
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Patient
        fields = ("id", "name", "surname", "patronymic", "birth_date",
                  "gender", "gender_display", "full_name", "created_at")
        read_only_fields = ("id", "created_at")


class CalculateRequestSerializer(serializers.Serializer):
    MODE_CHOICES = [("dtz", "ДТЗ"), ("mtz", "МТЗ")]
    mode = serializers.ChoiceField(choices=MODE_CHOICES)
    age = serializers.IntegerField(min_value=1, max_value=120)
    gender = serializers.ChoiceField(choices=MODE_CHOICES)
    st4 = serializers.FloatField(min_value=0.01)
    ttg = serializers.FloatField(min_value=0.001)
    atrttg = serializers.FloatField(min_value=0.01)
    thyroid_volume = serializers.FloatField(min_value=0.1)
    eop_stage = serializers.IntegerField(min_value=0, max_value=6)
    thyrostatic_daily_dose_mg = serializers.FloatField(min_value=0)
    thyrostatic_therapy_duration_months = serializers.FloatField(min_value=0)
    ccc_complications = serializers.BooleanField()
    compression_syndrome = serializers.BooleanField()
    slco1b1_polymorphism = serializers.BooleanField()


class CalculationHistorySerializer(serializers.ModelSerializer):
    mode_display = serializers.CharField(source="get_mode_display", read_only=True)
    gender_display = serializers.CharField(source="get_gender_display", read_only=True)
    patient = PatientSerializer(read_only=True)
    doctor = AccountSerializer(read_only=True)

    class Meta:
        model = CalculationHistory
        fields = [
            "id", "patient", "doctor",
            "mode", "mode_display",
            "age", "gender", "gender_display",
            "st4", "ttg", "atrttg",
            "thyroid_volume", "eop_stage",
            "thyrostatic_daily_dose_mg",
            "thyrostatic_therapy_duration_months",
            "ccc_complications", "compression_syndrome",
            "slco1b1_polymorphism",
            "score", "severity", "recommendation",
            "created_at",
        ]
        read_only_fields = fields