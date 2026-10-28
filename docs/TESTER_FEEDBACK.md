# Tester and operator feedback (implemented)

Record of the FI tester / BTI Ops suggestions that are now in the engine and portal. Companion guides stay the source of truth for fields and runbooks: [FI_ONBOARDING.md](FI_ONBOARDING.md), [USERS_ACCESS_CONTROLS.md](USERS_ACCESS_CONTROLS.md), [SHARIAH_AUDIT.md](SHARIAH_AUDIT.md).

Kenya Ops was **not** rewritten. FI desk work is a new **Origination** page (`/origination`). SMTP invite mail is still later.

Schema: Alembic **`016`** (API key reveal) and **`017`** (`fi_desk_cases`). `TESTER_SHELL` stays on. Super Admin / BTI Ops / FI Admin see Dashboard, Onboard FI, Institutions, Users, Settings, Ops Monitor, Audit, Origination, and Shariah. **FI Ops** sees Origination, All Workflows, Settings. **FI Approver** sees Origination, Approval Queue, Settings. No Dashboard, Shariah, or Ops Monitor.

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
| FI Ops needs an eight-step desk | `/origination` | Gated wizard. First sidebar tab. FI Ops and FI Approver land here after login. |
| No Dashboard / Shariah / Ops for FI Ops | Sidebar | Those three are hidden for FI Ops and FI Approver. Login ignores a leftover `/users` URL and sends them to Origination. |
| Approval Queue for FI Approver | `/origination/queue` | Lists assigned requests. Filter by requesting officer, status, date requested. Open jumps to the desk. |
| All Workflows for FI Ops | `/origination/workflows` | Lists origination cases. Filter by customer, status, date. Open jumps to the desk. |
| Commodity type is Airtime only | Origination step 1 | Document type then ID. Amount cannot be negative. **Commodity type** is Airtime only. |
| Step 3 locks after Yes | Origination step 3 | After confirm, purchase complete cannot be changed. |
| Buyer / Seller and facility on Murabaha | Origination step 4 | Buyer (name, email, phone) and Seller (FI) first, then facility account, repayment installments, first and last installment due dates. |
| Current commodity owner on resale | Origination step 5 | Separate rows: owner, email, phone (from the customer). |
| CASA on Complete proceeds | Origination step 6 | Customer CASA account and branch are required. |
| Later steps wait for Approval | Origination step 2 | FI Ops picks an FI Approver and sends the case. That approver decides on the same page (not Kenya `/approvals`). |
| Customer OTP for tester-grade checks | Steps 4–6 | Send OTP (email when `SMTP_HOST` is set). If SMTP is off, the code is shown on screen. 10 minutes. Purposes: `murabaha`, `agent`, `casa`. |
| Every desk action must leave a Shariah trail | Shariah Audit | Each create / decide / step / OTP writes `log_shariah_step` with a timestamp. |
| Shariah Audit must be visible to testers | `/shariah` | Unhidden in the tester shell. Super Admin / BTI Ops: all institutions or one. FI roles: own tenant. |
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
| 1 | Origination | FI Ops | Document type, ID, amount (≥ 0), **Commodity type** Airtime, pick FI Approver |
| 2 | Approval | Assigned FI Approver | Approve or return. Other steps stay locked until approve |
| 3 | Initiate Tawarruq | FI Ops | Confirm purchase Yes. Locked after moving to step 4 |
| 4 | Murabaha Sale | FI Ops | Buyer (customer) and Seller (FI), facility account, installment count and due dates, OTP `murabaha` |
| 5 | Commodity Resale | FI Ops | Current commodity owner, email, and phone. OTP purpose `agent` |
| 6 | Resale Proceeds | FI Ops | OTP purpose `casa`. Customer CASA account and branch required |
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
| POST | `/desk/cases/{id}/steps/{n}` | FI Ops, `n` 1–8, `{ "fields": {…} }` |
| POST | `/desk/cases/{id}/otp/send` | FI Ops `{ "purpose": "murabaha" \| "agent" \| "casa" }` |
| POST | `/desk/cases/{id}/otp/verify` | FI Ops `{ "purpose", "code" }` |
| GET | `/desk/audit` | `view_shariah` |

`fi_approver` write-block middleware allows `/desk/cases` and `/decide`.

OTP: hashed, 10 minutes. When SMTP sends, `dev_code` is omitted. When SMTP is off, `dev_code` is in the send response and on the Origination page.

Table: `fi_desk_cases` (Alembic `017`).

---

## 4. Shariah Audit

`/shariah` stays on the tester nav for Super Admin, BTI Ops, FI Admin, and Shariah. It is hidden for FI Ops and FI Approver.

- Super Admin and BTI Ops: filter **All** or one institution.
- FI Admin / Shariah: own tenant only.
- Two trails: Kenya application ledger (possession seal + chain) and origination desk cases (`entity_type = fi_desk_case`) with timestamps.

Every desk write calls `log_shariah_step`.

---

## 5. Users: BTI book vs FI book

Invite rules did not change. Super Admin still cannot invite FI Ops or FI Approver. BTI Ops still invites FI Admin only on an **Active** FI.

| Viewer | Users page |
|--------|------------|
| Super Admin | **BTI** (Super Admin, BTI Ops, BTI Finance, and any login with no institution) and **FI users** (tenant-bound). Invite roles follow the open book. FI table shows Institution. `?institution=` opens the FI book. |
| BTI Ops | Same two books. Default is FI. No invite on BTI (they cannot create BTI staff). |
| FI Admin | One directory for their institution. Invite FI desk roles as before. |

Helpers: `isBtiManagedUser`, `inviteRoleOptionsForBook` in `portal/src/config/roles.ts`.

---

## 6. Tests

```powershell
$env:PYTHONPATH="src"
python -m pytest tests/test_fi_desk.py tests/test_institution_onboarding.py tests/test_invite_matrix.py -q
```

`test_fi_desk.py`: eight steps, Airtime-only product, OTP, proceeds account/branch, Shariah audit rows, reveal requires a session password.

---

## 7. Not in this slice

| Item | Notes |
|------|--------|
| SMTP for invites and OTP | Codes and temp passwords still show in the portal / API when `SMTP_HOST` is unset |
| Rewrite of Kenya Ops | Origination is a separate desk |
| Lift tester shell | Kenya, Malaysia, Approvals, Billing stay hidden until `TESTER_SHELL` is false |
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
| Origination UI | `portal/src/pages/OriginationDeskPage.tsx`, `config/fiDesk.ts` |
| Shariah UI | `portal/src/pages/ShariahCompliancePage.tsx` |
| Users books | `portal/src/pages/UsersPage.tsx`, `config/roles.ts` |
| Tester nav | `TESTER_VISIBLE_PATHS` in `portal/src/config/roles.ts` |
| Tests | `tests/test_fi_desk.py` |
