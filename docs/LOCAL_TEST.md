# Local Run & Test Guide

Step-by-step instructions for running and validating the Buruuj Tawarruq engine on a workstation.

## Prerequisites

- Python 3.11+
- Node.js 18+ (portal and mobile)
- Optional: Docker Desktop (Postgres and the compose stack)

## 1. Engine setup

From the repository root:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
copy .env.example .env
```

Recommended for local dev (add to `.env`):

```env
KENYA_INTEGRATION_MODE=mock
AMANAH_ENABLED=false
SHARIAH_AUDIT_SERVICE_URL=
```

```powershell
python -m tawarruq.cli init-db
python -m tawarruq.cli serve --reload
```

| URL | Purpose |
|-----|---------|
| http://localhost:8000/docs | Swagger UI |
| http://localhost:8000/health | Health and integration flags |
| http://localhost:8000/redoc | ReDoc |

---

## 2. Unit tests

```powershell
pytest -v
```

Uses mock Kenya mode and disables the Shariah mirror (`tests/conftest.py`).

---

## 3. Malaysia flow (Swagger)

| # | Endpoint | Notes |
|---|----------|-------|
| 1 | `POST /api/v1/applications` | Copy `id` |
| 2 | `POST /api/v1/applications/{id}/offer` | Body: `{}` |
| 3 | `POST /api/v1/applications/{id}/accept` | |
| 4 | `POST /api/v1/transactions` | `"mode": "mock"` |
| 5–7 | `POST .../legs/purchase`, `transfer`, `sale` | |
| 8 | `GET /api/v1/applications/{id}/shariah-audit` | Shariah trail |

---

## 4. Kenya MNO flow (Swagger)

Requires `KENYA_INTEGRATION_MODE=mock`.

| # | Endpoint | Phase |
|---|----------|-------|
| 1 | `POST /api/v1/kenya/customers` | Register |
| 2 | `POST /api/v1/kenya/applications` | Financing request |
| 3 | `POST /api/v1/kenya/applications/{id}/eligibility` | Eligibility |
| 4 | `POST /api/v1/kenya/transactions` | Start MNO txn |
| 5 | `POST /api/v1/kenya/transactions/{id}/purchase` | Leg 1 |
| 6 | `POST /api/v1/kenya/transactions/{id}/possession` | If status `awaiting_possession` |
| 7 | `POST /api/v1/kenya/applications/{id}/offer` | Murabaha offer |
| 8 | `POST /api/v1/kenya/applications/{id}/accept` | Accept |
| 9 | `POST /api/v1/kenya/applications/{id}/murabaha` | Contract |
| 10 | `POST /api/v1/kenya/applications/{id}/murabaha/sign` | Sign |
| 11 | `POST /api/v1/kenya/transactions/{id}/transfer` | Leg 2 |
| 12 | `POST /api/v1/kenya/applications/{id}/wakala` | Wakala consent |
| 13 | `POST /api/v1/kenya/applications/{id}/complete-settlement` | Liquidate and disburse |
| 14 | `GET /api/v1/kenya/applications/{id}/repayments` | Schedule |
| 15 | `POST /api/v1/kenya/repayments/{id}/collect` | Pay installment |

**One-click mock demo:**

```http
POST /api/v1/kenya/applications/{id}/run-full-flow
```

**Verify Shariah integrity:**

```http
GET /api/v1/kenya/applications/{id}/shariah-audit/verify
GET /api/v1/kenya/shariah-audit/export?format=csv
```

Full flow reference: [KENYA_FLOW.md](KENYA_FLOW.md)

---

## 4b. Users and API keys (Swagger)

Open http://localhost:8000/docs (`AUTH_ENABLED=true`). Use **Authorize** after login so Try it out sends the session.

1. **Production Ops → `POST /ops/auth/login`** with Super Admin (`OPS_BOOTSTRAP_ADMIN_EMAIL` / `OPS_BOOTSTRAP_ADMIN_PASSWORD`). Copy `access_token`.
2. If `must_change_password` is true, run **`POST /ops/auth/change-password`**, then copy the new `access_token`.
3. Click **Authorize** → **BearerAuth** → paste the token (no `Bearer ` prefix) → Authorize.
4. **`GET /institutions`** — copy an `id`.
5. **`POST /ops/auth/users`** as Super Admin with `role: institution_admin` and that `institution_id`. Super Admin may also invite `institution_ops` or `fi_approver`.
6. Log in as the new FI Admin, change password, Authorize with that token, then **`POST /ops/auth/users`** with `role: institution_ops` or `fi_approver`. FI Admin inviting `bti_ops` returns 403.
7. Switch back to Super Admin and **`POST /institutions/{id}/api-keys`** with `role: api_client`. The same call as FI Admin returns 403.

Seeded FI Admin (`fi.admin@…` from `OPS_SEED_EMAIL_DOMAIN`) can skip step 5 if that user already exists. Password is in `data/ops_seed_credentials.txt` unless it was already changed.

Who may invite whom: [USERS_ACCESS_CONTROLS.md](USERS_ACCESS_CONTROLS.md).

---

## 5. Ops portal

```powershell
cd portal
npm install
npm run dev
```

Open http://localhost:5173

- **Kenya MNO Flow** — demo runner (mock mode)
- **Integrations** — per-institution Daraja/MNO config
- **Application detail** — Shariah audit, business steps

---

## 6. Expo mobile app

```powershell
cd mobile
npm install
$env:EXPO_PUBLIC_API_URL="http://192.168.x.x:8000/api/v1"
npm start
```

Screens: Apply, Offer, Contract, Settlement, Status, Repayments.

Use a LAN IP on a physical device. `localhost` only works on the machine running the API.

---

## 7. Shariah audit microservice (optional)

In a second terminal, from the repository root:

```powershell
$env:SHARIAH_AUDIT_DATABASE_URL="sqlite:///./data/shariah_audit.db"
python shariah-audit-service/app.py
```

Set in `.env` on the engine:

```env
SHARIAH_AUDIT_SERVICE_URL=http://localhost:8001
```

Verify:

```http
GET http://localhost:8001/health
GET http://localhost:8001/v1/verify-chain
```

Details: [SHARIAH_AUDIT.md](SHARIAH_AUDIT.md)

---

## 8. Docker Compose

```powershell
docker compose up --build
```

| Service | Port |
|---------|------|
| API | 8000 |
| Shariah audit | 8001 |
| Portal | 5173 |
| PostgreSQL | 5432 |

---

## 9. Demo script

With the API running:

```powershell
python scripts/demo_flow.py
```

---

## 10. Manual bridge (Malaysia pre-live)

Ops trade on the BSAS portal or the bank commodity desk, then paste the e-certificate into the engine.

### Ops portal

1. Open **Malaysia Manual Bridge** at http://127.0.0.1:5173/malaysia
2. Click **Start manual-bridge flow**
3. Copy the request packet fields into BSAS or send them to the bank desk
4. Paste the e-certificate number and confirm
5. Repeat for Legs 2–3, then **Disburse funds**

### API / Swagger

1. Create application, then offer, then accept
2. `POST /api/v1/transactions` with `"mode": "manual_bridge"`
3. `POST /api/v1/manual-bridge/transactions/{id}/advance` — writes a request under `data/manual_bridge/requests/`
4. `GET /api/v1/manual-bridge/pending` — ops inbox
5. Trade off-platform, then:

```http
POST /api/v1/transactions/{id}/legs/1/confirm
{"certificate_number": "CERT-BSAS-12345", "issuer": "BSAS"}
```

6. Advance again for Leg 2 and Leg 3

Confirm also writes `data/manual_bridge/replies/{external_ref}.json` so the file inbox stays in sync.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `run-full-flow` returns 400 | Set `KENYA_INTEGRATION_MODE=mock` |
| Offer before possession fails | Complete purchase and possession first |
| Liquidate fails "Wakala" | Call `POST .../wakala` after transfer |
| pytest database locked | Stop other API or pytest processes using `tawarruq.db` |
| pytest slow or hung | Clear `SHARIAH_AUDIT_SERVICE_URL` in the test env (conftest does this) |
| Mobile cannot reach API | Use the LAN IP in `EXPO_PUBLIC_API_URL` |

Live partner setup: [INTEGRATIONS.md](INTEGRATIONS.md)
