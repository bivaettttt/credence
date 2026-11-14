import os

from credence.access import passwords
from credence.store import db, one, sql

USERS = (
    ("applicant", "Дарья Лебедева", "APPLICANT"),
    ("other", "Игорь Соколов", "APPLICANT"),
    ("analyst", "Анна Волкова", "CREDIT_ANALYST"),
    ("risk", "Денис Орлов", "RISK_OFFICER"),
    ("admin", "Мария Ким", "ADMIN"),
)


def seed():
    password = os.environ["DEMO_PASSWORD"]
    if len(password) < 12:
        raise SystemExit("DEMO_PASSWORD requires at least 12 characters")
    with db.begin() as conn:
        for username, name, role in USERS:
            user = one(
                conn,
                """INSERT INTO users(username,name,password,role) VALUES (:u,:n,:p,:r)
                          ON CONFLICT DO NOTHING RETURNING id""",
                u=username,
                n=name,
                p=passwords.hash(password),
                r=role,
            )
            if user and role == "APPLICANT":
                org = one(
                    conn,
                    """INSERT INTO organizations(name,industry,registration,profile) VALUES
                              (:name,'Логистика',:reg,'Синтетический профиль учебной компании') RETURNING id""",
                    name="Полярис Логистика"
                    if username == "applicant"
                    else "Кварц Снабжение",
                    reg="DEMO-" + username.upper(),
                )
                sql(
                    conn,
                    "INSERT INTO organization_members VALUES (:o,:u)",
                    o=org["id"],
                    u=user["id"],
                )
        for code, name, minimum, maximum, rate in [
            ("WORKING", "Оборотное финансирование", 10_000_000, 500_000_000, 1450),
            ("CAPEX", "Оборудование", 20_000_000, 900_000_000, 1320),
        ]:
            sql(
                conn,
                """INSERT INTO products(code,version,name,min_amount,max_amount,min_months,max_months,rate,active)
                        VALUES (:code,1,:name,:min,:max,6,36,:rate,true) ON CONFLICT DO NOTHING""",
                code=code,
                name=name,
                min=minimum,
                max=maximum,
                rate=rate,
            )


if __name__ == "__main__":
    seed()
