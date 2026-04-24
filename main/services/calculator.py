# services/calculator.py

def calculate_score(data: dict, multiple_thyroid_nodules: bool) -> int:
    """Считает интегральный балл тяжести тиреотоксикоза."""
    score = 0
    age = data["age"]
    st4 = data["st4"]
    ttg = data["ttg"]
    atrttg = data["atrttg"]
    volume = data["thyroid_volume"]
    eop_stage = data["eop_stage"]
    dose = data["thyrostatic_daily_dose_mg"]
    duration = data["thyrostatic_therapy_duration_months"]

    # 1. Возраст
    if age <= 30:
        score += 3
    elif age <= 39:
        score += 2
    elif age <= 49:
        score += 1

    # 2. Пол
    if data["gender"] == "male": score += 1

    # 3. сТ4 (нг/дл)
    if st4 <= 1.78:
        score += 0
    elif st4 <= 2.78:
        score += 1
    elif st4 <= 3.78:
        score += 2
    elif st4 <= 4.78:
        score += 3
    else:
        score += 4

    # 4. ТТГ (мкМЕ/мл)
    if ttg > 2.5:
        score += 0
    elif ttg >= 0.1:
        score += 1
    else:
        score += 4

    # 5. АтрТТГ (МЕ/л)
    if atrttg <= 1.0:
        score += 0
    elif atrttg <= 3.0:
        score += 1
    elif atrttg <= 5.0:
        score += 2
    elif atrttg <= 10.0:
        score += 3
    else:
        score += 4

    # 6. Объём ЩЖ (мл)
    if volume < 25:
        score += 0
    elif volume <= 40:
        score += 1
    elif volume <= 60:
        score += 2
    elif volume <= 80:
        score += 3
    else:
        score += 4

    # 7. Стадия ЭОП
    score += eop_stage

    # 8. Суточная доза тиреостатиков (мг)
    if dose <= 4.9:
        score += 0
    elif dose <= 10:
        score += 1
    elif dose <= 15:
        score += 2
    elif dose <= 20:
        score += 3
    else:
        score += 4

    # 9. Длительность терапии (месяцы)
    if duration <= 12 or duration > 48:
        score += 4
    elif duration <= 24:
        score += 1
    elif duration <= 36:
        score += 2
    elif duration <= 48:
        score += 3

    # 10–13. Бинарные факторы
    if data["ccc_complications"]: score += 4
    if data["compression_syndrome"]: score += 4
    if not data["slco1b1_polymorphism"]: score += 4
    if multiple_thyroid_nodules: score += 4

    return score


def get_severity(score: int) -> str:
    if score <= 13:
        return "лёгкая"
    elif score <= 26:
        return "средняя"
    else:
        return "тяжёлая"


def get_recommendation(data: dict, score: int, mode: str) -> str:
    severity = get_severity(score)
    # Заголовок как в TS
    summary = f"Интегральный показатель: {score} баллов.\nСтепень тяжести тиреотоксикоза: {severity}.\n\n"

    has_polymorphism = data["slco1b1_polymorphism"]
    is_light_or_medium = score <= 17
    is_medium_or_heavy = score >= 18
    atrttg = data["atrttg"]
    low_antibodies = atrttg <= 3.9
    high_antibodies = atrttg > 3.9
    no_complications = not data["ccc_complications"]
    is_male = data["gender"] == "male"

    advice = ""
    if mode == "dtz":
        advice += "--- Рекомендация для ДТЗ ---\n"
        if has_polymorphism and is_light_or_medium and low_antibodies and no_complications:
            advice += "Субтотальная резекция ЩЖ (СРЩЖ). Обоснование: наличие полиморфизма SLCO1B1; лёгкая/средняя тяжесть (0–17 баллов); титр а/т к рТТГ ≤ 3,90 МЕ/л; отсутствие осложнений ССС."
        elif not has_polymorphism and is_medium_or_heavy and (high_antibodies or is_male):
            reasons = ["отсутствие полиморфизма SLCO1B1", "средняя/тяжёлая тяжесть (18–40 баллов)"]
            if high_antibodies: reasons.append("титр а/т к рТТГ > 3,90 МЕ/л")
            if is_male: reasons.append("мужской пол")
            advice += f"Тиреоидэктомия. Обоснование: {'; '.join(reasons)}."
        else:
            advice += "Требуется индивидуальная консультация специалиста для определения оптимального объёма операции."
    else:
        advice += "--- Рекомендация для МТЗ ---\n"
        if has_polymorphism and is_light_or_medium and no_complications:
            advice += "Субтотальная резекция ЩЖ (СРЩЖ). Обоснование: наличие полиморфизма SLCO1B1; лёгкая/средняя тяжесть (0–17 баллов); отсутствие осложнений ССС."
        elif not has_polymorphism and is_medium_or_heavy:
            advice += "Тиреоидэктомия. Обоснование: отсутствие полиморфизма SLCO1B1; средняя/тяжёлая тяжесть (18–40 баллов); множественные узлы в обеих долях ЩЖ."
        else:
            advice += "Требуется индивидуальная консультация специалиста для определения оптимального объёма операции."

    return summary + advice


def run_calculation(data: dict) -> dict:
    mode = data["mode"]
    multiple_thyroid_nodules = mode == "mtz"
    score = calculate_score(data, multiple_thyroid_nodules)
    severity = get_severity(score)
    recommendation = get_recommendation(data, score, mode)
    return {"score": score, "severity": severity, "recommendation": recommendation}