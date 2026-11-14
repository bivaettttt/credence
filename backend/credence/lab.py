from concurrent.futures import ThreadPoolExecutor
from enum import StrEnum
from uuid import uuid4

import httpx
from fastapi import HTTPException

from credence.access import digest, token_urlsafe
from credence.store import db, many, one, sql


class Scenario(StrEnum):
    success = "success"
    incomplete = "incomplete"
    additional = "additional"
    mismatch = "mismatch"
    high = "high"
    review = "review"
    approval = "approval"
    rejection = "rejection"
    stale = "stale"
    concurrent = "concurrent"
    replay = "replay"
    expired = "expired"
    invalid = "invalid"
    foreign = "foreign"


def run_scenario(scenario: Scenario):
    # The API is reached through a real socket to the isolated demo service.
    users = {}
    with db.begin() as conn:
        for user in many(
            conn,
            "SELECT id,username FROM users WHERE username IN ('applicant','other','analyst','risk')",
        ):
            token = token_urlsafe(32)
            users[user["username"]] = token
            sql(
                conn,
                "INSERT INTO sessions VALUES (:token,:actor,clock_timestamp()+interval '5 minutes')",
                token=digest(token),
                actor=user["id"],
            )
    if set(users) != {"applicant", "other", "analyst", "risk"}:
        raise HTTPException(409, "LAB_FIXTURES_MISSING")
    records = []
    try:
        with httpx.Client(
            base_url="http://127.0.0.1:8000", timeout=10, trust_env=False
        ) as client:

            def send(method, path, actor, body=None, key=None):
                headers = {"Authorization": "Bearer " + users[actor]}
                if key:
                    headers["Idempotency-Key"] = key
                result = client.request(
                    method, "/api" + path, headers=headers, json=body
                )
                trace = {
                    "method": method,
                    "path": path,
                    "role": actor,
                    "body": body,
                    "key": key,
                    "status": result.status_code,
                    "response": result.json(),
                    "request_id": result.headers["X-Request-ID"],
                }
                records.append(trace)
                return trace

            def expect(trace, status):
                if trace["status"] != status:
                    raise RuntimeError(
                        f"Unexpected laboratory outcome for {trace['path']}"
                    )
                return trace["response"]

            company = expect(
                send(
                    "POST",
                    "/organizations",
                    "applicant",
                    {
                        "name": "Credence Lab " + uuid4().hex[:6],
                        "industry": "Логистика",
                        "profile": "Синтетический эксперимент",
                    },
                ),
                201,
            )
            products = expect(send("GET", "/loan-products", "applicant"), 200)
            product = next(p for p in products if p["code"] == "WORKING")
            data = {
                "amount": product["min_amount"] if scenario != Scenario.mismatch else 1,
                "months": product["min_months"],
                "purpose": "Учебная закупка",
                "revenue": 100_000_000,
                "debt": 90_000_000 if scenario == Scenario.high else 1_000_000,
                "profit": -100 if scenario == Scenario.high else 10_000_000,
                "age": 12 if scenario == Scenario.high else 60,
            }
            initial = expect(
                send(
                    "POST",
                    "/applications",
                    "applicant",
                    dict(data, organization_id=company["id"], product_id=product["id"]),
                ),
                201,
            )
            path = "/applications/" + initial["id"]
            revision = initial["revision"]

            def step(action, actor, expected=200, **extra):
                nonlocal revision
                outcome = send(
                    "POST",
                    path + "/" + action,
                    actor,
                    dict(extra, revision=revision),
                    uuid4().hex,
                )
                result = expect(outcome, expected)
                if expected == 200:
                    revision = result["revision"]
                return result

            def document(kind):
                nonlocal revision
                inp = {
                    "revision": revision,
                    "kind": kind,
                    "label": "Учебные метаданные",
                }
                revision = expect(
                    send("POST", path + "/documents", "applicant", inp), 201
                )["revision"]

            def review():
                step("submit", "applicant")
                step("claim", "analyst")
                step("validate", "analyst")
                step("assess", "analyst")

            if scenario == Scenario.foreign:
                expect(send("GET", path, "other"), 404)
            elif scenario == Scenario.invalid:
                step("respond", "applicant", 409, choice="ACCEPT")
            elif scenario == Scenario.incomplete:
                assert (
                    step("submit", "applicant", 422)["detail"]["checks"]["documents"]
                    is False
                )
            else:
                document("FINANCIAL")
                document("REGISTRATION")
                if scenario == Scenario.mismatch:
                    assert (
                        step("submit", "applicant", 422)["detail"]["checks"]["amount"]
                        is False
                    )
                else:
                    review()
                    if scenario in {Scenario.additional, Scenario.stale}:
                        step(
                            "request_info",
                            "analyst",
                            reason="Подтвердите новый объём задолженности.",
                        )
                        if scenario == Scenario.stale:
                            result = step(
                                "recommend",
                                "analyst",
                                409,
                                choice="APPROVE",
                                reason="Проверка устаревшей оценки.",
                            )
                            assert result["detail"] == "CURRENT_EVIDENCE_REQUIRED"
                        data["debt"] = 70_000_000
                        revision = expect(
                            send(
                                "PATCH",
                                path,
                                "applicant",
                                dict(data, revision=revision),
                            ),
                            200,
                        )["revision"]
                        document("SUPPORTING")
                        review()
                    if scenario == Scenario.high:
                        record = expect(send("GET", path, "analyst"), 200)
                        assert (
                            next(e for e in record["evidence"] if e["kind"] == "RISK")[
                                "payload"
                            ]["category"]
                            == "HIGH"
                        )
                    if scenario not in {
                        Scenario.high,
                        Scenario.additional,
                        Scenario.stale,
                        Scenario.review,
                    }:
                        step(
                            "recommend",
                            "analyst",
                            choice="APPROVE",
                            reason="Рассмотрены учебные материалы.",
                        )
                        if scenario != Scenario.approval:
                            body = {
                                "revision": revision,
                                "choice": "REJECT"
                                if scenario == Scenario.rejection
                                else "APPROVE",
                                "reason": "Независимая учебная проверка.",
                            }
                            key = uuid4().hex

                            def decide(token):
                                return send(
                                    "POST", path + "/decide", "risk", body, token
                                )

                            if scenario == Scenario.concurrent:
                                with ThreadPoolExecutor(2) as pool:
                                    results = list(pool.map(decide, [key, uuid4().hex]))
                                assert sorted(r["status"] for r in results) == [
                                    200,
                                    409,
                                ]
                            else:
                                decision = expect(decide(key), 200)
                                revision = decision["revision"]
                                if scenario == Scenario.replay:
                                    assert expect(decide(key), 200)["replayed"]
                                if scenario == Scenario.success:
                                    assert (
                                        step("respond", "applicant", choice="ACCEPT")[
                                            "state"
                                        ]
                                        == "ACCEPTED"
                                    )
                                if scenario == Scenario.expired:
                                    from datetime import UTC, datetime, timedelta

                                    # Evaluate the same server transition at a future demo instant.
                                    result = expect(
                                        send(
                                            "POST",
                                            path + "/lab-expire",
                                            "applicant",
                                            {
                                                "revision": revision,
                                                "at": (
                                                    datetime.now(UTC)
                                                    + timedelta(days=8)
                                                ).isoformat(),
                                            },
                                            uuid4().hex,
                                        ),
                                        200,
                                    )
                                    assert result["state"] == "EXPIRED"
            with db.connect() as conn:
                final = one(
                    conn,
                    "SELECT state,revision,data_version FROM applications WHERE id=:id",
                    id=initial["id"],
                )
                events = many(
                    conn,
                    "SELECT action,previous,state,request_id FROM events WHERE app_id=:id ORDER BY id",
                    id=initial["id"],
                )
                decisions = sql(
                    conn,
                    "SELECT count(*) FROM evidence WHERE app_id=:id AND kind='DECISION'",
                    id=initial["id"],
                ).scalar_one()
            expected = {
                Scenario.success: "ACCEPTED",
                Scenario.incomplete: "DRAFT",
                Scenario.additional: "REVIEW",
                Scenario.mismatch: "DRAFT",
                Scenario.high: "REVIEW",
                Scenario.review: "REVIEW",
                Scenario.approval: "DECISION_PENDING",
                Scenario.rejection: "REJECTED",
                Scenario.stale: "REVIEW",
                Scenario.concurrent: "OFFERED",
                Scenario.replay: "OFFERED",
                Scenario.expired: "EXPIRED",
                Scenario.invalid: "DRAFT",
                Scenario.foreign: "DRAFT",
            }
            checks = {
                "expected_state": final["state"] == expected[scenario],
                "single_decision": decisions <= 1,
                "audit_matches": bool(events) and events[-1]["state"] == final["state"],
            }
            return {
                "scenario": scenario,
                "application_id": initial["id"],
                "before": initial,
                "after": final,
                "checks": checks,
                "passed": all(checks.values()),
                "events": events,
                "traffic": records,
            }
    finally:
        with db.begin() as conn:
            for token in users.values():
                sql(conn, "DELETE FROM sessions WHERE digest=:d", d=digest(token))
