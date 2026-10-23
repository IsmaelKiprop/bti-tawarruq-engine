# BTI Tawarruq — Users, Access, and Operational Controls

Complete operator and engineer guide for the live identity, permission, maker-checker, billing, reconciliation, and MFA framework.

Companion stakeholder catalogue: [BTI_Tawarruq_Users_ver_001.docx](BTI_Tawarruq_Users_ver_001.docx) (regenerate with `python scripts/build_users_doc.py`). Production deploy and monitoring remain in [PRODUCTION_OPS.md](PRODUCTION_OPS.md).

**Status:** implemented in `bti-tawarruq-engine` (Alembic `011`). Production VPS must pull, rebuild, and run `alembic upgrade head` (or restart SQLite so `init_db` adds the columns). Existing emails, including `admin@buruujfintech.com`, are never overwritten by seed.

---

## 1. Purpose

The engine is one multi-tenant Tawarruq orchestration platform. Banks, SACCOs, and MFIs use it through:

- the ops portal (`ops.buruujfintech.com` / local `:5173`)
- institution API keys (`api.buruujfintech.com` / local `:8000`)

There is **one** identity and permission framework. The portal does not ship a separate app per persona; navigation and writes are gated by role.

**End customers are not portal users.** Customer acceptance, signing, and journey tracking stay on FI channels (mobile app, customer journey APIs). They never receive a BTI ops login.

---

## 2. Design rules (enforced)

| Rule | How the engine enforces it |
|------|----------------------------|
| One framework | `ROLE_PERMISSIONS` in `src/tawarruq/services/rbac.py`; portal `canSeeNavItem` uses permissions only |
| Tenant isolation | Non-cross-tenant queries forced to the caller’s `institution_id` |
| Least privilege | Permissions are stable strings; roles compose them |
| Super Admin is not a trade desk | `platform_admin` has **no** `write_ops` and **no** `approve_txn` |
| Maker-checker | `write_ops` queues Murabaha / liquidation / disbursement; `approve_txn` executes; initiator cannot self-approve |
| Amount limits | `min(institution.approval_limit_amount, user.approval_limit_amount)` when both set |
| Tenant suspend | `Institution.active = false` blocks writes (Super Admin may PATCH the institution) |
| Privileged MFA | Super Admin, BTI Ops, BTI Finance enroll TOTP; login requires the code after enroll |
| Export by role | `export_data` on Shariah pack, audit CSV, billing CSV, recon CSV |
| Exceptions are auditable | Kenya/Malaysia retries require `write_bti_ops` and write an audit row |
| Seed is idempotent | `OPS_SEED_USERS=true` creates missing catalogue users only |

When `AUTH_ENABLED=false` (local mock / lab), auth and maker-checker are skipped so unauthenticated e2e still runs. **Production must set `AUTH_ENABLED=true`.**

---

## 3. Identities

| Kind | Authenticates as | Notes |
|------|------------------|-------|
| Portal human | Email + password → Bearer session | Optional TOTP after enroll |
| Machine client | `X-API-Key` | Role on the key; `api_client` preferred |
| Agent dealer | Portal session bound to `agent_dealer_id` | Float desk only |
| Mobile customer | Mobile JWT | FI channel; skips maker-checker |
| Partner callback | `X-Callback-Token` (if configured) | Daraja / MNO webhooks, not a login |

Session tokens with `typ=mfa` are **not** usable as portal sessions. They only complete the MFA login step.

---

## 4. Roles and permissions

Engine codes are the stable API values. Product names are what the Users page shows.

| Product name | Engine role | Scope | Home page |
|--------------|-------------|-------|-----------|
| BTI Platform Super Admin | `platform_admin` | Platform | `/institutions` |
| BTI Tawarruq Operations | `bti_ops` | Platform | `/ops` |
| BTI Finance / Billing | `bti_finance` | Platform | `/billing` |
| FI Administrator | `institution_admin` | Own tenant | `/` |
| FI Operations Officer | `institution_ops` | Own tenant | `/kenya` |
| FI Approver | `fi_approver` | Own tenant | `/approvals` |
| Shariah / Audit | `shariah_officer` | Tenant | `/shariah` |
| Reconciliation Officer | `reconciler` | Tenant, or BTI-wide if unbound | `/reconciliation` |
| Read only | `read_only` | Own tenant | `/` |
| Agent dealer | `agent_dealer` | Bound dealer pool | `/agent-dealers` |
| Institution API Client | `api_client` | Machine key | (not a portal login) |

### Who may create whom

Only Super Admin (`platform_admin`) and FI Admin (`institution_admin`) may invite. Extra engine roles (`read_only`, `agent_dealer`) stay off the portal invite form. The same map applies to `PATCH` role — you cannot promote someone into a role you are not allowed to create.

| Creator | May invite |
|---------|------------|
| Super Admin | Super Admin, FI Admin, BTI Ops, Shariah, BTI Finance, Recon |
| Super Admin must **not** | FI Ops, FI Approver (FI desk staff are created by the FI Admin) |
| FI Admin (own tenant) | FI Admin, FI Ops, FI Approver, Shariah, Recon |
| FI Admin must **not** | Super Admin, BTI Ops, BTI Finance |
| Everyone else | Nobody |

FI API Client and Sedania stay technical identities, not portal invites. Super Admin provisions API keys on **Webhooks**. FI Admin cannot create keys — they request BTI to onboard.

### Permission catalogue

| Permission | Meaning |
|------------|---------|
| `read` | View tenant-scoped records |
| `write_ops` | Initiate and progress desks (queues checker steps when auth is on) |
| `write_bti_ops` | Cross-tenant operational exceptions (failed-leg retry) |
| `approve_txn` | Approve or reject queued Murabaha / liquidation / disbursement |
| `manage_credentials` | Portal users and webhooks. API key **create** is Super Admin only |
| `manage_integrations` | Partner credential profiles |
| `manage_institutions` | Tenant lifecycle, suspend, approval policy, fee bps |
| `manage_billing` | Generate / pay / list invoices |
| `reconcile` | Scan and resolve settlement items |
| `view_metrics` | Ops Monitor |
| `view_shariah` | Audit ledger and certificates |
| `export_data` | CSV / Shariah pack downloads |
| `api_submit` | Machine quote / buy / sell / status |
| `dealer_desk` | Kenya float top-up only |

### Who holds what

| Role | Permissions |
|------|-------------|
| `platform_admin` | `read`, `write_bti_ops`, `manage_credentials`, `manage_integrations`, `manage_institutions`, `manage_billing`, `reconcile`, `view_metrics`, `view_shariah`, `export_data`, `api_submit` — **not** `write_ops`, **not** `approve_txn` |
| `bti_ops` | `read`, `write_ops`, `write_bti_ops`, `view_metrics`, `view_shariah`, `export_data` |
| `bti_finance` | `read`, `manage_billing`, `view_metrics`, `export_data` |
| `institution_admin` | `read`, `write_ops`, `approve_txn`, `manage_credentials`, `manage_integrations`, `view_metrics`, `view_shariah`, `export_data` |
| `institution_ops` | `read`, `write_ops`, `view_metrics`, `view_shariah` |
| `fi_approver` | `read`, `approve_txn`, `view_metrics` |
| `shariah_officer` | `read`, `view_metrics`, `view_shariah`, `export_data` |
| `reconciler` | `read`, `reconcile`, `view_metrics`, `export_data` |
| `read_only` | `read`, `view_metrics` |
| `agent_dealer` | `dealer_desk` |
| `api_client` | `read`, `api_submit`, `write_ops`, `view_metrics` |

### Write-blocked roles (middleware)

These roles cannot make arbitrary POST/PATCH/DELETE calls: `read_only`, `shariah_officer`, `bti_finance`, `reconciler`, `fi_approver`. Dedicated paths stay open:

- BTI Finance → `/api/v1/ops/billing/*`
- Reconciler → `/api/v1/ops/reconciliation/*`
- FI Approver → `/api/v1/ops/approvals/*` and paths ending `/approve` or `/reject`
- All roles → password change and MFA enroll/confirm

Agent dealers may only hit `/api/v1/ops/auth/*` (me, login, change-password) and `/api/v1/kenya/agent-dealers*`.

---

## 5. Authentication

### Portal login

```
POST /api/v1/ops/auth/login          { email, password }
POST /api/v1/ops/auth/mfa            { mfa_token, code }     # if mfa_enabled
POST /api/v1/ops/auth/change-password
GET  /api/v1/ops/auth/me
```

1. Temporary / seed passwords set `must_change_password`. The portal sends the user to `/change-password` before any other page.
2. If `mfa_enabled`, login returns `mfa_required=true` plus a short-lived `mfa_token` (not a session). The user submits the 6-digit TOTP.
3. Privileged roles (`platform_admin`, `bti_ops`, `bti_finance`) with MFA still off get `mfa_enroll_required=true`. The portal sends them to `/mfa-enroll`. The API does **not** hard-lock unenrolled privileged users (so bootstrap admin is not locked out).

### TOTP enroll

```
POST /api/v1/ops/auth/mfa/enroll     → { secret, otpauth_url, email }
POST /api/v1/ops/auth/mfa/confirm    { code }
```

Algorithm: RFC 6238, HMAC-SHA1, 30-second step, 6 digits, ±1 window. Issuer label: `Buruuj Ops`. Use any authenticator app.

### API keys

Header `X-API-Key` (override with `API_KEY_HEADER`). Super Admin creates keys under **Webhooks**. FI Admin is blocked and should request BTI to onboard:

```http
POST /api/v1/institutions/{id}/api-keys
{ "name": "fi-core-banking", "role": "api_client" }
```

`api_client` skips maker-checker so core-banking integrations execute immediately under the FI’s own dual-control.

### Users API (invite)

```
GET    /api/v1/ops/auth/users
POST   /api/v1/ops/auth/users            { email, full_name, role, institution_id?, approval_limit_amount? }
PATCH  /api/v1/ops/auth/users/{id}       { active?, … }   # activate / deactivate
POST   /api/v1/ops/auth/users/{id}/reset-password
DELETE /api/v1/ops/auth/users/{id}
```

Requires `manage_credentials` **and** the invite rules (`INVITE_TARGETS_BY_CREATOR` in `rbac.py`). Super Admin cannot invite FI Ops or FI Approver. FI Admin cannot invite BTI-internal roles.

**Invite flow:** create generates a temporary password, sets `must_change_password=true`, emails it via SMTP when `SMTP_HOST` is set (local copy under `CUSTOMER_MAIL_DIR/ops_invites/`). When SMTP succeeds, `temporary_password` is omitted from the API response. When SMTP is off or fails, the password is returned once for out-of-band share. Reset-password uses the same delivery. Deactivated users (`active=false`) cannot log in.

---

## 6. Tenant policy

Patch on Institutions (`manage_institutions`):

| Field | Default | Effect |
|-------|---------|--------|
| `active` | `true` | `false` suspends the tenant: session and API-key **writes** return 403 `Institution is suspended`. Super Admin may still PATCH `/api/v1/institutions/{id}` to unsuspend. |
| `approval_steps` | `murabaha,liquidation,disbursement` | Comma-separated checker steps. Omit a step to execute it immediately. |
| `approval_limit_amount` | `null` | Institution-wide cap. `null` = no institution cap. |
| `billing_fee_bps` | `25` | Platform fee in basis points on disbursed volume. |
| `bsas_mode` | `manual_bridge` | Default Malaysia desk: `mock` / `manual_bridge` / `live`. |

Portal: **Institutions** → edit suspend, steps, limit, and fee bps.

---

## 7. Maker-checker

### When a write is queued

`queued_or_none(...)` runs on gated endpoints. It returns HTTP **202** with a queue payload, or `null` so the handler executes immediately.

Immediate execution when any of these is true:

- `AUTH_ENABLED=false`
- caller is a mobile session
- caller role is `api_client`
- the action’s step is **not** in `institution.approval_steps`

Otherwise a `pending_approvals` row is created and the trade is **not** executed.

Duplicate pending rows for the same institution + action + application + transaction are reused (idempotent queue).

### Gated actions

| Step | Action code | Typical endpoint |
|------|-------------|------------------|
| `murabaha` | `kenya.accept_offer` | `POST /kenya/applications/{id}/accept` |
| `murabaha` | `kenya.create_murabaha` | `POST /kenya/applications/{id}/murabaha` |
| `murabaha` | `application.accept_offer` | `POST /applications/{id}/accept` |
| `liquidation` | `kenya.liquidate` | `POST /kenya/transactions/{id}/liquidate` |
| `liquidation` | `malaysia.sale_leg` | Malaysia sale / full-flow sale |
| `disbursement` | `kenya.complete_settlement` | `POST /kenya/applications/{id}/complete-settlement` |
| `disbursement` | `kenya.disburse` | `POST /kenya/disbursements` |
| `disbursement` | `malaysia.disburse` | `POST /disbursements` |
| `disbursement` | `kenya.run_full_flow` | `POST /kenya/applications/{id}/run-full-flow` |
| `disbursement` | `malaysia.run_full_flow` | Malaysia one-click flow |

Offer generation, eligibility, purchase, possession, and Wakala are **not** checker-gated (Shariah sequencing still applies).

### 202 body

```json
{
  "queued": true,
  "approval_id": "…",
  "id": "…",
  "step": "murabaha",
  "action": "application.accept_offer",
  "status": "pending",
  "amount": "10000.00",
  "currency": "KES",
  "application_id": "…",
  "transaction_id": null,
  "message": "Queued for FI Approver (maker-checker). The initiator cannot be the sole approver."
}
```

The Kenya Ops page shows this message. FI Approver works the queue on **Approvals**.

### Approve / reject

```
GET  /api/v1/ops/approvals?status=pending
POST /api/v1/ops/approvals/{id}/approve    { "note": "optional" }
POST /api/v1/ops/approvals/{id}/reject     { "note": "reason" }
```

Requires `approve_txn` and tenant access.

On approve the engine:

1. Refuses if the caller is the same ops user who queued the item (403/400: cannot self-approve).
2. Refuses if the amount exceeds the effective limit.
3. Runs the stored executor (the original Kenya/Malaysia service call).
4. Marks the row `executed` and writes `approval.executed` to the audit log.

On reject: status `rejected`, no trade execution, audit `approval.rejected`.

Executor failure is stored on `last_error`; the row stays pending so ops can retry after the underlying issue is fixed.

### Amount limits

Effective cap = `min(institution.approval_limit_amount, approver.approval_limit_amount)` among the values that are set. If neither is set, there is no amount cap.

Set the institution cap on **Institutions**. Set a per-approver cap on **Users** (`approval_limit_amount`).

### Recommended FI pattern

| Role | Does |
|------|------|
| FI Ops | Runs Kenya/Malaysia desks; checker steps return 202 |
| FI Approver | Opens **Approvals**, authorizes within limit |
| FI Admin | May both initiate and approve, but **cannot approve their own** queued item — a second admin/approver is required |
| BTI Ops | May initiate (queues for the FI) and retry failed legs |
| Super Admin | Cannot initiate or approve trades |

---

## 8. Billing

BTI Finance (and Super Admin) on **Billing**.

Fee for a period:

```
volume  = sum(Disbursement.amount) where disbursed_at ∈ [period_start, period_end)
          and the application belongs to the institution
fee     = round(volume × billing_fee_bps / 10000, 2)
currency = KES
status  = issued → paid
```

```
GET  /api/v1/ops/billing/invoices
POST /api/v1/ops/billing/invoices                 { institution_id, period_start, period_end, note? }
POST /api/v1/ops/billing/invoices/{id}/pay
GET  /api/v1/ops/billing/invoices/export          # also requires export_data
```

Finance cannot execute trades. Super Admin can generate invoices but still cannot run desks.

---

## 9. Reconciliation

Reconciler (tenant-scoped or BTI-wide if the user has no `institution_id`) on **Reconciliation**.

Scan walks commodity transactions (cap 2000) and compares:

- **expected** = application `amount_requested`
- **settled** = sum of that application’s disbursements

| Status | Meaning |
|--------|---------|
| `outstanding` | Nothing settled yet |
| `matched` | Expected and settled within 0.01 |
| `mismatch` | Settled, but amounts differ |
| `exception` | Officer-marked; later scans do not overwrite |

```
POST /api/v1/ops/reconciliation/scan
GET  /api/v1/ops/reconciliation?status=
POST /api/v1/ops/reconciliation/{id}/resolve      { status, note? }
GET  /api/v1/ops/reconciliation/export            # also requires export_data
```

Resolve statuses: `matched` | `exception` | `outstanding`. Resolution writes an audit note.

---

## 10. Exports (permission `export_data`)

| Export | Path | Typical roles |
|--------|------|----------------|
| Operational audit CSV | `GET /api/v1/audit/export` | Super Admin, BTI Ops, FI Admin, Shariah, Reconciler, Finance |
| Shariah pack | `GET /api/v1/kenya/shariah-audit/export` | Super Admin, BTI Ops, Shariah, FI Admin |
| Billing CSV | `GET /api/v1/ops/billing/invoices/export` | Super Admin, Finance |
| Recon CSV | `GET /api/v1/ops/reconciliation/export` | Super Admin, Reconciler |

Roles without `export_data` (FI Ops, FI Approver, Read-only, Dealer) cannot download these packs.

---

## 11. Exception retries (`write_bti_ops`)

| Path | Effect |
|------|--------|
| `POST /api/v1/kenya/ops/cases/{application_id}/retry` | Reset failed Kenya legs for retry |
| `POST /api/v1/manual-bridge/transactions/{transaction_id}/retry` | Reset failed Malaysia manual-bridge legs; failed txn → `awaiting_manual` |

Both write `bti.retry` (or equivalent) to the audit log. Super Admin and BTI Ops hold this permission. Kenya Ops shows **Retry failed legs** only when the session has `write_bti_ops`.

Retries do not skip Shariah sequencing (possession before Murabaha, Wakala before liquidation, No-Inah independent sale).

---

## 12. Portal map

Nav is permission-based. Super Admin does **not** see every write desk.

| Page | Permission / roles | Who |
|------|-------------------|-----|
| `/institutions` | `manage_institutions` | Super Admin |
| `/users` | `manage_credentials` | Super Admin, FI Admin |
| `/integrations` | `manage_integrations` | Super Admin, FI Admin |
| `/webhooks` | `manage_credentials` | Super Admin, FI Admin |
| `/kenya` | `write_ops` | BTI Ops, FI Admin, FI Ops |
| `/malaysia` | `write_ops` | BTI Ops, FI Admin, FI Ops |
| `/approvals` | `approve_txn` | FI Approver, FI Admin |
| `/mobile-lend` | listed roles | BTI Ops, FI Admin, FI Ops, FI Approver (no Super Admin) |
| `/billing` | `manage_billing` | Super Admin, Finance |
| `/reconciliation` | `reconcile` | Super Admin, Reconciler |
| `/shariah` | `view_shariah` | Super Admin, BTI Ops, FI Admin, Shariah |
| `/mfa-enroll` | session | Privileged roles |
| `/agent-dealers` | dealer desk | Agent dealer (ops can view; only dealer tops up) |

---

## 13. Data model

Alembic revision **`011_controls_billing_mfa`**. SQLite `init_db` also ALTERs missing columns.

**`institutions`:** `active`, `approval_steps`, `approval_limit_amount`, `billing_fee_bps`

**`ops_users`:** `approval_limit_amount`, `mfa_secret`, `mfa_enabled`

**`pending_approvals`:** queued maker-checker items (`pending` / `executed` / `rejected`)

**`billing_invoices`:** usage invoices (`issued` / `paid`)

**`reconciliation_items`:** one row per commodity transaction (unique `transaction_id`)

Deleting an institution cleans these control tables.

---

## 14. Environment

```env
AUTH_ENABLED=true
API_KEY_HEADER=X-API-Key
OPS_SESSION_SECRET=replace-with-long-random-string
OPS_BOOTSTRAP_ADMIN_EMAIL=admin@buruujfintech.com
OPS_BOOTSTRAP_ADMIN_PASSWORD=…          # first login must change this
OPS_SEED_USERS=true
OPS_SEED_PASSWORD=…                     # temporary; written to data/ops_seed_credentials.txt
OPS_SEED_EMAIL_DOMAIN=buruujfintech.com
```

Seed emails (domain = `OPS_SEED_EMAIL_DOMAIN`):

| Email | Role |
|-------|------|
| `OPS_BOOTSTRAP_ADMIN_EMAIL` | `platform_admin` |
| `bti.ops@…` | `bti_ops` |
| `bti.finance@…` | `bti_finance` |
| `fi.admin@…` | `institution_admin` (default tenant) |
| `fi.ops@…` | `institution_ops` |
| `fi.approver@…` | `fi_approver` |
| `shariah@…` | `shariah_officer` |
| `reconciler@…` | `reconciler` (BTI-wide) |
| `fi.reconciler@…` | `reconciler` (tenant) |
| `readonly@…` | `read_only` |
| `dealer@…` | `agent_dealer` |
| `seed-api-client` key | `api_client` |

Re-seed anytime: `python -m tawarruq.cli seed-ops-users`. Existing emails are left untouched.

---

## 15. Operator runbooks

### First production day

1. `alembic upgrade head` (must include `011`).
2. Confirm `AUTH_ENABLED=true` and a strong `OPS_SESSION_SECRET`.
3. Sign in as Super Admin → change password → enroll TOTP at `/mfa-enroll`.
4. Rotate seed passwords for BTI Ops, Finance, and the default FI users (or disable unused seeds).
5. On each live FI: set `approval_steps`, `approval_limit_amount`, `billing_fee_bps`.
6. Invite the FI Admin under **Users**. That FI Admin then invites FI Ops and FI Approver (and optional amount cap). Super Admin does not create FI desk staff.
7. Super Admin issues an `api_client` key on **Webhooks** if the FI submits trades over API.

### FI Ops runs a Kenya deal

1. Kenya Ops workbench, steps 1–3 (apply, purchase, possession) execute immediately.
2. Accept / Murabaha / liquidate / disburse return **202** if those steps are in `approval_steps`.
3. FI Approver opens **Approvals**, confirms amount ≤ limit, approves.
4. If the executor fails, `last_error` is on the queue item; BTI Ops may **Retry failed legs**.

### Suspend a tenant

Institutions → uncheck active (or `PATCH { "active": false }`). Ops users bound to that institution cannot write. Super Admin unsuspends with the same PATCH.

### Month-end billing

Finance → **Billing** → pick institution and period → generate invoice → mark paid when cash is received → optional CSV export.

### Settlement close

Reconciler → **Scan trades vs settlement** → filter mismatch/outstanding → resolve with a note → export CSV.

---

## 16. Tests

```powershell
cd bti-tawarruq-engine
$env:PYTHONPATH="src"
python -m pytest tests/test_controls.py tests/test_rbac.py tests/test_ops_login.py tests/test_invite_matrix.py tests/test_auth_scope.py tests/test_kenya_flow.py tests/test_api.py -q
```

`tests/test_controls.py` covers: Super Admin cannot create applications; queue + self-approve blocked; amount cap; tenant suspend; billing + recon; BTI ops retry; TOTP round-trip.

`tests/test_invite_matrix.py` and `tests/test_ops_login.py` cover who may invite whom: Super Admin invites FI Admin then FI Admin invites FI Ops; Super Admin cannot invite FI Ops or FI Approver; FI Admin cannot invite BTI roles or create API keys; FI Ops cannot invite anyone.

Maker-checker tests turn `AUTH_ENABLED=true`. Kenya/Malaysia mock flows keep it false so they execute immediately.

---

## 17. Source map

| Area | Files |
|------|--------|
| Roles / permissions | `src/tawarruq/services/rbac.py`, `src/tawarruq/enums.py` |
| Auth middleware | `src/tawarruq/api/middleware.py` |
| Maker-checker | `src/tawarruq/services/approval_service.py`, `src/tawarruq/api/approval_http.py` |
| Billing | `src/tawarruq/services/billing_service.py` |
| Reconciliation | `src/tawarruq/services/reconciliation_service.py` |
| TOTP | `src/tawarruq/services/totp_service.py` |
| HTTP | `src/tawarruq/api/routes_controls.py`, `routes_ops.py`, `routes_extended.py` (API keys Super Admin only) |
| OpenAPI / Swagger | `src/tawarruq/api/openapi_metadata.py` — invite rules and Super Admin key create |
| Models | `src/tawarruq/models/controls.py`, `institution.py`, `ops_user.py` |
| Migration | `alembic/versions/011_controls_billing_mfa.py` |
| Portal | `portal/src/config/roles.ts`, `UsersPage`, `WebhooksPage`, `navigation.ts`, pages `ApprovalsPage`, `BillingPage`, `ReconciliationPage`, `MfaEnrollPage`, `LoginPage` |
| Catalogue generator | `scripts/build_users_doc.py` |

---

## 18. Intentionally not in this release

| Item | Reason |
|------|--------|
| Product / branch approval limits | Amount limits are live; product and branch dimensions wait on each FI’s policy |
| End-customer BTI portal accounts | Out of scope — FI channels only |
| API middleware hard-lock until privileged MFA enroll | Would lock bootstrap admin; portal still prompts `/mfa-enroll` |
| Super Admin trade execution | Deliberate segregation of duties |

---

## 19. Related docs

- [KENYA_FLOW.md](KENYA_FLOW.md) — eight-step Kenya journey
- [MALAYSIA_FLOW.md](MALAYSIA_FLOW.md) — BSAS legs
- [SHARIAH_AUDIT.md](SHARIAH_AUDIT.md) — append-only ledger
- [PRODUCTION_OPS.md](PRODUCTION_OPS.md) — monitoring, Prometheus, CI/CD
- [LOCAL_TEST.md](LOCAL_TEST.md) — local Swagger walkthrough
- [INTEGRATIONS.md](../INTEGRATIONS.md) — Daraja / MNO / broker credentials
