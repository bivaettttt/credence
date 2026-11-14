# Проверки и трассируемость / Verification and traceability

| ID | Требования | Компонент и проверка |
|---|---|---|
| TC-01 | FR-01/02, NFR-02 | Applicant membership, missing document, product bounds, cross-company access, concurrent PATCH and session revocation. [API verification](../scripts/verify.py) |
| TC-02 | FR-03/04, NFR-01 | Claim, eligibility, additional information, stale evidence and deterministic score. [Workflow](../backend/credence/workflow.py), [unit cases](../tests/test_domain.py) |
| TC-03 | FR-05 | Rejection, independent approval, two parallel decisions and idempotent replay. [Lab](../backend/credence/lab.py) |
| TC-04 | FR-06/07 | Terms match decision, expiry and exact principal sum, immutable rows. [Domain](../backend/credence/domain.py), [API verification](../scripts/verify.py) |
| TC-05 | FR-08/09, NFR-03 | Traceable requests, real PostgreSQL transitions, portals and isolated scenarios. [Playwright](../frontend/e2e/flow.spec.ts) |

Observed results: eight pytest cases, 14 laboratory scenarios and two Chromium flows passed. PostgreSQL rejected changes to immutable history. Concurrent edits and decisions produced one success and one conflict. Both contract drift and core formatting were checked. Four BPMN diagrams passed OMG schema validation.

```sh
scripts/lab up
docker compose -p credence-lab exec -T api python - < scripts/verify.py
cd frontend
npm ci
npx playwright install chromium
npm run e2e
```

[Latest CI runs](https://github.com/bivaettttt/credence/actions)
