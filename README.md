# Buruuj Tawarruq Engine

Multi-tenant **Tawarruq-as-a-Service** for Buruuj Fintech. One engine and one ops portal serve banks, SACCOs, and MFIs:

- **Kenya** — MNO float / airtime Tawarruq (eight sealed steps)
- **Malaysia** — BSAS / Eiger commodity Murabaha (mock, manual bridge, or live)
- **Sedania AS SIDQ** — bank financing (wakeel + muqassah + CASA, or Rasul, or physical delivery)
- **SACCO execute** — inbound CBS facility; Buruuj trades and returns certificates; the SACCO pays the member

Plus **Amanah** orchestration, append-only Shariah audit, maker-checker, billing, reconciliation, and the **Buruuj Lend** mobile app.

Public surfaces: ops portal (`ops.buruujfintech.com` / local `:5173`), API (`api.buruujfintech.com` / local `:8000`). End customers are **not** portal users — they stay on FI channels and the customer journey APIs.

## What is implemented

| Area | Status |
|------|--------|
| **Kenya float Tawarruq** | Eight-step flow: apply → purchase → possession → Murabaha → Wakala → independent sale → clear → pay / repay |
| **Malaysia Tawarruq** | 3-leg BSAS / Eiger (`mock` / `manual_bridge` / `live`), desk packets, e-certificate paste |
| **Sedania AS SIDQ** | Approved wakeel + muqassah + CASA, AAOIFI Rasul, or physical delivery (`qabd hakiki`) |
| **SACCO execute** | `POST /tawarruq/execute` + HMAC; vaulted certificates; webhook `tawarruq.certificates_ready` |
| **No-Inah guardrail** | Blocks financier self-liquidation and originating MNO pool buybacks |
| **Shariah audit** | Append-only hash chain, ORM immutability, optional Python mirror, CSV / pack export |
| **Live integrations** | M-Pesa Daraja (B2C + STK), Safaricom / Airtel airtime, Airtel Money, broker OTC |
| **Multi-tenant** | Institutions, per-tenant credentials, webhooks, Super Admin–issued API keys |
| **Users & controls** | RBAC, who-may-invite rules, maker-checker, amount limits, tenant suspend, TOTP, invoices, recon |
| **Ops portal** | Role-aware nav: desks, Users, Webhooks, Approvals, Billing, Reconciliation, MFA |
| **Amanah worker** | Auto-advances Kenya / Malaysia legs after eligibility or offer acceptance |
| **Expo mobile** | Buruuj Lend (`mobile/`) — email MFA, FI invite / approve, customer journey |
| **Tests** | pytest: flows, Shariah, No-Inah, RBAC, invites, maker-checker, billing, auth |

## Architecture

```
[Expo Mobile App] ──► [Tawarruq Engine API :8000] ◄── [Ops portal :5173]
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
    [Amanah Worker]    [MNO / M-Pesa / Broker]   [Shariah Audit :8001]
         │                    │                    │
    Leg orchestration    Live partner APIs     Append-only ledger mirror
```

Auth when `AUTH_ENABLED=true`:

| Identity | How it authenticates |
|----------|----------------------|
| Portal human | Email + password → `Authorization: Bearer` session. Privileged roles enroll TOTP. |
| Machine client | `X-API-Key` (prefer role `api_client`) |
| SACCO execute | API key + `X-BTI-Timestamp` + `X-BTI-Signature` (HMAC) |
| Partner callback | `X-Callback-Token` when configured (Daraja / MNO) |

Local lab can set `AUTH_ENABLED=false` so unauthenticated mock flows still run. **Production must set `AUTH_ENABLED=true`.**

## Users, invites, and API keys

Only **Super Admin** (`platform_admin`) and **FI Admin** (`institution_admin`) may invite portal users. The same map applies to `PATCH` role. Extra engine roles (`read_only`, `agent_dealer`) stay off the invite form. FI API Client is a machine identity, not a portal invite.

| Caller | May invite | Must not invite |
|--------|------------|-----------------|
| Super Admin | Super Admin, BTI Ops, BTI Finance, FI Admin, FI Operations, FI Approver, Shariah / Audit, Reconciliation | Read only, Agent dealer, API client |
| FI Admin (own tenant) | FI Admin, FI Ops, FI Approver, Shariah, Recon | Super Admin, BTI Ops, BTI Finance |
| Everyone else | — | Anyone |

| Role | Engine code | Typical home |
|------|-------------|--------------|
| BTI Super Admin | `platform_admin` | Institutions (no trade execution) |
| BTI Operations | `bti_ops` | Kenya / Malaysia / Ops Monitor |
| BTI Finance | `bti_finance` | Billing |
| FI Administrator | `institution_admin` | Dashboard, Users |
| FI Operations | `institution_ops` | Kenya / Malaysia desks |
| FI Approver | `fi_approver` | Approvals |
| Shariah / Audit | `shariah_officer` | Shariah |
| Reconciliation | `reconciler` | Reconciliation |
| Agent dealer | `agent_dealer` | Float desk only |
| Institution API Client | `api_client` | Machine key — not a portal login |

**API keys:** Super Admin only, on **Webhooks** (`POST /api/v1/institutions/{id}/api-keys`). Prefer `api_client`. FI Admin cannot create keys — request BTI to onboard. Copy the key and HMAC secret once.

**Invite flow:** `POST /api/v1/ops/auth/users` generates a temporary password, emails it when `SMTP_HOST` is set, and forces a change on first login. Super Admin must send `institution_id` when inviting a tenant role.

Full catalogue: [docs/USERS_ACCESS_CONTROLS.md](docs/USERS_ACCESS_CONTROLS.md) and [docs/BTI_Tawarruq_Users_ver_001.docx](docs/BTI_Tawarruq_Users_ver_001.docx).

### Seeded test logins

When `OPS_SEED_USERS=true` (default), missing catalogue users are created. Existing emails are never overwritten. Secrets for **new** accounts go to `data/ops_seed_credentials.txt` (gitignored).

| Email (domain = `OPS_SEED_EMAIL_DOMAIN`) | Role |
|------------------------------------------|------|
| `OPS_BOOTSTRAP_ADMIN_EMAIL` | Super Admin |
| `bti.ops@…` | BTI Ops |
| `bti.finance@…` | BTI Finance |
| `fi.admin@…` | FI Admin (default tenant) |
| `fi.ops@…` / `fi.approver@…` | FI Ops / FI Approver |
| `shariah@…` / `reconciler@…` | Shariah / Recon |

First login must change the temporary password. Super Admin, BTI Ops, and BTI Finance should enroll TOTP at `/mfa-enroll`.

## Maker-checker

When `AUTH_ENABLED=true`, Murabaha, liquidation, and disbursement can queue for an FI Approver (`202`) instead of executing immediately. The initiator cannot approve their own item. Amount cap is `min(institution limit, approver limit)` when both are set.

Immediate execution when auth is off, the caller is `api_client` or a mobile session, or the step is omitted from `institution.approval_steps`.

Portal: FI Ops runs the desk; FI Approver works **Approvals**. Super Admin cannot initiate or approve trades.

## Product flows

### Kenya (eight steps)

Possession **must** be sealed before Murabaha. Wakala **must** be recorded before liquidation. No-Inah blocks sale back to the financier or originating MNO pool.

1. Apply and eligibility — `POST /kenya/customers`, `.../applications`, `.../eligibility`
2. Float purchase (Leg 1) — MNO or Agent Dealer
3. Constructive possession
4. Murabahah: offer, accept, contract, sign, Leg 2 transfer
5. Wakala
6. Independent spot sale (Leg 3)
7. Clearing
8. Wallet disbursement and repayments

Mock one-click: `POST /kenya/applications/{id}/run-full-flow` when `KENYA_INTEGRATION_MODE=mock`. Customer tracker: `GET /customer/applications/{ref}/journey`. See [docs/KENYA_FLOW.md](docs/KENYA_FLOW.md).

### Sedania bank financing (AS SIDQ)

Portal: **Sedania Financing**. The bank buys telecommunication airtime. SASC is appointed independently. The bank credits CASA. Buruuj is the rail, not the wakeel.

| Variant | `flow_variant` | After the independent sale |
|---------|----------------|----------------------------|
| Approved | `approved_wakeel` | Muqassah, then CASA |
| AAOIFI | `aaoifi_rasul` | CASA (no muqassah) |

`delivery_mode=physical` keeps the commodity with the customer; after full settlement SASC arranges `qabd hakiki`. Documents: Purchase Order, Commodity Invoice, Delivery Order, Trading e-Cert. See [docs/SEDANIA_FINANCING.md](docs/SEDANIA_FINANCING.md).

### SACCO execute

`POST /api/v1/tawarruq/execute` (`customer_id`, `amount`, `tenor`) signed with API key + HMAC. Buruuj stamps Wa'd / Wakalah, trades on AS SIDQ, vaults certificates for 7 years, and webhooks `tawarruq.certificates_ready`. **Buruuj never pays SACCO principal.** See [docs/SACCO_EXECUTE.md](docs/SACCO_EXECUTE.md).

HMAC: `X-BTI-Signature` = `HMAC-SHA256(hmac_secret, "{timestamp}.{raw_body}")` with `X-BTI-Timestamp` (unix seconds).

### Malaysia (BSAS / Eiger)

| Mode | Use |
|------|-----|
| `mock` | Local / CI — `POST /malaysia/applications/{id}/run-full-flow` |
| `manual_bridge` | Pre-live Suq Al-Sila' — desk packet + paste e-certificate |
| `live` + `MALAYSIA_COMMODITY_DESK=bsas\|eiger` | After partner connectivity |

See [docs/MALAYSIA_FLOW.md](docs/MALAYSIA_FLOW.md).

## Ops portal

```powershell
cd portal
npm install
npm run dev
```

Vite proxies `/api` to `http://127.0.0.1:8000`. Nav is permission-based.

| Page | Who |
|------|-----|
| `/institutions` | Super Admin — tenants, suspend, approval steps, fee bps |
| `/users` | Super Admin, FI Admin — invites (filtered by caller) |
| `/webhooks` | Super Admin issues keys; FI Admin registers callbacks and requests BTI for a key |
| `/integrations` | Super Admin, FI Admin — Daraja / MNO secrets |
| `/kenya` `/malaysia` `/sedania` | BTI Ops, FI Admin, FI Ops |
| `/approvals` | FI Approver, FI Admin |
| `/billing` | Super Admin, BTI Finance |
| `/reconciliation` | Super Admin, Reconciler |
| `/shariah` | Super Admin, BTI Ops, FI Admin, Shariah |
| `/agent-dealers` | Agent dealer (ops can view; only the dealer tops up) |

## Quick start

### Local (SQLite)

```powershell
cd bti-tawarruq-engine
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
# KENYA_INTEGRATION_MODE=mock
# AUTH_ENABLED=true   # required to test invites and keys

python -m tawarruq.cli init-db
python -m tawarruq.cli serve --reload
```

| Service | URL |
|---------|-----|
| Swagger | http://localhost:8000/docs |
| ReDoc | http://localhost:8000/redoc |
| Health | http://localhost:8000/health |
| Ops portal | http://localhost:5173 |
| Shariah audit (optional) | http://localhost:8001/health |

### Swagger testing (`AUTH_ENABLED=true`)

1. Open http://localhost:8000/docs
2. **Production Ops → `POST /ops/auth/login`** (bootstrap email / password from `.env`)
3. If `must_change_password`, call **`POST /ops/auth/change-password`**, then copy the new `access_token`
4. **Authorize → BearerAuth** — paste the token only (no `Bearer ` prefix)
5. `GET /institutions` — copy an `id`
6. Super Admin: `POST /ops/auth/users` with `role: institution_admin` and that `institution_id`. Super Admin may also invite `institution_ops` / `fi_approver`
7. Log in as that FI Admin, Authorize, invite `institution_ops` or `fi_approver`. FI Admin inviting `bti_ops` must 403
8. Super Admin: `POST /institutions/{id}/api-keys` with `role: api_client`. The same call as FI Admin must 403

Step-by-step: [docs/LOCAL_TEST.md](docs/LOCAL_TEST.md). Live script: `powershell -File scripts/live_invite_check.ps1`.

### Docker Compose (PostgreSQL)

```powershell
docker compose up --build
```

API `:8000`, Postgres `:5432`, Shariah audit `:8001`, portal image on `:15173`. For local portal against compose API, run `npm run dev` in `portal/` (proxies to `:8000`).

Set `AUTH_ENABLED=true` in compose. Alembic through `011` (controls, billing, MFA). SQLite `init_db` also adds missing columns; Postgres datetime columns use `TIMESTAMP`.

### Mobile

```powershell
cd mobile
npm install
$env:EXPO_PUBLIC_API_URL="http://<your-lan-ip>:8000/api/v1"
npx expo start
```

Engine must listen on `0.0.0.0`. See [mobile/README.md](mobile/README.md). Smoke: `python scripts/test_mobile_api_flow.py`.

## Key API surfaces

Prefix all paths with `/api/v1`.

### Auth and users

| Method | Path | Notes |
|--------|------|-------|
| POST | `/ops/auth/login` | `{ email, password }` → `access_token` |
| POST | `/ops/auth/change-password` | Required when `must_change_password` |
| POST | `/ops/auth/mfa` / `/mfa/enroll` / `/mfa/confirm` | Privileged TOTP |
| GET | `/ops/auth/me` | Role and permissions |
| GET/POST | `/ops/auth/users` | Invite — Super Admin / FI Admin only |
| PATCH | `/ops/auth/users/{id}` | Role change uses the same invite rules |
| POST | `/institutions/{id}/api-keys` | Super Admin only |

### Kenya

| Method | Path | Step |
|--------|------|------|
| POST | `/kenya/customers` | Register |
| POST | `/kenya/applications` | Financing request |
| POST | `/kenya/applications/{id}/eligibility` | Eligibility |
| POST | `/kenya/transactions` then `.../purchase` | Leg 1 |
| POST | `/kenya/transactions/{id}/possession` | Possession |
| POST | `/kenya/applications/{id}/offer` → `.../accept` → `.../murabaha` | Murabaha |
| POST | `/kenya/applications/{id}/wakala` | Wakala |
| POST | `/kenya/transactions/{id}/liquidate` | Leg 3 |
| POST | `/kenya/applications/{id}/complete-settlement` | Clear + pay |
| POST | `/kenya/applications/{id}/run-full-flow` | Mock demo |
| GET | `/kenya/shariah-audit/export` | Regulatory pack |

### Sedania / SACCO

| Method | Path | Notes |
|--------|------|-------|
| POST | `/sedania/financing` | Bank CMP on AS SIDQ |
| GET | `/sedania/financing/{id}/documents/{kind}` | Trade pack |
| POST | `/sedania/financing/{id}/settle` | Then optional `.../physical-delivery` |
| POST | `/tawarruq/execute` | SACCO inbound (HMAC) |
| GET | `/tawarruq/certificates/{id}` | Vaulted certificate |

### Malaysia

| Method | Path | Notes |
|--------|------|-------|
| POST | `/applications` → `.../offer` → `.../accept` | Application |
| POST | `/transactions` | `mode`: mock / manual_bridge / live |
| POST | `/transactions/{id}/legs/{purchase\|transfer\|sale}` | Legs |
| POST | `/malaysia/applications/{id}/run-full-flow` | Mock E2E |
| POST | `/manual-bridge/transactions/{id}/advance` | Desk packet |

### Controls

| Method | Path | Notes |
|--------|------|-------|
| PUT | `/institutions/{id}/integrations` | Daraja / MNO secrets |
| POST | `/webhooks` | Outbound callbacks |
| GET/POST | `/ops/approvals` | Maker-checker |
| GET/POST | `/ops/billing/invoices` | Usage invoices |
| GET/POST | `/ops/reconciliation` | Settlement match |
| GET | `/audit/export` | Operational CSV (`export_data`) |
| GET | `/health` | Flags including `auth_enabled`, `database_ok` |
| GET | `/metrics` | Prometheus (public scrape) |

## Configuration

Copy `.env.example` to `.env`.

| Variable | Purpose |
|----------|---------|
| `AUTH_ENABLED` | Enforce RBAC. Production: `true` |
| `OPS_SESSION_SECRET` | Sign portal sessions |
| `OPS_BOOTSTRAP_ADMIN_EMAIL` / `_PASSWORD` | First Super Admin |
| `OPS_SEED_USERS` / `OPS_SEED_PASSWORD` / `OPS_SEED_EMAIL_DOMAIN` | Catalogue seed |
| `SMTP_HOST` / `SMTP_FROM` | Invite email |
| `KENYA_INTEGRATION_MODE` | `mock` or `live` |
| `DATABASE_URL` | SQLite default; PostgreSQL in production |
| `PUBLIC_API_BASE_URL` | Per-institution callback URLs |
| `SHARIAH_AUDIT_SERVICE_URL` | Optional audit mirror |
| `MALAYSIA_COMMODITY_DESK` | `bsas` or `eiger` when live |
| `INTEGRATION_ENCRYPTION_KEY` | Encrypt partner secrets at rest |

Partner keys (Daraja, MNO, Airtel, broker): [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md).

## Tests

```powershell
$env:PYTHONPATH="src"
python -m pytest tests/test_invite_matrix.py tests/test_ops_login.py tests/test_rbac.py tests/test_controls.py -q
pytest -v
```

Mock Kenya mode; Shariah mirror is disabled in `tests/conftest.py`. Demo with the API running: `python scripts/demo_flow.py`.

## Project layout

```
bti-tawarruq-engine/
├── src/tawarruq/           # FastAPI engine + services
│   ├── api/                # Routes, OpenAPI, middleware
│   ├── amanah/             # Background worker
│   ├── integrations/       # Daraja, MNO, Airtel, broker, Sedania
│   └── services/           # RBAC, invites, flows, billing, recon
├── portal/                 # Vite ops portal
│   ├── public/brand/       # Logo (served at /brand/…)
│   └── src/styles/         # Single CSS entry (index.css)
├── mobile/                 # Expo Buruuj Lend
│   └── assets/             # App icons / splash only
├── shariah-audit-service/  # Append-only ledger mirror
├── alembic/                # Migrations
├── tests/                  # pytest
├── docs/                   # Flow, access, integrations guides
├── scripts/                # Demo, seed docx, live invite check
└── data/                   # Local runtime only (gitignored except .gitkeep)
```

## Documentation

| Doc | Contents |
|-----|----------|
| [docs/USERS_ACCESS_CONTROLS.md](docs/USERS_ACCESS_CONTROLS.md) | Roles, invites, keys, maker-checker, billing, recon, MFA |
| [docs/BTI_Tawarruq_Users_ver_001.docx](docs/BTI_Tawarruq_Users_ver_001.docx) | Stakeholder catalogue (`python scripts/build_users_doc.py`) |
| [docs/KENYA_FLOW.md](docs/KENYA_FLOW.md) | Kenya eight steps, No-Inah, mobile mapping |
| [docs/MALAYSIA_FLOW.md](docs/MALAYSIA_FLOW.md) | BSAS / Eiger modes |
| [docs/SEDANIA_FINANCING.md](docs/SEDANIA_FINANCING.md) | Bank CASA / physical delivery |
| [docs/SACCO_EXECUTE.md](docs/SACCO_EXECUTE.md) | Inbound CBS execute |
| [docs/SHARIAH_AUDIT.md](docs/SHARIAH_AUDIT.md) | Ledger, hash chain, export |
| [docs/LOCAL_TEST.md](docs/LOCAL_TEST.md) | Swagger walkthrough, Kenya / Malaysia / invites |
| [docs/PRODUCTION_OPS.md](docs/PRODUCTION_OPS.md) | Seed emails, monitoring, CI/CD |
| [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) | Daraja / MNO / broker credentials |

## License

Proprietary — Buruuj Fintech.
