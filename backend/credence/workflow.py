from hashlib import sha256
from json import dumps

from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

from credence.domain import COMMANDS, Role, eligibility, risk, schedule
from credence.store import many, one, sql


def pack(value):
    return dumps(jsonable_encoder(value), ensure_ascii=False, sort_keys=True)


def member(conn, organization, actor):
    return one(
        conn,
        "SELECT actor FROM organization_members WHERE organization_id=:o AND actor=:u",
        o=organization,
        u=actor["id"],
    )


def application(conn, id, actor, *, lock=False):
    item = one(
        conn,
        "SELECT * FROM applications WHERE id=:id" + (" FOR UPDATE" if lock else ""),
        id=id,
    )
    if (
        not item
        or (
            actor["role"] == Role.APPLICANT
            and not member(conn, item["organization_id"], actor)
        )
        or (
            actor["role"] == Role.ANALYST
            and item["analyst_id"] != actor["id"]
            and item["state"] != "SUBMITTED"
        )
        or (
            actor["role"] == Role.RISK
            and (
                item["state"]
                not in {
                    "DECISION_PENDING",
                    "OFFERED",
                    "REJECTED",
                    "ACCEPTED",
                    "DECLINED",
                    "EXPIRED",
                }
                and not one(
                    conn,
                    "SELECT id FROM evidence WHERE app_id=:id AND kind='RECOMMENDATION' LIMIT 1",
                    id=id,
                )
            )
        )
    ):
        raise HTTPException(404, "APPLICATION_NOT_FOUND")
    return item


def event(conn, id, actor, request_id, action, previous=None, state=None, reason=None):
    sql(
        conn,
        """INSERT INTO events(app_id,actor,action,previous,state,reason,request_id)
                VALUES (:id,:actor,:action,:previous,:state,:reason,:request)""",
        id=id,
        actor=actor["id"],
        action=action,
        previous=previous,
        state=state,
        reason=reason,
        request=request_id,
    )


def document_set(conn, id):
    return many(
        conn,
        "SELECT DISTINCT ON(kind) * FROM documents WHERE app_id=:id ORDER BY kind,version DESC",
        id=id,
    )


def detail(conn, item, actor):
    id = item["id"]
    evidence = many(
        conn, "SELECT * FROM evidence WHERE app_id=:id ORDER BY created_at,id", id=id
    )
    current = {
        item["current_check"],
        item["current_risk"],
        item["current_recommendation"],
    }
    for row in evidence:
        row["current"] = row["id"] in current or row["kind"] == "DECISION"
    docs = document_set(conn, id)
    verified_ids = {
        key
        for row in evidence
        if row["kind"] == "ELIGIBILITY" and row["current"]
        for key in row["payload"].get("document_ids", [])
    }
    for doc in docs:
        doc["status"] = "VERIFIED" if str(doc["id"]) in verified_ids else "PENDING"
    events = many(
        conn,
        "SELECT e.*,u.name AS actor_name FROM events e JOIN users u ON e.actor=u.id WHERE app_id=:id ORDER BY e.id",
        id=id,
    )
    snapshots = many(
        conn, "SELECT * FROM snapshots WHERE app_id=:id ORDER BY version", id=id
    )
    if actor["role"] == Role.APPLICANT:
        evidence = [row for row in evidence if row["kind"] == "DECISION"]
        events = [
            row
            for row in events
            if row["action"] not in {"validate", "assess", "recommend", "return"}
        ]
    return {
        **item,
        "documents": docs,
        "evidence": evidence,
        "events": events,
        "snapshots": snapshots,
        "offer": one(conn, "SELECT * FROM offers WHERE app_id=:id", id=id),
    }


def change(conn, item, **fields):
    approved = {
        "state",
        "data",
        "data_version",
        "analyst_id",
        "current_check",
        "current_risk",
        "current_recommendation",
    }
    assert fields.keys() <= approved
    reason = fields.pop("data", None)
    if reason is not None:
        fields["data"] = pack(reason)
    assignments = "".join(
        f",{k}=CAST(:{k} AS jsonb)" if k == "data" else f",{k}=:{k}" for k in fields
    )
    result = one(
        conn,
        f"""UPDATE applications SET revision=revision+1,updated_at=clock_timestamp(){assignments}
                         WHERE id=:id RETURNING *""",
        id=item["id"],
        **fields,
    )
    return result


def append_evidence(conn, item, actor, kind, payload):
    return one(
        conn,
        """INSERT INTO evidence(app_id,version,kind,actor,payload)
                     VALUES (:id,:version,:kind,:actor,CAST(:payload AS jsonb)) RETURNING id""",
        id=item["id"],
        version=item["data_version"],
        kind=kind,
        actor=actor["id"],
        payload=pack(payload),
    )["id"]


def current(conn, item, key):
    row = one(
        conn,
        "SELECT * FROM evidence WHERE id=:id AND app_id=:app AND version=:v",
        id=item[key],
        app=item["id"],
        v=item["data_version"],
    )
    if not row:
        raise HTTPException(409, "CURRENT_EVIDENCE_REQUIRED")
    return row


def command(conn, item, actor, request_id, action, payload, key):
    role, states = COMMANDS[action]
    if actor["role"] != role:
        raise HTTPException(403, "ROLE_FORBIDDEN")
    if role == Role.ANALYST and action != "claim" and item["analyst_id"] != actor["id"]:
        raise HTTPException(403, "ASSIGNED_ANALYST_REQUIRED")
    id = item["id"]
    digest = sha256(pack([action, payload]).encode()).hexdigest()
    receipt = one(
        conn,
        "SELECT * FROM receipts WHERE app_id=:id AND actor=:actor AND key=:key",
        id=id,
        actor=actor["id"],
        key=key,
    )
    if receipt:
        if receipt["digest"] != digest:
            raise HTTPException(409, "IDEMPOTENCY_CONFLICT")
        return {**receipt["payload"], "replayed": True}
    if payload["revision"] != item["revision"]:
        raise HTTPException(409, "REVISION_CONFLICT")
    if action == "recommend" and item["state"] == "INFO_REQUIRED":
        raise HTTPException(409, "CURRENT_EVIDENCE_REQUIRED")
    if item["state"] not in states:
        raise HTTPException(409, "INVALID_TRANSITION")
    fields = {}
    reason = payload.get("reason")
    if action == "submit":
        product = one(
            conn, "SELECT * FROM products WHERE id=:id", id=item["product_id"]
        )
        org = one(
            conn,
            "SELECT * FROM organizations WHERE id=:id FOR SHARE",
            id=item["organization_id"],
        )
        docs = document_set(conn, id)
        checks = eligibility(item["data"], product, docs, org["active"])
        if not all(checks.values()):
            raise HTTPException(422, {"code": "INELIGIBLE", "checks": checks})
        version = item["data_version"] + 1
        snapshot = {
            "data": item["data"],
            "product": product,
            "organization": org,
            "documents": docs,
            "checks": checks,
        }
        sql(
            conn,
            "INSERT INTO snapshots(app_id,version,payload) VALUES (:id,:v,CAST(:payload AS jsonb))",
            id=id,
            v=version,
            payload=pack(snapshot),
        )
        fields = {"state": "SUBMITTED", "data_version": version, "analyst_id": None}
    elif action == "claim":
        fields = {"state": "REVIEW", "analyst_id": actor["id"]}
    elif action in {"validate", "assess", "recommend", "decide"}:
        snap = one(
            conn,
            "SELECT payload FROM snapshots WHERE app_id=:id AND version=:v",
            id=id,
            v=item["data_version"],
        )["payload"]
        if action == "validate":
            if item["current_check"]:
                raise HTTPException(409, "ALREADY_VALIDATED")
            fields["current_check"] = append_evidence(
                conn,
                item,
                actor,
                "ELIGIBILITY",
                {
                    "checks": snap["checks"],
                    "document_ids": [d["id"] for d in snap["documents"]],
                },
            )
        elif action == "assess":
            current(conn, item, "current_check")
            if item["current_risk"]:
                raise HTTPException(409, "ALREADY_ASSESSED")
            fields["current_risk"] = append_evidence(
                conn, item, actor, "RISK", risk(snap["data"])
            )
        elif action == "recommend":
            current(conn, item, "current_risk")
            fields = {
                "state": "DECISION_PENDING",
                "current_recommendation": append_evidence(
                    conn,
                    item,
                    actor,
                    "RECOMMENDATION",
                    {
                        "choice": payload["choice"],
                        "reason": reason,
                        "risk_id": item["current_risk"],
                    },
                ),
            }
        else:
            recommendation = current(conn, item, "current_recommendation")
            assessment = current(conn, item, "current_risk")
            if recommendation["actor"] == actor["id"] or recommendation["payload"][
                "risk_id"
            ] != str(assessment["id"]):
                raise HTTPException(409, "INDEPENDENT_CURRENT_REVIEW_REQUIRED")
            terms = {
                **{k: snap["data"][k] for k in ("amount", "months")},
                "rate": snap["product"]["rate"],
                "product_version": snap["product"]["version"],
                "currency": "RUB",
            }
            decision = append_evidence(
                conn,
                item,
                actor,
                "DECISION",
                {
                    "choice": payload["choice"],
                    "reason": reason,
                    "recommendation_id": recommendation["id"],
                    "risk_id": assessment["id"],
                    "terms": terms,
                },
            )
            fields = {"state": "REJECTED"}
            if payload["choice"] == "APPROVE":
                terms["schedule"] = schedule(
                    terms["amount"], terms["months"], terms["rate"]
                )
                sql(
                    conn,
                    """INSERT INTO offers(app_id,decision_id,terms,expires_at)
                            VALUES (:id,:decision,CAST(:terms AS jsonb),clock_timestamp()+interval '7 days')""",
                    id=id,
                    decision=decision,
                    terms=pack(terms),
                )
                fields = {"state": "OFFERED"}
    elif action == "request_info":
        fields = {
            "state": "INFO_REQUIRED",
            "current_risk": None,
            "current_check": None,
            "current_recommendation": None,
        }
    elif action == "return":
        fields = {"state": "REVIEW", "current_recommendation": None}
    elif action in {"respond", "expire"}:
        offer = one(
            conn,
            "SELECT expires_at<=COALESCE(CAST(:at AS timestamptz),clock_timestamp()) AS expired FROM offers WHERE app_id=:id AND state='OPEN' FOR UPDATE",
            id=id,
            at=payload.get("at"),
        )
        if not offer or (action == "expire" and not offer["expired"]):
            raise HTTPException(409, "OFFER_NOT_EXPIRABLE")
        state = (
            "EXPIRED"
            if offer["expired"]
            else "ACCEPTED"
            if payload["choice"] == "ACCEPT"
            else "DECLINED"
        )
        sql(conn, "UPDATE offers SET state=:state WHERE app_id=:id", id=id, state=state)
        fields = {"state": state}
    elif action == "withdraw":
        fields = {"state": "WITHDRAWN"}
    result = change(conn, item, **fields)
    event(conn, id, actor, request_id, action, item["state"], result["state"], reason)
    if action in {"request_info", "decide"}:
        sql(
            conn,
            """INSERT INTO notifications(actor,app_id,message)
                    SELECT actor,:id,:message FROM organization_members WHERE organization_id=:org""",
            id=id,
            org=item["organization_id"],
            message=reason
            if action == "request_info"
            else "По заявке принято решение.",
        )
    result = jsonable_encoder(result)
    sql(
        conn,
        "INSERT INTO receipts VALUES (:id,:u,:key,:digest,CAST(:payload AS jsonb))",
        id=id,
        u=actor["id"],
        key=key,
        digest=digest,
        payload=pack(result),
    )
    return {**result, "replayed": False}
