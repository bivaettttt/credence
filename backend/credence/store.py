import os

from sqlalchemy import create_engine, text

db = create_engine(
    os.getenv("DATABASE_URL", "postgresql+psycopg://credence@127.0.0.1:56434/credence"),
    pool_pre_ping=True,
    hide_parameters=True,
)


def sql(conn, statement, **params):
    return conn.execute(text(statement), params)


def one(conn, statement, **params):
    row = sql(conn, statement, **params).mappings().one_or_none()
    return dict(row) if row is not None else None


def many(conn, statement, **params):
    return [dict(row) for row in sql(conn, statement, **params).mappings()]
