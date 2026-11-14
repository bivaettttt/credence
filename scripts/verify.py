import os
from concurrent.futures import ThreadPoolExecutor

import httpx
from credence.lab import Scenario
from credence.store import db, sql
from sqlalchemy.exc import IntegrityError

with httpx.Client(base_url="http://127.0.0.1:8000", timeout=30) as client:
    password = os.environ["DEMO_PASSWORD"]

    def login(username):
        resp = client.post(
            "/api/auth/login", json={"username": username, "password": password}
        )
        resp.raise_for_status()
        return {"Authorization": "Bearer " + resp.json()["token"]}

    admin, applicant = login("admin"), login("applicant")
    assert client.get("/api/applications").status_code == 401
    assert client.get("/api/users", headers=applicant).status_code == 403
    assert client.post("/api/lab/success", headers=applicant).status_code == 403
    for scenario in Scenario:
        response = client.post("/api/lab/" + scenario, headers=admin)
        assert response.status_code == 200, (scenario, response.text)
        row = response.json()
        assert row["passed"], (scenario, row["checks"])
        assert all(step["request_id"] for step in row["traffic"])
        if scenario == Scenario.success:
            id = row["application_id"]
            record = client.get("/api/applications/" + id, headers=admin).json()
            decision = next(e for e in record["evidence"] if e["kind"] == "DECISION")
            offer = record["offer"]
            assert all(
                offer["terms"][k] == v for k, v in decision["payload"]["terms"].items()
            )
            assert offer["state"] == "ACCEPTED"
            for table in ("snapshots", "evidence", "offers", "events"):
                try:
                    with db.begin() as conn:
                        sql(conn, f"DELETE FROM {table} WHERE app_id=:id", id=id)
                except IntegrityError:
                    pass
                else:
                    raise AssertionError(f"{table} evidence was mutable")
    row = client.post("/api/lab/incomplete", headers=admin).json()
    draft = row["before"]
    payload = {
        **draft["data"],
        "revision": draft["revision"],
        "purpose": "Параллельное обновление",
    }
    path = "/api/applications/" + draft["id"]
    with ThreadPoolExecutor(2) as pool:
        statuses = list(
            pool.map(
                lambda _: (
                    client.patch(path, headers=applicant, json=payload).status_code
                ),
                range(2),
            )
        )
    assert sorted(statuses) == [200, 409]
    assert client.post("/api/auth/logout", headers=applicant).status_code == 204
    assert client.get(path, headers=applicant).status_code == 401
print(
    "14 laboratory scenarios, immutability, concurrent draft edits, role gates and session revocation verified"
)
