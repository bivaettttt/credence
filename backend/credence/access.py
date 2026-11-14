from hashlib import sha256
from secrets import token_urlsafe
from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from credence.store import db, one, sql

passwords = PasswordHasher()
dummy = passwords.hash(token_urlsafe(32))
bearer = HTTPBearer(auto_error=False)


def digest(secret):
    return sha256(secret.encode()).hexdigest()


def login(payload):
    with db.begin() as conn:
        user = one(conn, "SELECT * FROM users WHERE username=:u", u=payload.username)
        try:
            valid = passwords.verify(
                user["password"] if user else dummy, payload.password
            )
        except VerifyMismatchError:
            valid = False
        if not user or not user["active"] or not valid:
            raise HTTPException(401, "INVALID_CREDENTIALS")
        token = token_urlsafe(32)
        sql(
            conn,
            "INSERT INTO sessions VALUES (:d,:u,clock_timestamp()+interval '8 hours')",
            d=digest(token),
            u=user["id"],
        )
        return {"token": token}


def identity(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
):
    if credentials:
        hashed = digest(credentials.credentials)
        with db.connect() as conn:
            user = one(
                conn,
                """SELECT u.id,u.username,u.name,u.role FROM users u JOIN sessions s ON s.actor=u.id
                             WHERE digest=:d AND expires>clock_timestamp() AND u.active""",
                d=hashed,
            )
        if user:
            return {**user, "session": hashed}
    raise HTTPException(401, "AUTH_REQUIRED")


Actor = Annotated[dict, Depends(identity)]


def require(actor, role):
    if actor["role"] != role:
        raise HTTPException(403, "ROLE_FORBIDDEN")
