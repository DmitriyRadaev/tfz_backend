from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager


class AccountManager(BaseUserManager):
    def create_user(self, email, name, surname, patronymic=None, password=None, role="WORKER", **kwargs):
        if not email:
            raise ValueError("Email is required")
        if not name:
            raise ValueError("Name is required")
        if not surname:
            raise ValueError("Surname is required")

        email = self.normalize_email(email)
        user = self.model(
            email=email, name=name, surname=surname,
            patronymic=patronymic or "", role=role, **kwargs
        )
        if password:
            user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, surname, password=None, **kwargs):
        user = self.create_user(
            email=email, name=name, surname=surname,
            password=password, role=Account.Role.SUPERADMIN, **kwargs
        )
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user

    def create_admin(self, email, name, surname, password=None, **kwargs):
        user = self.create_user(
            email=email, name=name, surname=surname,
            password=password, role=Account.Role.ADMIN, **kwargs
        )
        user.is_staff = True
        user.save(using=self._db)
        return user

    def create_worker(self, email, name, surname, patronymic=None, password=None, work=None, position=None, **kwargs):
        user = self.create_user(
            email=email, name=name, surname=surname,
            patronymic=patronymic, password=password,
            role=Account.Role.WORKER, **kwargs
        )
        if work is not None or position is not None:
            WorkerProfile.objects.update_or_create(user=user, defaults={
                "work": work or "",
                "position": position or ""
            })
        return user


class Account(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        SUPERADMIN = "SUPERADMIN", "Главный администратор"
        ADMIN = "ADMIN", "Администратор"
        WORKER = "WORKER", "Работник"

    email = models.EmailField(null=False, blank=False, unique=True)
    name = models.CharField(max_length=50, blank=False, null=False, verbose_name="Имя")
    surname = models.CharField(max_length=50, blank=False, null=False, verbose_name="Фамилия")
    patronymic = models.CharField(max_length=50, blank=True, default="", verbose_name="Отчество")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.WORKER)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = AccountManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name", "surname"]

    def __str__(self):
        full_name = f"{self.surname} {self.name} {self.patronymic}".strip()
        return f"{full_name} ({self.role})"

    def has_perm(self, perm, obj=None):
        if self.is_superuser or self.role == Account.Role.SUPERADMIN:
            return True
        return super().has_perm(perm, obj)

    def has_module_perms(self, app_label):
        if self.is_active and (self.is_superuser or self.role == Account.Role.SUPERADMIN):
            return True
        return self.is_staff

    # синхронизируем is_staff/is_superuser с ролью при сохранении
    def save(self, *args, **kwargs):
        if self.role in (self.Role.ADMIN, self.Role.SUPERADMIN):
            self.is_staff = True
        if self.role == self.Role.SUPERADMIN:
            self.is_superuser = True
        super().save(*args, **kwargs)

    @property
    def is_superadmin(self):
        return self.role == Account.Role.SUPERADMIN

    @property
    def is_admin_role(self):
        return self.role == Account.Role.ADMIN

    @property
    def is_worker(self):
        return self.role == Account.Role.WORKER


class WorkerProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="worker_profile")
    work = models.CharField(max_length=255, blank=True, null=False)
    position = models.CharField(max_length=255, blank=True, null=False)

    def __str__(self):
        return f"Profile for {self.user.email}"


class Patient(models.Model):
    class Gender(models.IntegerChoices):
        MALE = 0, "Мужской"
        FEMALE = 1, "Женский"

    name = models.CharField(max_length=255, verbose_name="Имя")
    surname = models.CharField(max_length=255, verbose_name="Фамилия")
    patronymic = models.CharField(max_length=255, blank=True, default="", verbose_name="Отчество")
    birth_date = models.DateField(verbose_name="Дата рождения")
    gender = models.IntegerField(choices=Gender.choices, verbose_name="Пол")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Пациент"
        verbose_name_plural = "Пациенты"

    def __str__(self):
        return f"{self.surname} {self.name} {self.patronymic}".strip()

    @property
    def full_name(self):
        return f"{self.surname} {self.name} {self.patronymic}".strip()


class CalculationHistory(models.Model):
    class Mode(models.TextChoices):
        DTZ = "dtz", "ДТЗ (Диффузный токсический зоб)"
        MTZ = "mtz", "МТЗ (Многоузловой токсический зоб)"

    class Gender(models.TextChoices):
        MALE = "male", "Мужской"
        FEMALE = "female", "Женский"

    # SET_NULL чтобы расчёт оставался если врач удалён
    doctor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="calculations",
        verbose_name="Врач"
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="calculations",
        verbose_name="Пациент"
    )
    mode = models.CharField(max_length=10, choices=Mode.choices, verbose_name="Режим")

    age = models.PositiveIntegerField(verbose_name="Возраст")
    gender = models.CharField(max_length=10, choices=Gender.choices, verbose_name="Пол")
    st4 = models.FloatField(verbose_name="сТ4 (нг/дл)")
    ttg = models.FloatField(verbose_name="ТТГ (мкМЕ/мл)")
    atrttg = models.FloatField(verbose_name="АтрТТГ (МЕ/л)")
    thyroid_volume = models.FloatField(verbose_name="Объём ЩЖ (мл)")
    eop_stage = models.PositiveIntegerField(verbose_name="Стадия ЭОП")
    thyrostatic_daily_dose_mg = models.FloatField(verbose_name="Суточная доза тиреостатиков (мг)")
    thyrostatic_therapy_duration_months = models.FloatField(verbose_name="Длительность терапии (мес.)")
    ccc_complications = models.BooleanField(default=False, verbose_name="Осложнения ССС")
    compression_syndrome = models.BooleanField(default=False, verbose_name="Компрессионный синдром")
    slco1b1_polymorphism = models.BooleanField(default=False, verbose_name="Полиморфизм SLCO1B1")

    score = models.IntegerField(verbose_name="Балл")
    severity = models.CharField(max_length=20, verbose_name="Степень тяжести")
    recommendation = models.TextField(verbose_name="Рекомендация")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Расчёт"
        verbose_name_plural = "История расчётов"

    def __str__(self):
        patient_name = self.patient.full_name if self.patient else "—"
        return f"{patient_name} | {self.get_mode_display()} | {self.score} баллов | {self.created_at:%d.%m.%Y %H:%M}"