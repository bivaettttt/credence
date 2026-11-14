from enum import StrEnum


class Role(StrEnum):
    APPLICANT = "APPLICANT"
    ANALYST = "CREDIT_ANALYST"
    RISK = "RISK_OFFICER"
    ADMIN = "ADMIN"


COMMANDS = {
    "submit": (Role.APPLICANT, {"DRAFT", "INFO_REQUIRED"}),
    "claim": (Role.ANALYST, {"SUBMITTED"}),
    "validate": (Role.ANALYST, {"REVIEW"}),
    "assess": (Role.ANALYST, {"REVIEW"}),
    "request_info": (Role.ANALYST, {"REVIEW"}),
    "recommend": (Role.ANALYST, {"REVIEW"}),
    "return": (Role.RISK, {"DECISION_PENDING"}),
    "decide": (Role.RISK, {"DECISION_PENDING"}),
    "respond": (Role.APPLICANT, {"OFFERED"}),
    "expire": (Role.APPLICANT, {"OFFERED"}),
    "withdraw": (Role.APPLICANT, {"DRAFT", "SUBMITTED", "REVIEW", "INFO_REQUIRED"}),
}
REQUIRED_DOCUMENTS = {"FINANCIAL", "REGISTRATION"}


def eligibility(data, product, documents, organization_active=True):
    return {
        "amount": product["min_amount"] <= data["amount"] <= product["max_amount"],
        "term": product["min_months"] <= data["months"] <= product["max_months"],
        "documents": REQUIRED_DOCUMENTS <= {item["kind"] for item in documents},
        "financials": all(
            data.get(key) is not None for key in ("revenue", "debt", "profit", "age")
        )
        and (data.get("revenue") or 0) > 0,
        "organization": organization_active,
    }


def risk(data):
    rules = [
        ("R-01", "Возраст компании", data["age"], data["age"] < 24, 25),
        (
            "R-02",
            "Долг к выручке",
            [data["debt"], data["revenue"]],
            data["debt"] * 100 > data["revenue"] * 60,
            30,
        ),
        (
            "R-03",
            "Сумма к выручке",
            [data["amount"], data["revenue"]],
            data["amount"] * 100 > data["revenue"] * 40,
            25,
        ),
        ("R-04", "Годовая прибыль", data["profit"], data["profit"] <= 0, 20),
    ]
    factors = [
        {
            "id": id,
            "label": label,
            "value": value,
            "matched": matched,
            "points": points if matched else 0,
        }
        for id, label, value, matched, points in rules
    ]
    score = sum(factor["points"] for factor in factors)
    return {
        "model": "1.0",
        "score": score,
        "category": "HIGH" if score >= 60 else "MEDIUM" if score >= 25 else "LOW",
        "factors": factors,
        "explanation": "Учебный балл равен сумме сработавших правил.",
    }


def schedule(amount, months, rate):
    chunk, remainder = divmod(amount, months)
    balance = amount
    result = []
    for month in range(1, months + 1):
        principal = chunk + (remainder if month == months else 0)
        interest = (balance * rate + 60_000) // 120_000
        balance -= principal
        result.append(
            {
                "month": month,
                "principal": principal,
                "interest": interest,
                "payment": principal + interest,
                "balance": balance,
            }
        )
    return result
