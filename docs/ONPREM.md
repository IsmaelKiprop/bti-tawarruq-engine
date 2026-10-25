# On-prem install

Same images as the BTI-hosted engine. This edition is a **customer-owned single-tenant stack**: one live institution, site admin issues API keys, and only the product modules you enable.

The BTI VPS stays on the existing `docker-compose.yml`. Do **not** replace that file with this one.

Packaging choices (Compose vs their Postgres vs systemd) and how tenancy is stored: [DEPLOYMENT.md](DEPLOYMENT.md).

## What changes vs managed SaaS

| | Managed (`DEPLOYMENT_MODE=managed`) | On-prem (`DEPLOYMENT_MODE=onprem`) |
|---|---|---|
| Tenants | Many FIs on one cluster | One site institution |
| Operator roles | BTI Super Admin / Ops / Finance | Same permission codes, Site Admin / Ops / Finance labels |
| API keys | Super Admin only | Site Admin or FI Admin |
| Seed | BTI catalogue + MWALIMU / DIB demos | Site institution + site staff only |
| Brand | Buruuj Fintech | `BRAND_NAME` |
| Desks | All tracks | `ENABLED_PRODUCTS` |
| Database | One shared Postgres, many `institutions` rows | Their Postgres (Compose volume or bank-owned). Still one database; usually one institution |
| Shariah mirror | SQLite file in `./data` (lab / VPS default) | Point `SHARIAH_AUDIT_DATABASE_URL` at Postgres `tawarruq_audit` — see [DEPLOYMENT.md](DEPLOYMENT.md#shariah-audit-stores-packaging-gap) |

## Install

1. Copy [`.env.onprem.example`](../.env.onprem.example) to `.env` and fill secrets.
2. Generate an encryption key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

3. Set `OPS_SESSION_SECRET` to a long random string.
4. Put TLS in front of the portal and API (Caddy, nginx, or the bank’s ingress). Compose binds the API to `127.0.0.1:8000` and the portal to `PORTAL_BIND` (default `8080`).
5. Start:

```bash
docker compose -f docker-compose.onprem.yml --env-file .env up -d --build
```

6. Sign in as `OPS_BOOTSTRAP_ADMIN_EMAIL`. Change the password. Enroll TOTP.
7. Set `OPS_SEED_USERS=false` in `.env` and recreate the API container so later restarts do not add catalogue users.

```bash
docker compose -f docker-compose.onprem.yml --env-file .env up -d api
```

8. Schema upgrades (image now includes Alembic):

```bash
docker compose -f docker-compose.onprem.yml exec api alembic upgrade head
```

## Product modules

`ENABLED_PRODUCTS` is a comma-separated list:

- `kenya` — Kenya ops, customers, repayments, agent dealers, M-Pesa callbacks
- `malaysia` — Malaysia manual bridge
- `sedania` — Sedania AS SIDQ
- `sacco` — inbound SACCO execute
- `billing` — BTI-style usage invoices (usually off on-prem)
- `mobile` — Buruuj Lend / mobile invite APIs

Example Kenya-only bank:

```env
ENABLED_PRODUCTS=kenya
```

The portal reads the same flags from `GET /health` and `/ops/auth/me` and hides nav for disabled modules. The Institutions directory is hidden on-prem; the site institution is seeded from `ONPREM_INSTITUTION_NAME` / `ONPREM_INSTITUTION_CODE`.

## Brand

- `BRAND_NAME` — login lockup, TOTP issuer (`{Brand} Ops`), certificate chrome
- Portal logo stays the Buruuj mark only when `BRAND_NAME` is Buruuj Fintech; otherwise the name is shown as text
- `CORS_ORIGINS` — extra browser origins (comma-separated). `PORTAL_PUBLIC_URL` is always allowed

## Data stores on this host

Compose starts **one** Postgres (`tawarruq`) for the book, users, keys, and the **primary** Shariah table `shariah_audit_logs`. That is the database to back up.

The `shariah-audit` container is an optional **mirror**. Out of the box it uses SQLite at `./data/shariah_audit.db`, which is **not** in a `pg_dump`. For a production on-prem site, create `tawarruq_audit` on the same Postgres and set `SHARIAH_AUDIT_DATABASE_URL` as in [DEPLOYMENT.md](DEPLOYMENT.md#shariah-audit-stores-packaging-gap). The bank may also skip the mirror and rely on the engine table only.

If IT already operates Postgres, delete the `postgres` service from a local override and set `DATABASE_URL` (and the audit URL) at their host. The API does not require Docker — only that URL.

## After go-live

- Keep Postgres unpublished except `127.0.0.1` (or do not publish it at all if only the API talks to it)
- Back up Postgres `tawarruq` and, if used, `tawarruq_audit`. Do not treat the SQLite audit file as the system of record
- Rotate the bootstrap password and any seed API key in `data/ops_seed_credentials.txt`
- Point `PUBLIC_API_BASE_URL` at the public HTTPS API so partner callbacks resolve
- Do not merge this compose over the BTI production file
