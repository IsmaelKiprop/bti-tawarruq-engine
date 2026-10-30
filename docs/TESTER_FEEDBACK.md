# Tester and operator feedback (implemented)

Record of the FI tester / BTI Ops suggestions that are now in the engine and portal. Companion guides stay the source of truth for fields and runbooks: [FI_ONBOARDING.md](FI_ONBOARDING.md), [USERS_ACCESS_CONTROLS.md](USERS_ACCESS_CONTROLS.md), [SHARIAH_AUDIT.md](SHARIAH_AUDIT.md).

Kenya Ops was **not** rewritten. FI desk work is a new **Origination** page (`/origination`). SMTP invite mail is still later.

Schema: Alembic **`016`** (API key reveal), **`017`** (`fi_desk_cases`), **`018`** (platform settings), **`019`** (charge percents), **`020`** (provider rate history). `TESTER_SHELL` stays on. Super Admin / BTI Ops / FI Admin see Dashboard, Onboard FI, Institutions, Users, Settings, Ops Monitor, Audit, Origination, and Shariah. **Shariah officers** land on Shariah Audit: BTI-wide sees all FIs, FI-bound sees their tenant. **FI Ops** sees Origination, All Workflows, Settings, plus the live Tawarruq desk (`/malaysia` or `/sedania`) when Super Admin’s latest provider matches. **FI Approver** sees Origination, Approval Queue, Settings. No Dashboard, Shariah, or Ops Monitor. Kenya / Approvals / Billing stay hidden.

---

## What shipped

| Suggestion | Where | What you see |
|------------|-------|--------------|
| Navbar should show the page title only | Every portal page | Title in the top bar. The old one-line description under the title is gone. |
| FI Admin should see API Client pending **and** issued | Institution profile `/institution` | **Pending Super Admin** after Request. **API client issued** after Super Admin creates the key. |
| After issue, FI Admin must be able to copy the key | `/institution`, Super Admin Webhooks / Institutions | Masked secrets, Show / Hide, Copy, Copy both. Reveal needs the signed-in user’s password. |
| Copy UI should be clean | Same copy panel on profile, Webhooks, Institutions, Dashboard | One panel: prefix visible, full secret hidden until password + Show. |
| Super Admin issues keys; FI Admin only requests | Webhooks + profile | `POST /institutions/{id}/api-keys` is Super Admin only. FI Admin uses Request. A second request is blocked once issued. |
| GET must not dump plaintext keys | `GET /institutions/{id}/api-keys/request` | Status, prefix, timestamps. `api_key` and `hmac_secret` are null until reveal. |
| FI Ops needs an eight-step desk | `/origination` | Gated wizard. Profit and FI Approver sit on step 1. Approval Queue stays for the assigned approver. FI Ops and FI Approver land here after login. |
| No Dashboard / Shariah / Ops for FI Ops | Sidebar | Those three are hidden for FI Ops and FI Approver. Login ignores a leftover `/users` URL and sends them to Origination. |
| Approval Queue for FI Approver | `/origination/queue` | Lists assigned requests. Customer name column. Search by customer or requester. Filter by officer, status, date. Open jumps to the desk. |
| All Workflows for FI Ops | `/origination/workflows` | Lists origination cases. Filter by customer, status, date. Clearing marks the case **Complete** (not In Progress). Open jumps to the desk. |
| Sedania % Charge and BTI % Charge | Settings, Onboard | Super Admin: Sedania default **0.0035%**, per-FI BTI default **0.004%**. Save needs password and OTP. New FIs set BTI % Charge on Onboard → Commercial. |
| Commodity type is Airtime only | Origination step 1 | Document type then ID. Amount cannot be negative. **Commodity type** is Airtime only. |
| Step 3 locks after Yes | Origination step 3 | After confirm, purchase complete cannot be changed. |
| Buyer / Seller and facility on Murabaha | Origination step 4 | Buyer (name, email, phone) and Seller (FI) first, then facility account, repayment installments, first and last installment due dates. |
| Current commodity owner on resale | Origination step 5 | Separate rows: owner, email, phone (from the customer). |
| CASA on Complete proceeds | Origination step 6 | Customer CASA account and branch are required. |
| Later steps wait for Approval | Origination step 1 | FI Ops picks an FI Approver and sends the case. That approver decides on the same first screen (not Kenya `/approvals`). The separate approval tab is hidden. |
| Customer journey instead of OTP | Approve + later steps | Approve creates the existing `/customer/{ref}` journey and emails the offer. Murabaha waits for the customer to accept. Later desk steps, Bursa, and Sedania email the same journey link. |
| Every desk action must leave a Shariah trail | Shariah Audit | Each create / decide / step / OTP writes `log_shariah_step` with a timestamp. |
| Shariah Audit must be visible to testers | `/shariah` | Unhidden in the tester shell. Super Admin / BTI Ops / BTI-wide Shariah: all institutions or one. FI Shariah / FI Admin: own tenant. |
| Audit for Shariah officers at BTI and FI level | `/shariah`, Users | Super Admin invites **Shariah / Audit (BTI-wide)** from the BTI book, or tenant Shariah from **FI users**. Seed: `bti.shariah@…` (all FIs) and `shariah@…` (one FI). |
| Shariah must include the new desk | `/shariah` | Origination cases plus the desk audit list, not only Kenya applications. |
| Separate BTI users from FI users | `/users` | Super Admin: **BTI** and **FI users** books. BTI Ops lands on FI (they only invite FI Admin). FI Admin stays on one tenant directory. |

---

## 1. Portal chrome

The top bar uses the route title only (`Users`, `Origination`, `Shariah Audit`). How-to copy stays on the page and in the explainer, not under the navbar title.

---

## 2. API Client request, issue, and copy

```
FI Admin Request  →  status requested (Pending Super Admin)
Super Admin POST /institutions/{id}/api-keys  →  status issued
FI Admin (or Super Admin) POST .../api-keys/reveal { password }  →  copy panel
```

| Method | Path | Who | Returns |
|--------|------|-----|---------|
| GET | `/api/v1/institutions/{id}/api-keys/request` | Tenant session | `none` / `requested` / `issued`. Secrets omitted. `key_prefix` when issued. |
| POST | `/api/v1/institutions/{id}/api-keys/request` | FI Admin, Active FI only | Creates pending request. No-op if already requested. `400` if already issued. Super Admin must not use this (issue from Webhooks). |
| POST | `/api/v1/institutions/{id}/api-keys` | Super Admin | Issues `api_client` + HMAC. Stores `reveal_key` for later FI copy. |
| POST | `/api/v1/institutions/{id}/api-keys/reveal` | Signed-in user on that tenant | `{ "password": "…" }`. `401` without a session. `400` if password is wrong or nothing is issued. |

Keys created before `016` have no `reveal_key`. Super Admin re-issues from Webhooks so FI Admin can copy.

Portal: `SecretCopyPanel` on Institution profile, Webhooks, Institutions (after issue), and Dashboard.

---

## 3. Origination desk (eight gated steps)

New desk. Kenya `/kenya` is unchanged and stays hidden while the tester shell is on.

| Step | Title | Who | Gate |
|------|-------|-----|------|
| 1 | Origination + approval | FI Ops then assigned FI Approver | Document type, ID, amount (≥ 0), **profit**, **Commodity type** Airtime, pick FI Approver. Approver decides on this same screen. Approve emails `/customer/{ref}` |
| 3 | Initiate Tawarruq | FI Ops | Confirm purchase Yes. Locked after moving to step 4. Emails the journey |
| 4 | Murabaha Sale | FI Ops | Buyer (customer) and Seller (FI), facility account, installment count and due dates. Customer must accept the offer on their journey first |
| 5 | Commodity Resale | FI Ops | Current commodity owner, email, and phone. Emails the journey |
| 6 | Resale Proceeds | FI Ops | Customer CASA account and branch required. Emails the journey |
| 7 | Clearing | FI Ops | Settlement reference |
| 8 | Complete | FI Ops | Closes the case |

Home path: FI Ops and FI Approver → `/origination`. FI Approver only sees cases assigned to them.

### Desk API (`/api/v1/desk`)

| Method | Path | Who |
|--------|------|-----|
| GET | `/desk/approvers` | FI Ops (tenant) |
| GET / POST | `/desk/cases` | FI Ops creates. Approver lists assigned cases. Shariah may list |
| GET | `/desk/cases/{id}` | Tenant + assigned approver |
| POST | `/desk/cases/{id}/decide` | Assigned FI Approver `{ "decision": "approve" \| "return", "comments"? }` |
| POST | `/desk/cases/{id}/steps/{n}` | FI Ops, `n` 3–8, `{ "fields": {…} }` |
| GET | `/desk/audit` | `view_shariah` |

`fi_approver` write-block middleware allows `/desk/cases` and `/decide`.

OTP send/verify remain on the API but the Origination UI no longer uses them. Approve attaches the existing customer journey (`notify_offer_ready`). Later steps call `notify_step_ready` with the same `/customer/{ref}` link.

Table: `fi_desk_cases` (Alembic `017`).

---

## 4. Shariah Audit

`/shariah` stays on the tester nav for Super Admin, BTI Ops, FI Admin, and Shariah. It is hidden for FI Ops and FI Approver.

- Super Admin, BTI Ops, and **BTI-wide Shariah** (`institution_id` null): filter **All** or one institution.
- FI Admin and **FI Shariah** (tenant-bound): own institution only.
- Two trails: Kenya application ledger (possession seal + chain) and origination desk cases (`entity_type = fi_desk_case`) with timestamps.

Invite: Super Admin **BTI** book → Shariah / Audit (BTI-wide). Super Admin **FI users** or FI Admin → Shariah for that tenant. Same pattern as Recon.

Every desk write calls `log_shariah_step`.

---

## 5. Users: BTI book vs FI book

Invite rules did not change for FI Ops / FI Approver (Super Admin still cannot invite them). BTI Ops still invites FI Admin only on an **Active** FI. Super Admin can now invite **Shariah / Audit** and **Recon** on both books: BTI-wide (no institution) or one FI.

| Viewer | Users page |
|--------|------------|
| Super Admin | **BTI** (Super Admin, BTI Ops, BTI Finance, BTI-wide Shariah / Recon, and any login with no institution) and **FI users** (tenant-bound). Invite roles follow the open book. FI table shows Institution. `?institution=` opens the FI book. |
| BTI Ops | Same two books. Default is FI. No invite on BTI (they cannot create BTI staff). |
| FI Admin | One directory for their institution. Invite FI desk roles including tenant Shariah. |

Helpers: `isBtiManagedUser`, `inviteRoleOptionsForBook` in `portal/src/config/roles.ts`.

---

## 6. Tests

```powershell
$env:PYTHONPATH="src"
python -m pytest tests/test_fi_desk.py tests/test_institution_onboarding.py tests/test_invite_matrix.py tests/test_ops_login.py::test_shariah_officer_audit_at_bti_and_fi_level tests/test_ops_login.py::test_super_admin_sets_sedania_charge_pct -q
```

`test_fi_desk.py`: profit required on create, approve attaches journey and writes the offer mail file, Murabaha waits for customer accept (no desk OTP), proceeds account/branch, clearing seals **Complete**, Shariah audit rows, reveal requires a session password. Charge test: default 0.0035 / 0.004, second Sedania rate replaces the first, Bursa sets `active_provider`, password + OTP to save, FI Admin 403.

---

## 7. Not in this slice

| Item | Notes |
|------|--------|
| SMTP for invites and journey mail | Temp passwords and journey copies still file locally when `SMTP_HOST` is unset |
| Rewrite of Kenya Ops | Origination is a separate desk |
| Lift tester shell | Kenya, Approvals, Billing stay hidden until `TESTER_SHELL` is false. Bursa / Sedania show when Super Admin’s latest provider matches |
| Keys issued before `016` | No `reveal_key`; Super Admin re-issues |
| KYC file store / live PEP | Unchanged: text references and status enums |

---

## Source map

| Area | Files |
|------|--------|
| Navbar title only | `portal/src/components/AppLayout.tsx` |
| Copy / reveal UI | `portal/src/components/SecretCopyPanel.tsx` |
| Reveal + request | `src/tawarruq/api/routes_extended.py`, Alembic `016_api_key_reveal.py` |
| Desk | `src/tawarruq/services/fi_desk_service.py`, `api/routes_desk.py`, `models/fi_desk.py`, Alembic `017_fi_desk_cases.py` |
| Platform charges | `src/tawarruq/services/platform_settings_service.py`, Alembic `018_platform_settings.py`, `019_charge_pcts.py`, `020_provider_rates.py`, `portal/src/pages/SettingsPage.tsx` |
| Origination UI | `portal/src/pages/OriginationDeskPage.tsx`, `config/fiDesk.ts`, `DeskCaseListPage.tsx` |
| Shariah UI | `portal/src/pages/ShariahCompliancePage.tsx` |
| Users books | `portal/src/pages/UsersPage.tsx`, `config/roles.ts` |
| Tester nav | `TESTER_VISIBLE_PATHS` in `portal/src/config/roles.ts` |
| Tests | `tests/test_fi_desk.py` |
