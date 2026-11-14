import pytest
from credence.domain import eligibility, risk, schedule


@pytest.mark.parametrize(
    ("age", "debt", "profit", "score"),
    [(24, 60, 1, 0), (23, 60, 1, 25), (23, 61, 0, 75)],
)
def test_risk_thresholds(age, debt, profit, score):
    result = risk(
        {"age": age, "debt": debt, "profit": profit, "revenue": 100, "amount": 40}
    )
    assert result["score"] == score
    assert sum(f["points"] for f in result["factors"]) == score


@pytest.mark.parametrize(
    ("amount", "months", "rate"),
    [(101, 6, 1450), (60, 60, 0), (10**12, 36, 1320), (120000, 6, 1200)],
)
def test_schedule_preserves_amount(amount, months, rate):
    result = schedule(amount, months, rate)
    assert len(result) == months and result[-1]["balance"] == 0
    assert sum(row["principal"] for row in result) == amount
    assert result[0]["interest"] == (amount * rate + 60000) // 120000
    assert all(row["payment"] == row["principal"] + row["interest"] for row in result)


def test_eligibility_failures():
    result = eligibility(
        {"amount": 1, "months": 3},
        {"min_amount": 5, "max_amount": 10, "min_months": 6, "max_months": 12},
        [],
        False,
    )
    assert not any(result.values())
