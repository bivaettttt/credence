# Architecture / Архитектура

React → nginx → FastAPI → PostgreSQL. Use a modular monolith and one transaction per command. Separate user sessions, mutable application records and append-only underwriting evidence. Each command locks the application row and requires the expected revision. This serializes concurrent decisions and prevents stale edits. Critical POST commands store response receipts in the same transaction. A change to a key's normalized request yields 409.

ADR-01. Store RUB amounts as integer kopecks and rates in basis points. Use declining balance with equal principal installments, rounding monthly interest half-up to a kopeck. Put the principal remainder in the last installment. This is an educational schedule without fees or calendar adjustments.

ADR-02. Product revisions are append-only. A draft pins its product revision. Submission embeds the selected terms, organization details, inputs and document versions. Eligibility, risk results, recommendations and decisions point to the submitted data version. The current revision tracks every command independently.

ADR-03. Risk is a transparent demonstration over invented corporate inputs. It never chooses the final decision. Four binary rules add points. Missing inputs block submission. Decisions are signed by an authenticated risk officer with a written reason, separate from the assigned analyst. No real suitability or default probability is inferred.

ADR-04. Sessions use opaque random bearer tokens with stored hashes and Argon2id passwords. The browser keeps tokens in memory. Demo credentials and lab are local. A separate Compose project and database volume isolate laboratory records.

## Educational risk policy v1

| Rule | Trigger | Points |
|---|---|---:|
| R-01 | Age < 24 months | 25 |
| R-02 | Debt > 60% of annual revenue | 30 |
| R-03 | Requested amount > 40% of annual revenue | 25 |
| R-04 | Annual profit ≤ 0 | 20 |

LOW < 25, MEDIUM 25–59, HIGH ≥ 60. Integer comparisons avoid division and precision drift. All complete cases go through manual underwriting and independent review. A request for additional data clears current eligibility, risk and recommendation pointers. Submission advances data version. Approving an application atomically creates one decision and a seven-day offer. Expiry is materialized by an explicit response attempt or expiry command.

[Requirements and transition table](domain.md)
