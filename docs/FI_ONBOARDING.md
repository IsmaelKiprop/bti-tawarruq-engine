# FI onboarding

BTI onboards **customer financial institutions** (banks, SACCOs, and other FIs). The FI is BTI’s customer. Onboarding is a KYC wizard. Engine settings (BSAS mode, deal maker-checker, billing fee) stay on **Manage**.

There is **no maker-checker on FI onboarding**. Super Admin activate is immediate. BTI Ops submit waits for Super Admin. Deal maker-checker (Murabaha, liquidation, disbursement) stays on institution management.

This slice stores KYC fields and document **references** (filename or ticket id). File upload and live PEP / sanctions screening are not in this release. Screening statuses default to `NOT_STARTED`.

## Who can onboard

| Actor | Start / save / submit | Approve or return | Set Active / Dormant / Deactivated | Invite FI Admin |
|-------|------------------------|-------------------|------------------------------------|-----------------|
| Super Admin | Yes. Submit activates. | Yes | Yes | Only when lifecycle is `active` |
| BTI Ops | Yes. Submit goes to `pending_approval`. | No | No | Only when lifecycle is `active` |
| FI Admin | View own KYC only | No | No | Own tenant after Active (FI desk roles). May request API Client |
| Everyone else | No | No | No | No |

FI roles only see their own tenant. Do not invite FI Admin or FI desk users onto a draft or pending FI. After Active, Super Admin or BTI Ops invites FI Admin. That FI Admin invites FI Operations, FI Approver, and other FI desk roles in their tenancy.

## Portal

Tester-shell nav: Dashboard, Onboard FI, Institutions, Users, Settings, then Ops Monitor, then Audit. Kenya / Malaysia / Approvals stay hidden until the tester shell is lifted.

| Page | Path | Purpose |
|------|------|---------|
| Dashboard | `/` | Super Admin: type pie, regulator pie, onboarded-by-month bar, Active / Dormant / Deactivated, uptime, primary Onboard button. Other roles: uptime only. |
| Onboard FI | `/institutions/onboard` | New KYC wizard |
| Resume KYC | `/institutions/:id/onboard` | Continue a draft or review a pending / active profile |
| Directory | `/institutions` | Search, lifecycle filter, resume / approve, link to Manage |
| Manage | `/institutions/:id` | Engine settings only |
| Users | `/users` | Super Admin and BTI Ops invite FI Admin. Dropdown lists **Active** FIs only. FI Admin invites own-tenant desk roles. |
| FI profile | `/institution` | FI Admin: read-only KYC and **Request API Client** |

Super Admin home is Dashboard. Super Admin CTA on Review: **Activate institution**. BTI Ops CTA: **Submit for Super Admin approval**. Wizard CTAs: **Previous**, **Save draft**, **Next**.

### Wizard pages

One KYC category per page. **Next** is blocked until that page’s required fields are valid. You cannot skip ahead by clicking later steps. **Save draft** still stores incomplete work. Final submit re-checks the same rules.

1. **Identity** — legal name (writes `institutions.name`), code (auto from name, editable), type, support email, main telephone, address, KRA PIN, website.
2. **Regulatory** — primary regulator, licence number, issue / expiry, licence status, register URL.
3. **Ownership** — parent, shareholders, UBOs, board, senior management, PEP / sanctions / adverse-media status.
4. **Representatives** — primary contact, compliance officer, signatories, ID type / number / status, authority document reference.
5. **Settlement** — bank, account name / number / currency, verification status, evidence document reference. Full account numbers are not written into audit `details`.
6. **Commercial** — expected monthly count / value, typical / max amount, go-live, commercial agreement, pricing reference, dispute email.
7. **Review** — summary. Super Admin activates. BTI Ops submits for Super Admin.

`other_institution_type` is required when type is OTHER. `regulator_other_name` is required when regulator is OTHER.

## Lifecycle

`institutions.lifecycle_status` is the source of truth. `institutions.active` stays in sync (`true` only when lifecycle is `active`) so existing tenant-suspend middleware still works.

| Status | Meaning | Invite FI Admin |
|--------|---------|-----------------|
| `draft` | KYC in progress | Blocked |
| `pending_approval` | BTI Ops submitted | Blocked |
| `active` | Live customer FI | Allowed |
| `dormant` | Paused | Blocked |
| `deactivated` | Closed | Blocked |

Existing DEFAULT / MWALIMU / DIB rows stay `active` with an empty profile until someone fills KYC.

```
Onboard wizard → save draft
        │
        ├─ Super Admin submit → active
        └─ BTI Ops submit → pending_approval
                    │
                    ├─ Super Admin approve → active
                    └─ Super Admin return → draft
```

## API

Keep `POST /institutions` (name / code) for seeds and tests. Portal onboarding uses the routes below. Prefix `/api/v1`.

| Method | Path | Who | Notes |
|--------|------|-----|-------|
| GET | `/institutions` | Session / key; FI roles are tenant-scoped | Directory |
| GET | `/institutions/summary` | Super Admin (`manage_institutions`) | Dashboard charts |
| POST | `/institutions/onboarding` | Super Admin or BTI Ops | Start draft |
| GET | `/institutions/{id}/onboarding` | Super Admin, BTI Ops, or FI Admin (own tenant) | Read KYC |
| PATCH | `/institutions/{id}/onboarding` | Super Admin or BTI Ops | Save draft |
| POST | `/institutions/{id}/onboarding/submit` | Super Admin or BTI Ops | Super Admin → `active` + `APPROVED`. BTI Ops → `pending_approval` + `UNDER_REVIEW` |
| POST | `/institutions/{id}/onboarding/decide` | Super Admin | `{ "decision": "approve" \| "return" \| "reject", "reason"? }` |
| PATCH | `/institutions/{id}/lifecycle` | Super Admin | `{ "lifecycle_status": "active" \| "dormant" \| "deactivated" }` |
| GET / POST | `/institutions/{id}/api-keys/request` | FI Admin (own tenant) | Request API Client. GET is `requested` (pending) or `issued` with `api_key` + `hmac_secret` to copy. Super Admin issues `POST /institutions/{id}/api-keys` |

`fi_id` is the engine institution UUID. It is not typed on the form.

## Data model

Alembic **`015`**. SQLite `init_db` adds `lifecycle_status` and `create_all` builds `institution_profiles`.

**`institutions`:** tenant row (`code`, `active`, `lifecycle_status`, BSAS, fee, approval steps).

**`institution_profiles`:** 1:1 KYC. JSON columns for shareholders, UBOs, directors, senior management, signatories, related entities. Workflow: `application_status`, `submission_date`, `approval_decision`, `approval_reason`, `approver_id`, `created_by`, `updated_by`.

## Tester walk (portal)

Local Compose portal: http://127.0.0.1:15173. Seed emails and passwords: `data/ops_seed_credentials.txt`. Privileged roles must change password and should enroll TOTP.

1. Super Admin signs in. Dashboard is first: charts and **Onboard financial institution**.
2. Onboard a Bank and a SACCO. Activate. Confirm they appear as Active and the charts update.
3. Open Institutions. Filter by lifecycle. Open Manage for BSAS / deal maker-checker only.
4. Users: invite FI Admin only for an Active FI. Draft / pending FIs are not in the dropdown.
5. Optional: BTI Ops starts a third FI and submits. Super Admin approves from the directory or the Review page.

Swagger: after Super Admin login, `POST /institutions/onboarding` then `POST /institutions/{id}/onboarding/submit`. Invite FI Admin only after `lifecycle_status` is `active`.

## Tests

```powershell
$env:PYTHONPATH="src"
python -m pytest tests/test_institution_onboarding.py tests/test_rbac.py tests/test_invite_matrix.py tests/test_ops_login.py tests/test_auth_scope.py -q
```

Covered: Super Admin submit activates and allows invite; BTI Ops submit is pending and invite is blocked until Super Admin approve; FI Admin cannot onboard or see other tenants; incomplete KYC is rejected on submit.

## Deploy

```bash
# On the VPS: stash compose, pull, restore compose. Do not commit VPS compose.
cp docker-compose.yml /tmp/docker-compose.yml.vps
git stash push -m "vps compose" -- docker-compose.yml
git pull
cp /tmp/docker-compose.yml.vps docker-compose.yml

# Schema from init_db with no alembic_version row:
docker compose exec api alembic stamp 014
docker compose exec api alembic upgrade head

# Already at 014:
docker compose exec api alembic upgrade head

docker compose build --no-cache api portal
docker compose up -d api portal
```

Do not `git add` Word lock files.

## Source map

| Area | Files |
|------|--------|
| Model | `src/tawarruq/models/institution.py`, `institution_profile.py` |
| Service | `src/tawarruq/services/institution_onboarding_service.py` |
| HTTP | `src/tawarruq/api/routes.py` |
| Migration | `alembic/versions/015_institution_kyc_profile.py`, `src/tawarruq/database.py` |
| Portal | `portal/src/pages/InstitutionOnboardPage.tsx`, `InstitutionsPage.tsx`, `DashboardPage.tsx`, `config/fiKyc.ts` |
| Tests | `tests/test_institution_onboarding.py` |

## Not in this slice

| Item | Notes |
|------|--------|
| KYC file store / virus scan | Document fields take a text reference |
| Live PEP / sanctions | Status enums only |
| Super Admin inviting FI Ops / FI Approver | Unchanged invite map |
| Opening Kenya / Malaysia / Approvals for testers | `TESTER_SHELL` stays on |
