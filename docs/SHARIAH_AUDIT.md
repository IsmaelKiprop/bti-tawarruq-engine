# Shariah Audit Logging

Append-only immutable ledger for Shariah compliance and regulatory review (CMA / CBK). Implemented in **Python** (not .NET): in-process ledger plus optional isolated microservice.

## Design principles

1. **Append-only** — no UPDATE or DELETE on `shariah_audit_logs` (ORM event guards)
2. **Hash chain** — each entry links `previous_hash` → `entry_hash` for tamper detection
3. **State machine** — transactions cannot skip phases (e.g. liquidation without sealed possession)
4. **Dual storage** — primary rows in the **engine** database (`shariah_audit_logs`); optional HTTP mirror to the audit microservice

The primary chain is what ops and regulators should treat as the book. The microservice is a copy. See [DEPLOYMENT.md](DEPLOYMENT.md#shariah-audit-stores-packaging-gap).

## Audit entry fields

| Field | Description |
|-------|-------------|
| `timestamp` | Server UTC |
| `step_id` | e.g. `CONSTRUCTIVE_POSSESSION`, `OWNERSHIP_TRANSFER`, `WAKALA_APPOINTMENT` |
| `entity_type` / `entity_id` | Linked business object |
| `asset_ref_no` | MNO batch hash or external reference |
| `actor_from` / `actor_to` | Parties in the step |
| `payload_hash` | SHA-256 of canonical JSON payload |
| `verified_at` | Required for possession steps |
| `mno_receipt_id` | Required for `CONSTRUCTIVE_POSSESSION` |
| `previous_hash` / `entry_hash` | Chain links |
| `institution_id`, `application_id`, `transaction_id` | Tenant scoping |

## Step IDs (Kenya flow)

```
FINANCING_REQUEST → ELIGIBILITY_CHECK → MURABAHA_PURCHASE → CONSTRUCTIVE_POSSESSION
→ MURABAHA_OFFER → OWNERSHIP_TRANSFER → WAKALA_APPOINTMENT → THIRD_PARTY_LIQUIDATION
→ WALLET_DISBURSEMENT → REPAYMENT_SCHEDULED → REPAYMENT_RECEIVED
```

## In-process API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/kenya/applications/{id}/shariah-audit` | Full trail for application |
| GET | `/api/v1/kenya/applications/{id}/shariah-audit/verify` | Chain + possession seal check |
| GET | `/api/v1/kenya/shariah-audit/verify-chain` | Global or per-institution chain |
| GET | `/api/v1/kenya/shariah-audit/export?format=csv\|json` | Regulatory export |

Malaysia applications: `GET /api/v1/applications/{id}/shariah-audit`

### Origination desk trail

Every Origination action (`create`, decide, step complete, OTP send / verify) calls `log_shariah_step` with `entity_type = fi_desk_case`. Portal **Shariah Audit** (`/shariah`) is on the tester nav.

- Super Admin / BTI Ops / BTI-wide Shariah (`bti.shariah@…`, no institution): **All** institutions or one.
- FI Admin / FI Shariah (`shariah@…`): own tenant.
- Two lists: Kenya applications (possession seal + chain) and origination desk cases with timestamps.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/desk/audit` | Desk-case Shariah rows (`view_shariah`) |
| GET | `/api/v1/desk/cases` | Cases the viewer may see |

See [TESTER_FEEDBACK.md](TESTER_FEEDBACK.md).

## Python microservice

Location: `shariah-audit-service/app.py`

```powershell
$env:SHARIAH_AUDIT_DATABASE_URL="sqlite:///./data/shariah_audit.db"
python shariah-audit-service/app.py
# Listens on :8001
```

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/health` | Service health |
| POST | `/v1/entries` | Append entry (mirrored from engine) |
| GET | `/v1/verify-chain` | Verify hash chain |
| GET | `/v1/export?format=csv\|json` | Export ledger |

### Engine mirror

In `.env`:

```env
SHARIAH_AUDIT_SERVICE_URL=http://localhost:8001
SHARIAH_AUDIT_SERVICE_TOKEN=   # optional Bearer token
```

Every `log_shariah_step()` call appends locally and POSTs to the microservice (failures are logged, non-blocking).

### Where the mirror is stored

| Install | `SHARIAH_AUDIT_DATABASE_URL` | Backup |
|---------|------------------------------|--------|
| Lab / local Compose | `sqlite:////app/data/shariah_audit.db` (compose default) | File under `./data/` — easy to lose |
| BTI VPS (managed) | Same SQLite default unless you change it | Snapshot `./data` **and** Postgres |
| Real on-prem | **Postgres** `tawarruq_audit` on the same server as `tawarruq` | `pg_dump` both databases together |

The service accepts any SQLAlchemy URL. Do **not** point it at the engine database `tawarruq` — `shariah-audit-service` calls `init_db()` and would create engine tables in the mirror. Use a dedicated database:

```env
SHARIAH_AUDIT_SERVICE_URL=http://shariah-audit:8001
SHARIAH_AUDIT_DATABASE_URL=postgresql+psycopg://tawarruq:YOUR_PASSWORD@postgres:5432/tawarruq_audit
```

You can omit the mirror entirely (`SHARIAH_AUDIT_SERVICE_URL` empty). The in-process ledger in the engine Postgres still records every step.

## State machine enforcement

Implemented in `shariah_state_machine.py`:

- **Possession seal** — `CONSTRUCTIVE_POSSESSION` audit entry + verified MNO receipt before Phase 2 offer
- **Transfer before liquidation** — Leg 2 must be `confirmed`
- **Wakala before liquidation** — `customer_agencies` row required (customer consent)
- **Phase index** — cannot jump to Phase 3 while Phase 1 incomplete

Violations raise `ShariahStateViolation` (HTTP 409 on API).

## Code locations

| Module | Role |
|--------|------|
| `services/shariah_ledger_service.py` | Append-only writes, chain verification |
| `services/shariah_crypto.py` | SHA-256 payload + entry hashing |
| `services/shariah_state_machine.py` | Phase / leg enforcement |
| `services/shariah_audit_service.py` | Query, export, application integrity |
| `services/shariah_audit_remote.py` | HTTP mirror to microservice |
| `models/kenya_flow.py` | `ShariahAuditLog` ORM model |
| `services/fi_desk_service.py` | Desk-case `log_shariah_step` on every action |
| `portal/src/pages/ShariahCompliancePage.tsx` | Tenant vs all + desk trail |

## Database migrations

- `002_shariah_immutable_ledger.py` — hash chain columns, possession fields
- ORM guards registered in `database.init_db()`

## Testing

```powershell
pytest tests/test_shariah_audit.py -v
```

Covers: required possession fields, append-only mutations blocked, hash chain validity, phase skip prevention.
