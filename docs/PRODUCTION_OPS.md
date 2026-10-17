# Production Ops Stack

This guide covers role-based auth, monitoring, and CI/CD deploy for the Buruuj Tawarruq engine.

## Role-based access control (RBAC)

When `AUTH_ENABLED=true`, every protected route requires an `X-API-Key` header. API keys carry one of four roles:

| Role | Scope | Permissions |
|------|-------|-------------|
| `platform_admin` | All institutions | Full access including create institutions and cross-tenant reads |
| `institution_admin` | Own institution | Ops writes + manage webhooks, API keys, integrations |
| `institution_ops` | Own institution | Daily ops (applications, transactions, manual bridge, Kenya flow) |
| `read_only` | Own institution | GET only + metrics (auditors, dashboards) |

### Create keys with roles

```bash
curl -X POST http://localhost:8000/api/v1/institutions/{id}/api-keys \
  -H "X-API-Key: $PLATFORM_ADMIN_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"ops-portal","role":"institution_admin"}'
```

Only `platform_admin` keys can create other `platform_admin` keys or register new institutions.

### Portal auth (email + password)

With `AUTH_ENABLED=true`, the ops portal uses a login page (not pasted API keys):

1. Bootstrap admin is created on first API start when no ops users exist (`OPS_BOOTSTRAP_ADMIN_EMAIL` / `OPS_BOOTSTRAP_ADMIN_PASSWORD`).
2. Sign in at `/login`. Temporary passwords force `/change-password` before any other page.
3. **Log out** clears the session and returns to `/login`.
4. Platform / institution admins open **Users** to create logins, copy the temporary password, and send it out of band.
5. Machine clients can still use `X-API-Key` for API automation.

### Environment

```env
AUTH_ENABLED=true
API_KEY_HEADER=X-API-Key
OPS_SESSION_SECRET=replace-with-long-random-string
OPS_BOOTSTRAP_ADMIN_EMAIL=admin@bti.local
OPS_BOOTSTRAP_ADMIN_PASSWORD=ChangeMeNow!123
CALLBACK_AUTH_TOKEN=your-callback-secret   # optional, for inbound Daraja/MNO webhooks
```

Run Alembic migration `004` (or restart with SQLite — `init_db` adds the `role` column automatically):

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
- [ ] Create `platform_admin` + per-institution keys
- [ ] Configure real Daraja / MNO / BSAS credentials
- [ ] Register HTTPS callback URLs
- [ ] Scrape `/metrics` into your observability stack
- [ ] Enable GitHub deploy workflow environment secrets for your host
