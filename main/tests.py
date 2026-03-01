# tests.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from .services.calculator import calculate_score, get_severity, get_recommendation, run_calculation
from .models import CalculationHistory

Account = get_user_model()

BASE_DATA = {
    "mode": "dtz",
    "age": 35,
    "gender": "male",
    "st4": 3.0,
    "ttg": 0.05,
    "atrttg": 5.0,
    "thyroid_volume": 50.0,
    "eop_stage": 1,
    "thyrostatic_daily_dose_mg": 12.0,
    "thyrostatic_therapy_duration_months": 18,
    "ccc_complications": False,
    "compression_syndrome": False,
    "slco1b1_polymorphism": False,
}


class CalculatorServiceTest(TestCase):

    def test_score_age_brackets(self):
        data = {**BASE_DATA, "age": 25}
        score_young = calculate_score(data, False)
        data["age"] = 55
        score_old = calculate_score(data, False)
        self.assertGreater(score_young, score_old)

    def test_mtz_adds_4_points(self):
        score_dtz = calculate_score(BASE_DATA, multiple_thyroid_nodules=False)
        score_mtz = calculate_score(BASE_DATA, multiple_thyroid_nodules=True)
        self.assertEqual(score_mtz - score_dtz, 4)

    def test_severity_boundaries(self):
        self.assertEqual(get_severity(0), "лёгкая")
        self.assertEqual(get_severity(13), "лёгкая")
        self.assertEqual(get_severity(14), "средняя")
        self.assertEqual(get_severity(26), "средняя")
        self.assertEqual(get_severity(27), "тяжёлая")
        self.assertEqual(get_severity(40), "тяжёлая")

    def test_run_calculation_returns_required_keys(self):
        result = run_calculation(BASE_DATA)
        self.assertIn("score", result)
        self.assertIn("severity", result)
        self.assertIn("recommendation", result)

    def test_dtz_recommendation_thyroidectomy(self):
        data = {
            **BASE_DATA,
            "mode": "dtz",
            "slco1b1_polymorphism": False,
            "atrttg": 5.0,       # high antibodies
            "gender": "male",
            "ccc_complications": False,
            # score должен быть >= 18
            "age": 25,
            "st4": 5.0,
            "ttg": 0.05,
        }
        result = run_calculation(data)
        self.assertIn("Тиреоидэктомия", result["recommendation"])

    def test_fallback_recommendation(self):
        # Условия не попадают ни в одну ветку
        data = {
            **BASE_DATA,
            "slco1b1_polymorphism": True,
            "atrttg": 5.0,          # high antibodies → не попадёт в СРЩЖ для DTZ
            "ccc_complications": False,
            "age": 60,
            "st4": 1.0,
            "ttg": 3.0,             # score будет очень низкий — лёгкая
        }
        result = run_calculation(data)
        self.assertIn("консультация", result["recommendation"])


class CalculatorAPITest(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.user = Account.objects.create_user(
            email="test@test.com",
            name="Test",
            surname="User",
            password="testpass123",
        )
        self.client.force_authenticate(user=self.user)
        self.url = "/api/calculator/calculate/"

    def test_calculate_creates_history(self):
        response = self.client.post(self.url, BASE_DATA, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CalculationHistory.objects.filter(user=self.user).count(), 1)

    def test_unauthenticated_returns_401(self):
        self.client.logout()
        response = self.client.post(self.url, BASE_DATA, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_invalid_data_returns_400(self):
        bad_data = {**BASE_DATA, "age": -1}
        response = self.client.post(self.url, bad_data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_history_list_returns_only_own(self):
        # Создаём второго пользователя с его расчётом
        other_user = Account.objects.create_user(
            email="other@test.com", name="Other", surname="User", password="pass"
        )
        CalculationHistory.objects.create(
            user=other_user, **{k: v for k, v in BASE_DATA.items()},
            score=10, severity="лёгкая", recommendation="test"
        )

        self.client.post(self.url, BASE_DATA, format="json")  # наш расчёт

        response = self.client.get("/api/calculator/history/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)  # только наш

    def test_history_filter_by_mode(self):
        self.client.post(self.url, {**BASE_DATA, "mode": "dtz"}, format="json")
        self.client.post(self.url, {**BASE_DATA, "mode": "mtz"}, format="json")

        response = self.client.get("/api/calculator/history/?mode=dtz")
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["mode"], "dtz")