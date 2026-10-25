# Deployment: packaging and data stores

The product is a Python API, an nginx portal, and Postgres. Docker Compose is the **reference installer**, not a requirement of the engine. Tenancy and backups are decided by **how many Postgres instances you run**, not by containers.

Customer-server steps: [ONPREM.md](ONPREM.md). Ledger behaviour: [SHARIAH_AUDIT.md](SHARIAH_AUDIT.md). BTI VPS: [PRODUCTION_OPS.md](PRODUCTION_OPS.md).

## What an install actually is

| Process | Role | Default in Compose |
|---------|------|--------------------|
| `api` | Engine + Amanah + primary ledger | Postgres via `DATABASE_URL` |
| `portal` | Ops UI | Static nginx, proxies `/api` |
| `postgres` | Book, users, keys, `shariah_audit_logs` | One database named `tawarruq` |
| `shariah-audit` | Optional HTTP **mirror** of the ledger | **Separate SQLite file** under `./data/` |

The engine talks to the database through `DATABASE_URL` only. Lab can use SQLite (`python -m tawarruq.cli serve`). Production must use Postgres.

## Why Docker, and when not to use it

Compose exists so a VPS or a bank VM starts the same four processes without matching Python versions by hand. Keep it as the default ship vehicle.

| Situation | Ship this |
|-----------|-----------|
| BTI managed cluster, most on-prem VMs | Docker Compose (`docker-compose.yml` or `docker-compose.onprem.yml`) |
| Bank already runs Postgres (and maybe Kubernetes) | Same API/portal **images**, **their** Postgres. Drop the `postgres` service. Set `DATABASE_URL`. Helm only if they already live on K8s |
| Bank forbids containers | systemd (or a Windows service) + venv + nginx/IIS + their Postgres. Same env vars |
| Air-gap / no Docker Hub | Offline image tarball, or the systemd path |
| Local lab | SQLite + Vite, or local Compose. Not a production topology |

Do not adopt Kubernetes for the first on-prem sale unless the bank already operates it. One VM + Compose, or one VM + their Postgres, is enough.

## Database tenancy (implemented)

**One Postgres per install. Tenants are rows, not databases.**

```
Managed (BTI SaaS)          On-prem (bank DC)
┌─────────────────┐         ┌─────────────────┐
│  one Postgres   │         │  their Postgres │
│  institutions[] │         │  one SITE row   │
│  Bank A, SACCO B│         │  (no sibling FI)│
└─────────────────┘         └─────────────────┘
```

- **Managed:** Bank A and SACCO B share `institutions` and related tables. Isolation is `institution_id` + RBAC in [`src/tawarruq/api/deps.py`](../src/tawarruq/api/deps.py). Super Admin can see across tenants by design.
- **On-prem:** `docker-compose.onprem.yml` creates a **new** Postgres volume. Other customers are not in it. Inside it there is still one database and usually one institution (`ONPREM_INSTITUTION_CODE`).

Two on-prem banks never share a database, because they are two installs. Two FIs on BTI’s cloud **do** share a database.

That is normal for an early multi-tenant product. It is also the item a regulated bank will challenge on a **managed** contract: one missed tenant filter, one cluster-wide restore, or one noisy neighbour.

**Keep this shape until a customer pays for more isolation.** Then add **database-per-tenant** on managed (a `DATABASE_URL` per institution). Do not use schema-per-tenant — auditors do not treat a shared `postgres` superuser as isolation.

| Offer | Database |
|-------|----------|
| SACCO on BTI cloud | Shared Postgres, row scope |
| Large FI on BTI cloud who requires residency | Dedicated Postgres, still BTI-hosted (not implemented as a product flag yet) |
| Same FI, their DC | On-prem Compose **or** their existing Postgres — never the SaaS DB |

## Shariah audit stores (packaging gap)

There are **two** ledgers today:

1. **Primary (correct for backups)** — `shariah_audit_logs` in the **engine** database. Hash chain, append-only ORM guards, exports. This is what the portal and `/kenya/shariah-audit*` read.
2. **Optional mirror** — `shariah-audit` process. Compose sets `SHARIAH_AUDIT_DATABASE_URL=sqlite:////app/data/shariah_audit.db`. That file is **not** in Postgres backups.

This is a packaging gap, not a tenancy design. The primary chain is already in Postgres. The mirror is a second copy for an isolated audit service. On a lab or BTI VPS the SQLite file is acceptable if `./data` is snapshotted. On a **real on-prem** install, point the mirror at the **same Postgres server**, a **separate database** (do not reuse `tawarruq` — the audit process runs `init_db()` and would create engine tables).

Create the extra database once:

```sql
CREATE DATABASE tawarruq_audit;
```

Then in `.env`:

```env
SHARIAH_AUDIT_SERVICE_URL=http://shariah-audit:8001
SHARIAH_AUDIT_DATABASE_URL=postgresql+psycopg://tawarruq:YOUR_PASSWORD@postgres:5432/tawarruq_audit
```

`docker-compose.onprem.yml` reads `SHARIAH_AUDIT_DATABASE_URL` from the environment. Recreate `shariah-audit` after changing it. Back up `tawarruq` and `tawarruq_audit` together.

If the bank does not want the extra process, leave `SHARIAH_AUDIT_SERVICE_URL` empty. The primary ledger in the engine database is enough; the mirror is optional.

## What this does not change

- Local Docker on `127.0.0.1:15173` and the BTI VPS compose stay **managed** + Compose Postgres.
- Do not overwrite production `docker-compose.yml` with the on-prem file.
- License files, Helm, and air-gap registries are later work, not required to sell the first on-prem install.
