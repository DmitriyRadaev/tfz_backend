# admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Account, WorkerProfile, Patient, CalculationHistory


@admin.register(Account)
class AccountAdmin(UserAdmin):
    list_display = ("email", "name", "surname", "role", "is_active", "is_staff", "created_at")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("email", "name", "surname")
    ordering = ("-created_at",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Личные данные", {"fields": ("name", "surname", "patronymic")}),
        ("Роль и доступ", {"fields": ("role", "is_active", "is_staff", "is_superuser")}),
        ("Даты", {"fields": ("created_at", "updated_at")}),
    )
    readonly_fields = ("created_at", "updated_at")
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "name", "surname", "patronymic", "role", "password1", "password2"),
        }),
    )


@admin.register(WorkerProfile)
class WorkerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "work", "position")
    search_fields = ("user__email", "user__name", "user__surname")


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("full_name", "birth_date", "gender", "created_at")
    list_filter = ("gender",)
    search_fields = ("name", "surname", "patronymic")
    ordering = ("-created_at",)


@admin.register(CalculationHistory)
class CalculationHistoryAdmin(admin.ModelAdmin):
    list_display = ("patient", "doctor", "mode", "score", "severity", "created_at")
    list_filter = ("mode", "severity", "created_at")
    search_fields = ("patient__surname", "patient__name", "doctor__email")
    readonly_fields = ("score", "severity", "recommendation", "created_at")
    ordering = ("-created_at",)