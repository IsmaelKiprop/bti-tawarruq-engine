# Production Ops Stack

This guide covers production auth flags, monitoring, and CI/CD deploy for the Buruuj Tawarruq engine.

Complete users, maker-checker, billing, reconciliation, and MFA documentation: **[USERS_ACCESS_CONTROLS.md](USERS_ACCESS_CONTROLS.md)**. Stakeholder catalogue: `docs/BTI_Tawarruq_Users_ver_001.docx`.

## Role-based access control (RBAC)

When `AUTH_ENABLED=true`, protected routes require an ops session Bearer token or an `X-API-Key`. Roles align with `docs/BTI_Tawarruq_Users_ver_001.docx`. Full permission matrix and APIs: [USERS_ACCESS_CONTROLS.md](USERS_ACCESS_CONTROLS.md).

| Role | Doc category | Scope | Core permissions |
|------|--------------|-------|------------------|
| `platform_admin` | BTI Platform Super Administrator | Platform | Tenant lifecycle, credentials, billing, retries (`write_bti_ops`). **No** `write_ops` / `approve_txn` — admin access does not execute trades |
| `bti_ops` | BTI Tawarruq Operations Officer | Platform | Cross-tenant ops (`write_ops`, `write_bti_ops`) — not tenant lifecycle |
| `bti_finance` | BTI Finance / Billing Officer | Platform | `manage_billing` (no trade execution) |
| `institution_admin` | FI Administrator | Own tenant | Ops + users/integrations + `approve_txn`. Cannot create API keys |
| `institution_ops` | FI Operations Officer | Own tenant | Initiate/monitor (`write_ops`) |
| `fi_approver` | FI Approver | Own tenant | `approve_txn` only (maker-checker) |
| `shariah_officer` | Shariah / Audit | Tenant | Read-only + `view_shariah` |
| `reconciler` | Reconciliation Officer | Tenant or BTI-wide | `reconcile` |
| `read_only` | Viewer | Own tenant | GET + metrics |
| `agent_dealer` | Kenya float desk | Dealer | `dealer_desk` only |
| `api_client` | Institution API Client | Machine key | `api_submit` + `write_ops` (not a portal login) |

### Create keys with roles

```bash
curl -X POST http://localhost:8000/api/v1/institutions/{id}/api-keys \
  -H "X-API-Key: $PLATFORM_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"fi-core-banking","role":"api_client"}'
```

Only Super Admin (`platform_admin`) can create API keys or register new institutions. Super Admin may invite Super Admin, BTI Ops, BTI Finance, FI Admin, FI Operations, FI Approver, Shariah / Audit, and Reconciliation. FI Admin invites FI desk staff (FI Admin, FI Operations, FI Approver, Shariah / Audit, Reconciliation) for their own tenant.

### Portal auth (email + password)

With `AUTH_ENABLED=true`, the ops portal uses a login page (not pasted API keys):

1. On API start (when `OPS_SEED_USERS=true`, default), the engine **idempotently** seeds the BTI role catalogue: BTI ops/finance, FI admin/ops/approver, shariah, reconciler, read-only, agent dealer, plus an `api_client` key. Existing emails are never overwritten.
2. Bootstrap / seed passwords come from `OPS_BOOTSTRAP_*` and `OPS_SEED_PASSWORD`. New secrets are appended to `data/ops_seed_credentials.txt` (gitignored).
3. Sign in at `/login`. Temporary passwords force `/change-password` before any other page.
4. Re-run anytime: `python -m tawarruq.cli seed-ops-users`
5. Super Admin invites staff under **Users** using the named roles, including FI Admin, FI Operations, and FI Approver when needed.
6. Machine clients use `X-API-Key` (`api_client` role preferred). Super Admin issues the key on **Webhooks**; FI Admin requests BTI to onboard.
7. Privileged portal roles (Super Admin, BTI Ops, BTI Finance) should enroll TOTP at `/mfa-enroll`. After enrollment, login requires the authenticator code.
8. Murabaha, liquidation, and disbursement are maker-checker gated when `AUTH_ENABLED=true`. FI Ops queues the step; FI Approvers act on **Approvals**. Amount limits on the institution or the approver are enforced. The initiator cannot be the sole approver.

| Seeded email (domain = `OPS_SEED_EMAIL_DOMAIN`) | Role |
|-----------------------------------------------|------|
| `OPS_BOOTSTRAP_ADMIN_EMAIL` | `platform_admin` |
| `bti.ops@…` | `bti_ops` |
| `bti.finance@…` | `bti_finance` |
| `fi.admin@…` | `institution_admin` (default / MWALIMU tenant) |
| `fi.ops@…` | `institution_ops` |
| `fi.approver@…` | `fi_approver` |
| `shariah@…` | `shariah_officer` |
| `reconciler@…` | `reconciler` (BTI-wide) |
| `fi.reconciler@…` | `reconciler` (tenant) |
| `readonly@…` | `read_only` |
| `dealer@…` | `agent_dealer` (SEED-DEALER pool) |

### Environment

```env
AUTH_ENABLED=true
API_KEY_HEADER=X-API-Key
OPS_SESSION_SECRET=replace-with-long-random-string
OPS_BOOTSTRAP_ADMIN_EMAIL=admin@bti.local
OPS_BOOTSTRAP_ADMIN_PASSWORD=ChangeMeNow!123
CALLBACK_AUTH_TOKEN=your-callback-secret   # optional, for inbound Daraja/MNO webhooks
```

Run Alembic through `011` (controls, billing, MFA columns). SQLite `init_db` adds missing columns automatically:

```bash
alembic upgrade head
```

## Monitoring

### Health check

`GET /health` — engine status, integration flags, `auth_enabled`, `database_ok`.

### Ops metrics dashboard

`GET /api/v1/ops/metrics` — JSON snapshot for the portal **Ops Monitor** page:

- Application and transaction counts by status
- Manual bridge pending count
- Active webhooks / API keys
- HTTP request counters and average latency

Requires `view_metrics` permission (all roles except unauthenticated when auth is on).

### Prometheus scrape

`GET /metrics` — public text exposition (no auth). Example metrics:

- `tawarruq_applications_total`
- `tawarruq_transactions_by_status{status="..."}`
- `tawarruq_manual_bridge_pending`
- `tawarruq_http_requests_total`
- `tawarruq_http_errors_total`

Point Prometheus or Grafana Agent at `http://engine:8000/metrics`.

## CI/CD

### Continuous integration (`.github/workflows/ci.yml`)

On every push/PR:

1. `pytest` — full engine test suite including RBAC tests
2. Portal `npm ci && npm run build`
3. Docker image build for API and portal

### Deploy (`.github/workflows/deploy.yml`)

Triggered on push to `main` or manual **workflow_dispatch** (staging/production):

1. Builds tagged Docker images (`engine` + `portal`)
2. Exports `deploy-artifacts/` tarball for `docker compose up`

### Local production stack

```bash
docker compose up -d
```

Services:

| Service | Port | Notes |
|---------|------|-------|
| postgres | 5432 | Production database |
| api | 8000 | Set `AUTH_ENABLED=true` in compose env |
| shariah-audit | 8001 | Append-only mirror |
| portal | 5173 | Set `VITE_API_URL` to public API |

### Go-live checklist

- [ ] Postgres `DATABASE_URL` (not SQLite)
- [ ] `AUTH_ENABLED=true`
- [ ] Alembic `011` applied (approvals, billing, MFA columns)
- [ ] Super Admin password rotated and TOTP enrolled
- [ ] Create `platform_admin` + per-institution keys / FI Approver
- [ ] Configure real Daraja / MNO / BSAS credentials
- [ ] Register HTTPS callback URLs
- [ ] Scrape `/metrics` into your observability stack
- [ ] Enable GitHub deploy workflow environment secrets for your host
