import logging
import os
from typing import Annotated, Literal
from uuid import UUID, uuid4

from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from credence import contracts as c
from credence.access import Actor, login, passwords, require
from credence.domain import COMMANDS, Role
from credence.lab import Scenario, run_scenario
from credence.store import db, many, one, sql
from credence.workflow import application, change, command, detail, event, member, pack

app = FastAPI(
    title="Credence",
    version="1.0.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)
P = "/api/applications"
log = logging.getLogger("credence")


@app.middleware("http")
async def correlate(request: Request, call_next):
    request.state.id = uuid4()
    try:
        response = await call_next(request)
    except Exception as error:
        log.error("request_id=%s error=%s", request.state.id, type(error).__name__)
        response = JSONResponse({"detail": "INTERNAL_ERROR"}, 500)
    response.headers["X-Request-ID"] = str(request.state.id)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(RequestValidationError)
async def invalid(request: Request, error: RequestValidationError):
    return JSONResponse({"detail": "INVALID_INPUT"}, 422)


@app.exception_handler(IntegrityError)
async def conflict(request: Request, error: IntegrityError):
    return JSONResponse({"detail": "CONSTRAINT_CONFLICT"}, 409)


@app.get("/health")
def health():
    with db.connect() as conn:
        sql(conn, "SELECT 1 FROM products LIMIT 1")
    return {"status": "ok"}


@app.post("/api/auth/login")
def sign_in(payload: c.Login):
    return login(payload)


@app.post("/api/auth/logout", status_code=204)
def logout(actor: Actor):
    with db.begin() as conn:
        sql(conn, "DELETE FROM sessions WHERE digest=:d", d=actor["session"])


@app.get("/api/me")
def me(actor: Actor):
    return {
        **{k: actor[k] for k in ("id", "role", "name", "username")},
        "lab": actor["role"] == Role.ADMIN and os.getenv("LAB_MODE") == "1",
    }


@app.get("/api/users")
def users(actor: Actor):
    require(actor, Role.ADMIN)
    with db.connect() as conn:
        return many(
            conn, "SELECT id,username,name,role,active FROM users ORDER BY username"
        )


@app.post("/api/users", status_code=201)
def new_user(payload: c.Account, actor: Actor, request: Request):
    require(actor, Role.ADMIN)
    with db.begin() as conn:
        user = one(
            conn,
            """INSERT INTO users(username,name,password,role) VALUES (:u,:n,:p,:r)
                     RETURNING id,username,name,role,active""",
            u=payload.username,
            n=payload.name,
            p=passwords.hash(payload.password),
            r=payload.role,
        )
        event(
            conn, None, actor, request.state.id, "USER_CREATE", reason=str(user["id"])
        )
        return user


@app.get("/api/organizations")
def organizations(actor: Actor):
    require(actor, Role.APPLICANT)
    with db.connect() as conn:
        return many(
            conn,
            "SELECT o.* FROM organizations o JOIN organization_members m ON m.organization_id=o.id WHERE m.actor=:u ORDER BY name",
            u=actor["id"],
        )


@app.post("/api/organizations", status_code=201)
def create_org(payload: c.Organization, actor: Actor, request: Request):
    require(actor, Role.APPLICANT)
    with db.begin() as conn:
        row = one(
            conn,
            """INSERT INTO organizations(name,industry,profile,registration) VALUES
                    (:name,:industry,:profile,'DEMO-'||gen_random_uuid()) RETURNING *""",
            **payload.model_dump(),
        )
        sql(
            conn,
            "INSERT INTO organization_members VALUES (:o,:u)",
            o=row["id"],
            u=actor["id"],
        )
        event(
            conn,
            None,
            actor,
            request.state.id,
            "ORGANIZATION_CREATE",
            reason=str(row["id"]),
        )
        return row


@app.put("/api/organizations/{id}")
def edit_org(id: UUID, payload: c.Organization, actor: Actor, request: Request):
    require(actor, Role.APPLICANT)
    with db.begin() as conn:
        if not member(conn, id, actor):
            raise HTTPException(404, "ORGANIZATION_NOT_FOUND")
        row = one(
            conn,
            "UPDATE organizations SET name=:name,industry=:industry,profile=:profile WHERE id=:id RETURNING *",
            id=id,
            **payload.model_dump(),
        )
        event(
            conn, None, actor, request.state.id, "ORGANIZATION_UPDATE", reason=str(id)
        )
        return row


@app.get("/api/loan-products")
def products(actor: Actor):
    with db.connect() as conn:
        if actor["role"] == Role.ADMIN:
            return many(conn, "SELECT * FROM products ORDER BY code,version DESC")
        return many(
            conn,
            "SELECT * FROM (SELECT DISTINCT ON(code) * FROM products ORDER BY code,version DESC) latest WHERE active",
        )


@app.post("/api/loan-products", status_code=201)
def create_product(payload: c.Product, actor: Actor, request: Request):
    require(actor, Role.ADMIN)
    with db.begin() as conn:
        sql(
            conn,
            "SELECT pg_advisory_xact_lock(hashtextextended(:code,0))",
            code=payload.code,
        )
        row = one(
            conn,
            """INSERT INTO products(code,version,name,min_amount,max_amount,min_months,max_months,rate,active)
                      VALUES (:code,(SELECT COALESCE(max(version),0)+1 FROM products WHERE code=:code),
                              :name,:min_amount,:max_amount,:min_months,:max_months,:rate,:active) RETURNING *""",
            **payload.model_dump(),
        )
        event(
            conn,
            None,
            actor,
            request.state.id,
            "PRODUCT_VERSION",
            reason=str(row["id"]),
        )
        return row


VISIBILITY = """(:role='ADMIN'
 OR (:role='APPLICANT' AND EXISTS(SELECT 1 FROM organization_members m WHERE m.organization_id=a.organization_id AND m.actor=:u))
 OR (:role='CREDIT_ANALYST' AND (a.analyst_id=:u OR a.state='SUBMITTED'))
 OR (:role='RISK_OFFICER' AND (a.state='DECISION_PENDING' OR EXISTS(
 SELECT 1 FROM evidence e WHERE e.app_id=a.id AND e.kind='RECOMMENDATION'))))"""


@app.get(P)
def applications(
    actor: Actor,
    state: str | None = None,
    q: Annotated[str, Query(max_length=100)] = "",
    offset: Annotated[int, Query(ge=0)] = 0,
):
    with db.connect() as conn:
        return many(
            conn,
            f"""SELECT a.*,o.name AS organization,p.name AS product
                      FROM applications a JOIN organizations o ON o.id=a.organization_id JOIN products p ON p.id=a.product_id
                      WHERE {VISIBILITY} AND (CAST(:state AS text) IS NULL OR a.state=:state)
                      AND (o.name ILIKE :pattern OR CAST(a.number AS text) ILIKE :pattern)
                      ORDER BY a.updated_at DESC,a.id LIMIT 50 OFFSET :offset""",
            role=actor["role"],
            u=actor["id"],
            state=state,
            pattern=f"%{q}%",
            offset=offset,
        )


@app.get("/api/tasks")
def tasks(actor: Actor):
    if actor["role"] not in {Role.ANALYST, Role.RISK}:
        raise HTTPException(403, "ROLE_FORBIDDEN")
    return [
        a
        for a in applications(actor, q="", offset=0)
        if a["state"]
        in (
            {"SUBMITTED", "REVIEW"}
            if actor["role"] == Role.ANALYST
            else {"DECISION_PENDING"}
        )
    ]


@app.get("/api/stats")
def stats(actor: Actor):
    with db.connect() as conn:
        return many(
            conn,
            f"""SELECT state,count(*) AS count FROM applications a WHERE {VISIBILITY}
                             GROUP BY state ORDER BY state""",
            role=actor["role"],
            u=actor["id"],
        )


@app.post(P, status_code=201)
def new_application(payload: c.NewApplication, actor: Actor, request: Request):
    require(actor, Role.APPLICANT)
    with db.begin() as conn:
        if not member(conn, payload.organization_id, actor):
            raise HTTPException(404, "ORGANIZATION_NOT_FOUND")
        product = one(
            conn,
            """SELECT * FROM products p WHERE id=:id AND active
                         AND version=(SELECT max(version) FROM products WHERE code=p.code)""",
            id=payload.product_id,
        )
        if not product:
            raise HTTPException(409, "PRODUCT_UNAVAILABLE")
        data = payload.model_dump(exclude={"organization_id", "product_id"})
        row = one(
            conn,
            """INSERT INTO applications(organization_id,product_id,owner_id,data)
                      VALUES (:o,:p,:u,CAST(:data AS jsonb)) RETURNING *""",
            o=payload.organization_id,
            p=payload.product_id,
            u=actor["id"],
            data=pack(data),
        )
        event(conn, row["id"], actor, request.state.id, "create", state="DRAFT")
        return row


@app.get(P + "/{id}")
def get_application(id: UUID, actor: Actor):
    with db.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
        return detail(conn, application(conn, id, actor), actor)


@app.patch(P + "/{id}")
def edit_application(
    id: UUID, payload: c.EditApplication, actor: Actor, request: Request
):
    require(actor, Role.APPLICANT)
    with db.begin() as conn:
        row = application(conn, id, actor, lock=True)
        editable(row, payload.revision)
        result = change(conn, row, data=payload.model_dump(exclude={"revision"}))
        event(conn, id, actor, request.state.id, "edit", row["state"], row["state"])
        return result


def editable(row, revision):
    if row["revision"] != revision:
        raise HTTPException(409, "REVISION_CONFLICT")
    if row["state"] not in {"DRAFT", "INFO_REQUIRED"}:
        raise HTTPException(409, "APPLICATION_LOCKED")


@app.post(P + "/{id}/documents", status_code=201)
def attach(id: UUID, payload: c.Document, actor: Actor, request: Request):
    require(actor, Role.APPLICANT)
    with db.begin() as conn:
        row = application(conn, id, actor, lock=True)
        editable(row, payload.revision)
        document = one(
            conn,
            """INSERT INTO documents(app_id,kind,label,version) VALUES
                        (:id,:kind,:label,(SELECT COALESCE(max(version),0)+1 FROM documents WHERE app_id=:id AND kind=:kind))
                        RETURNING *""",
            id=id,
            kind=payload.kind,
            label=payload.label,
        )
        result = change(conn, row)
        event(
            conn,
            id,
            actor,
            request.state.id,
            "document",
            row["state"],
            row["state"],
            payload.kind,
        )
        return {"document": document, "revision": result["revision"]}


Key = Annotated[
    str, Header(alias="Idempotency-Key", pattern=r"^[A-Za-z0-9._-]{1,128}$")
]
Payloads = {
    "request_info": c.Explain,
    "return": c.Explain,
    "recommend": c.Decision,
    "decide": c.Decision,
    "respond": c.ResponseInput,
}


def register_command(action):
    model = Payloads.get(action, c.Command)

    def execute(id: UUID, payload: model, actor: Actor, request: Request, key: Key):
        require(actor, COMMANDS[action][0])
        with db.begin() as conn:
            row = application(conn, id, actor, lock=True)
            return command(
                conn, row, actor, request.state.id, action, payload.model_dump(), key
            )

    app.add_api_route(
        P + "/{id}/" + action,
        execute,
        methods=["POST"],
        name=action,
        responses={
            403: {"description": "Forbidden"},
            409: {"description": "State, revision or key conflict"},
        },
    )


for operation in COMMANDS:
    register_command(operation)


@app.get(P + "/{id}/{section}")
def history(
    id: UUID,
    section: Literal[
        "events",
        "documents",
        "eligibility",
        "risk-assessments",
        "reviews",
        "decisions",
        "offers",
    ],
    actor: Actor,
):
    record = get_application(id, actor)
    if section in {"events", "documents"}:
        return record[section]
    if section == "offers":
        return record["offer"]
    kind = {
        "eligibility": "ELIGIBILITY",
        "risk-assessments": "RISK",
        "reviews": "RECOMMENDATION",
        "decisions": "DECISION",
    }[section]
    return [row for row in record["evidence"] if row["kind"] == kind]


@app.get("/api/notifications")
def notifications(actor: Actor):
    with db.connect() as conn:
        return many(
            conn,
            "SELECT * FROM notifications WHERE actor=:u ORDER BY id DESC LIMIT 100",
            u=actor["id"],
        )


@app.post("/api/notifications/{id}/read", status_code=204)
def read_notice(id: int, actor: Actor):
    with db.begin() as conn:
        if not one(
            conn,
            "UPDATE notifications SET read_at=COALESCE(read_at,clock_timestamp()) WHERE id=:id AND actor=:u RETURNING id",
            id=id,
            u=actor["id"],
        ):
            raise HTTPException(404, "NOTIFICATION_NOT_FOUND")


@app.get("/api/audit")
def audit(actor: Actor, offset: Annotated[int, Query(ge=0)] = 0):
    require(actor, Role.ADMIN)
    with db.connect() as conn:
        return many(
            conn,
            """SELECT e.*,u.name AS actor_name FROM events e JOIN users u ON u.id=e.actor
                            ORDER BY e.id DESC LIMIT 100 OFFSET :offset""",
            offset=offset,
        )


@app.post("/api/lab/{scenario}")
def lab(scenario: Scenario, actor: Actor):
    require(actor, Role.ADMIN)
    if os.getenv("LAB_MODE") != "1":
        raise HTTPException(403, "LAB_DISABLED")
    try:
        return run_scenario(scenario)
    except (AssertionError, RuntimeError) as error:
        raise HTTPException(500, "LAB_INVARIANT_FAILED") from error


@app.post(P + "/{id}/lab-expire")
def lab_expire(id: UUID, payload: c.LabClock, actor: Actor, request: Request, key: Key):
    require(actor, Role.APPLICANT)
    if os.getenv("LAB_MODE") != "1":
        raise HTTPException(403, "LAB_DISABLED")
    with db.begin() as conn:
        row = application(conn, id, actor, lock=True)
        return command(
            conn,
            row,
            actor,
            request.state.id,
            "expire",
            payload.model_dump(mode="json"),
            key,
        )
