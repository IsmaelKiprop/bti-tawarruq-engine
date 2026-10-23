# Buruuj Tawarruq Engine

Multi-tenant **Tawarruq-as-a-Service** platform for Buruuj Fintech: Malaysia BSAS commodity flows, Kenya MNO airtime/float financing, **Amanah** AI orchestration, Shariah-compliant audit logging, and customer-facing mobile apps.

## What is implemented

| Area | Status |
|------|--------|
| **Malaysia Tawarruq** | 3-leg BSAS flow (mock / manual_bridge / live), business steps 7–12, Shariah audit |
| **Sedania AS SIDQ financing** | Approved wakeel + muqassah + CASA, AAOIFI Rasul, or physical delivery (qabd hakiki) |
| **Kenya float Tawarruq** | Eight-step flow: apply → purchase → possession → Murabaha → Wakala → independent sale → clear → pay / repay |
| **No-Inah guardrail** | Blocks financier self-liquidation and originating MNO pool buybacks |
| **Shariah audit ledger** | Append-only hash chain, ORM immutability, Python microservice + regulatory export |
| **Live integrations** | M-Pesa (Daraja B2C/STK), Safaricom/Airtel airtime, Airtel Money disbursement, broker OTC API |
| **Multi-tenant** | Per-institution credentials, API keys, webhooks, integration profiles |
| **Amanah worker** | Auto-advances Kenya/Malaysia legs after eligibility or offer acceptance |
| **Ops portal** | Dashboard, Sedania/Kenya/Malaysia desks, Users, Approvals, Billing, Reconciliation, MFA |
| **Users & controls** | Catalogue RBAC, maker-checker, amount limits, tenant suspend, TOTP, usage invoices |
| **Expo mobile app** | Timiza-style Shariah lending app (`mobile/` · Buruuj Lend) |
| **Tests** | pytest: Kenya/Malaysia flows, Shariah, No-Inah, RBAC, maker-checker, billing, auth |

## Architecture overview

```
[Expo Mobile App] ──► [Tawarruq Engine API :8000]
                              │
         ┌────────────────────┼────────────────────┐
         │                    │                    │
    [Amanah Worker]    [MNO / M-Pesa / Broker]   [Shariah Audit Service :8001]
         │                    │                    │
    Leg orchestration    Live partner APIs     Append-only ledger mirror
```

### Sedania bank financing (AS SIDQ)

Matches the BTI Advisory deck. Portal: **Sedania Financing**. API: `POST /sedania/financing`.

1. Customer signs the financing contract and enters the CMP
2. Customer may appoint SEDANIA As Salam Capital independently as wakeel (approved) or Rasul (AAOIFI)
3. Bank purchases telecommunication airtime on AS SIDQ (Purchase Order, Commodity Invoice)
4. Qabd hukmi via Delivery Order
5. Murabahah deferred sale and Trading e-Cert
6. SASC sells to random purchasers, unless the customer keeps the commodity
7. Approved flow only: muqassah set-off
8. Bank credits CASA, or SASC arranges physical delivery after full settlement

See [docs/SEDANIA_FINANCING.md](docs/SEDANIA_FINANCING.md).

### Kenya flow (canonical 8 steps)

The customer tracker, Kenya Ops, and Swagger all use this order. Possession **must** be sealed before Murabaha. Wakala **must** be recorded before liquidation.

1. Facility application and eligibility (`POST /kenya/customers`, `.../applications`, `.../eligibility`)
2. Float purchase, Leg 1 (`POST /kenya/transactions` then `.../purchase` or `.../agent-dealer-purchase`)
3. Constructive possession (`POST /kenya/transactions/{id}/possession`)
4. Murabahah deferred sale: offer, accept, contract, sign, Leg 2 transfer
5. Agency activation / Wakala (`POST /kenya/applications/{id}/wakala`)
6. Spot sale to an independent broker, No-Inah enforced (`POST .../liquidate`)
7. Clearing and settlement (`POST .../complete-settlement`)
8. Wallet disbursement and repayments (`POST /kenya/disbursements`, `POST /kenya/repayments/{id}/collect`)

See [docs/KENYA_FLOW.md](docs/KENYA_FLOW.md) for API and mobile mapping. Swagger: `http://localhost:8000/docs`.

### Shariah audit

Immutable append-only ledger with SHA-256 payload hashes and hash-chain tamper detection. State machine blocks phase skips (e.g. liquidation without sealed possession).

- In-process ledger + ORM guards (no UPDATE/DELETE on audit rows)
- Optional mirror to **Python** microservice: `shariah-audit-service/app.py`
- Export: `GET /api/v1/kenya/shariah-audit/export?format=csv|json`

See [docs/SHARIAH_AUDIT.md](docs/SHARIAH_AUDIT.md).

## Quick start

### Local development (SQLite)

```powershell
cd bti-tawarruq-engine
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
# For local dev without partner credentials:
#   KENYA_INTEGRATION_MODE=mock

python -m tawarruq.cli init-db
python -m tawarruq.cli serve --reload
```

| Service | URL |
|---------|-----|
| Swagger | http://localhost:8000/docs |
| Health | http://localhost:8000/health |
| Ops portal | http://localhost:5173 (see below) |
| Shariah audit service | http://localhost:8001/health (optional) |

### Ops portal

```powershell
cd portal
npm install
npm run dev
```

Kenya demo: open **Kenya MNO Flow** — runs eligibility → full mock flow when `KENYA_INTEGRATION_MODE=mock`.

### Expo mobile app

```powershell
cd mobile
npm install

# Discover LAN IP: ipconfig  →  IPv4 Address
$env:EXPO_PUBLIC_API_URL="http://<your-lan-ip>:8000/api/v1"
npx expo start
```

Engine must listen on all interfaces for a physical device:

```powershell
python -m tawarruq.cli serve --host 0.0.0.0 --port 8000
```

In the app: **Settings** → paste the LAN URL → **Test** → **Get financing**.

See [mobile/README.md](mobile/README.md). Smoke-test without a phone:

```powershell
python scripts/test_mobile_api_flow.py
```

### Docker Compose (PostgreSQL + Shariah service)

```powershell
docker compose up --build
```

Runs: Postgres, API (`:8000`), Shariah audit (`:8001`), portal (`:5173`).

### Shariah audit service (standalone)

```powershell
$env:SHARIAH_AUDIT_DATABASE_URL="sqlite:///./data/shariah_audit.db"
python shariah-audit-service/app.py
```

Set `SHARIAH_AUDIT_SERVICE_URL=http://localhost:8001` in `.env` so the engine mirrors audit entries.

## Key API surfaces

### Malaysia (BSAS)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/applications` | Create financing application |
| POST | `/api/v1/applications/{id}/offer` | Generate offer |
| POST | `/api/v1/applications/{id}/accept` | Accept offer |
| POST | `/api/v1/transactions` | Start 3-leg transaction (`mode`: mock / manual_bridge / live) |
| POST | `/api/v1/transactions/{id}/legs/{purchase\|transfer\|sale}` | Execute leg |
| GET | `/api/v1/applications/{id}/shariah-audit` | Shariah trail |

### Kenya MNO

| Method | Path | Step |
|--------|------|------|
| POST | `/api/v1/kenya/customers` | Register customer |
| POST | `/api/v1/kenya/applications` | Financing request |
| POST | `/api/v1/kenya/applications/{id}/eligibility` | Eligibility check |
| POST | `/api/v1/kenya/transactions` | Start MNO transaction |
| POST | `/api/v1/kenya/transactions/{id}/purchase` | Leg 1 purchase |
| POST | `/api/v1/kenya/transactions/{id}/possession` | Verify possession |
| GET | `/api/v1/kenya/applications/{id}/offer` | Offer summary |
| POST | `/api/v1/kenya/applications/{id}/offer` | Generate offer |
| POST | `/api/v1/kenya/applications/{id}/accept` | Accept offer |
| POST | `/api/v1/kenya/applications/{id}/murabaha` | Create contract |
| POST | `/api/v1/kenya/applications/{id}/murabaha/sign` | Customer signature |
| POST | `/api/v1/kenya/transactions/{id}/transfer` | Leg 2 transfer |
| POST | `/api/v1/kenya/applications/{id}/wakala` | Wakala consent |
| POST | `/api/v1/kenya/transactions/{id}/liquidate` | Leg 3 liquidation |
| POST | `/api/v1/kenya/applications/{id}/complete-settlement` | Liquidate + disburse + schedule |
| GET | `/api/v1/kenya/applications/{id}/repayments` | Repayment schedule |
| POST | `/api/v1/kenya/repayments/{id}/collect` | Collect installment (STK) |
| GET | `/api/v1/kenya/applications/{id}/shariah-audit/verify` | Integrity check |
| GET | `/api/v1/kenya/shariah-audit/export` | Regulatory export |
| POST | `/api/v1/kenya/applications/{id}/run-full-flow` | Mock one-click demo |

### Platform

| Method | Path | Description |
|--------|------|-------------|
| PUT | `/api/v1/institutions/{id}/integrations` | Per-tenant Daraja/MNO credentials |
| POST | `/api/v1/webhooks` | Outbound event webhooks |
| POST | `/api/v1/ops/auth/users` | Invite portal user (Super Admin / FI Admin; role depends on caller) |
| POST | `/api/v1/institutions/{id}/api-keys` | Tenant API keys — Super Admin only (`AUTH_ENABLED=true`) |
| GET | `/api/v1/audit/export` | Operational audit CSV (`export_data`) |
| GET/POST | `/api/v1/ops/approvals` | Maker-checker queue, approve, reject |
| GET/POST | `/api/v1/ops/billing/invoices` | Usage invoices (volume × fee bps) |
| GET/POST | `/api/v1/ops/reconciliation` | Scan trades vs disbursements |

## Project layout

```
bti-tawarruq-engine/
├── src/tawarruq/           # FastAPI engine + services
│   ├── api/                # Route modules (kenya, callbacks, …)
│   ├── amanah/             # Background worker + Kenya orchestrator
│   ├── integrations/       # Daraja, MNO airtime, Airtel Money, broker OTC
│   └── services/           # Flow, Shariah ledger, No-Inah, wallet, …
├── shariah-audit-service/  # Python append-only audit microservice
├── mobile/                 # Expo React Native customer app
├── portal/                 # Vite ops portal
├── alembic/                # DB migrations (through 011 controls/billing/MFA)
├── tests/                  # pytest suite (flows, RBAC, maker-checker)
├── docs/                   # Flow, users/access, and local test guides
├── scripts/                # Demo and smoke scripts
├── assets/                 # Brand assets
└── INTEGRATIONS.md         # Live partner setup guide
```

## Tests

```powershell
pytest -v
```

Tests use `KENYA_INTEGRATION_MODE=mock` and disable the Shariah audit mirror automatically (`tests/conftest.py`).

Optional demo script (API must be running):

```powershell
python scripts/demo_flow.py
```

## Configuration

Copy `.env.example` to `.env`. Important variables:

| Variable | Purpose |
|----------|---------|
| `KENYA_INTEGRATION_MODE` | `mock` (sync dev) or `live` (partner APIs + callbacks) |
| `DATABASE_URL` | SQLite default; use PostgreSQL in production |
| `SHARIAH_AUDIT_SERVICE_URL` | Mirror audit entries to isolated service |
| `BROKER_LIQUIDATION_API_URL` | Independent OTC broker liquidation API |
| `AUTH_ENABLED` | Enforce RBAC (portal sessions + API keys). Production: `true` |
| `PUBLIC_API_BASE_URL` | Build per-institution callback URLs |

Full list: `.env.example` and [INTEGRATIONS.md](INTEGRATIONS.md).

## Documentation

- [docs/USERS_ACCESS_CONTROLS.md](docs/USERS_ACCESS_CONTROLS.md) — Roles, maker-checker, billing, recon, MFA, APIs
- [docs/BTI_Tawarruq_Users_ver_001.docx](docs/BTI_Tawarruq_Users_ver_001.docx) — Stakeholder users catalogue
- [docs/KENYA_FLOW.md](docs/KENYA_FLOW.md) — Kenya eight-step flow, No-Inah, mobile mapping
- [docs/SHARIAH_AUDIT.md](docs/SHARIAH_AUDIT.md) — Ledger, hash chain, export, microservice
- [INTEGRATIONS.md](INTEGRATIONS.md) — Daraja, MNO, Airtel, broker, multi-tenant callbacks
- [docs/PRODUCTION_OPS.md](docs/PRODUCTION_OPS.md) — Seed emails, monitoring, Prometheus, CI/CD deploy
- [docs/LOCAL_TEST.md](docs/LOCAL_TEST.md) — Local run, Swagger walkthrough, mobile, Docker

## License

Proprietary — Buruuj Fintech.
