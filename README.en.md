# Credence · Digital Loan Origination

[Русский](README.ru.md)

Credence models loan origination for synthetic companies. Applicants manage companies, documents and draft applications. Analysts claim work, check materials, calculate an educational risk score and recommend an outcome. Risk officers record an independent decision. Administrators maintain product revisions, users and audit visibility.

## Run

```sh
docker compose up --build
```

[Console](http://127.0.0.1:8110) · [Swagger UI](http://127.0.0.1:8110/api/docs)

Local accounts `applicant`, `other`, `analyst`, `risk` and `admin` use `Credence-demo-local`. See [.env.example](.env.example) for port and initial password settings. Compose waits for PostgreSQL, migrates and seeds synthetic organizations and products. The web listener binds to loopback.

## Workflow and architecture

Submission checks the company, two required document types and product limits. A sealed snapshot pins product and material versions. Validation, assessment and recommendation reference that snapshot. An information request invalidates current evidence. Resubmission captures a new snapshot. Approval and offer creation commit together. The educational schedule uses integer kopecks, basis points and equal principal installments. An offer has a seven-day deadline.

A modular monolith uses Python, FastAPI, Pydantic, SQLAlchemy, Alembic and PostgreSQL. Nginx serves React, TypeScript and Vite. The API verifies role, membership and revision. Critical POST requests require an `Idempotency-Key`. Browser tokens remain in memory and logout revokes the session. Argon2id protects passwords. PostgreSQL triggers protect historical records.

[Requirements and rules](docs/domain.md) · [Architecture, data and diagrams](docs/architecture.md) · [REST/OpenAPI](docs/openapi.json)

## Laboratory and verification

```sh
scripts/lab up
```

Open the [lab on port 8111](http://127.0.0.1:8111) as `admin`. Fourteen scenarios show requests, replies, history and assertions. `scripts/lab reset` recreates the separate lab and its volume. For a demonstration, request more information, show the stale assessment rejection and resubmit before approving an offer. [Verification](docs/verification.md) · [GitHub Actions](https://github.com/bivaettttt/credence/actions) · [12 screenshots](assets/screenshots) · [Walkthrough](docs/demo.md)

## Limits and extensions

All lending data and decisions are synthetic. The score explains rule matches and requires manual review. Documents are metadata. Offer expiry is materialized by an attempted response or the expiry command. Extensions include retention policies, scheduled expiry and independent validation of more complex credit rules. A public license has not been declared. [Status](docs/PROJECT_STATUS.md)
