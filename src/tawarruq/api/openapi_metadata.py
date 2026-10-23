API_DESCRIPTION = """
## Buruuj Fintech Tawarruq-as-a-Service Engine

Multi-tenant Islamic finance engine for **Tawarruq** commodity financing (Malaysia BSAS, Kenya MNO float, and SACCO / Sedania As-Sidq execute),
**Amanah** AI orchestration, **No-Inah** guardrails, and **Shariah** append-only audit logging.

---

### Sedania bank financing (AS SIDQ, BTI Advisory deck 20 Oct 2026)

Approved flow (`flow_variant=approved_wakeel`): SASC is independent *wakeel*, then **muqassah**, then the bank credits **CASA**.

Proposed AAOIFI flow (`flow_variant=aaoifi_rasul`): SASC is *Rasul* (messenger), no muqassah, then the bank credits CASA.

Physical delivery (`delivery_mode=physical`): customer keeps the commodity. After full settlement, SASC arranges *qabd hakiki* with the supplier.

| Step | Action | API |
|------|--------|-----|
| 1 | Apply, sign CMP, appoint SASC | `POST /sedania/financing` |
| 2–5 | Purchase, qabd hukmi, Murabahah, trade pack | Engine calls Sedania `/v1/trading/purchase` and `/transfer-murabahah` |
| 6 | Independent sale (unless physical) | Sedania `/v1/trading/liquidate` |
| 7 | Muqassah (approved wakeel only) | Vaulted set-off instruction |
| 8 | Bank credits CASA | Vaulted CASA credit advice |
| * | Physical delivery after settlement | `POST /sedania/financing/{id}/settle` then `.../physical-delivery` |
| * | Documents | `GET /sedania/financing/{id}/documents/{kind}` |

Trade pack: Purchase Order, Commodity Invoice, Delivery Order, Trading e-Cert.

---

### SACCO execute path (Mwalimu CBS → Buruuj → Sedania)

This is the inbound facility contract. The SACCO already pre-approved the member. Buruuj does **not** pay out cash.

| Step | Initiator | Receiver | API |
|------|-----------|----------|-----|
| 1 | SACCO CBS | Buruuj | `POST /tawarruq/execute` (`customer_id`, `amount`, `tenor`) signed with API key + HMAC |
| 2 | Buruuj token engine | Internal | Signs Wa'd and Wakalah stamps |
| 3–8 | Buruuj | Sedania As-Sidq | `POST /v1/trading/purchase`, `/transfer-murabahah`, `/liquidate` (Sedania returns certificates 1–3) |
| 9 | Buruuj | SACCO CBS | Signed webhook `tawarruq.certificates_ready` with the three vault URLs |
| 10 | SACCO CBS | Member | Cash disbursement on the SACCO ledger / M-Pesa. **Buruuj never handles principal.** |

HMAC: `X-BTI-Timestamp` (unix seconds) and `X-BTI-Signature` = `HMAC-SHA256(hmac_secret, "{timestamp}.{raw_body}")`. The HMAC secret is shown once when the API key is created.

Certificate payloads are vaulted for 7 years: `GET /tawarruq/certificates/{id}?token=...`

---

### Malaysia standard flow (BSAS, 12 ops steps)

Matches the portal Malaysia track. The customer tracker collapses this into eight labels.

| Step | Action | API |
|------|--------|-----|
| 1 | Customer request | `POST /applications` |
| 2 | Offer and acceptance | `POST /applications/{id}/offer` then `.../accept` |
| 3 | Purchase instruction | `POST /transactions` (`mode`: mock / manual_bridge / live) |
| 4 | Commodity purchase (Leg 1) | `POST /transactions/{id}/legs/purchase` |
| 5 | Purchase confirmation | `POST /transactions/{id}/legs/1/confirm` (manual bridge: paste e-certificate) |
| 6 | Bank ownership confirmation | Engine records title after Leg 1 confirm |
| 7 | Sale to customer | `POST /applications/{id}/customer-sale` |
| 8 | Customer agency (Wakala) | `POST /applications/{id}/customer-agency` |
| 9 | Sale instruction | `POST /manual-bridge/transactions/{id}/advance` (or live sale) |
| 10 | Commodity sale (Leg 3) | `POST /transactions/{id}/legs/sale` |
| 11 | Sale confirmation and funds | `POST /transactions/{id}/legs/3/confirm` |
| 12 | Disbursement and certificate | `POST /disbursements` |
| * | Shariah audit | `GET /applications/{id}/shariah-audit` |

**Desk modes:** `mock` (one-click `POST /malaysia/applications/{id}/run-full-flow`), `manual_bridge` (Suq Al-Sila' desk packet + e-certificate), `live` with `MALAYSIA_COMMODITY_DESK=bsas|eiger`.

Bursa Suq Al-Sila' has no public trading API. Manual bridge is the standard path until participant connectivity is issued. Eiger is the alternative API desk after onboarding.

**Manual bridge ops path** (pre-live Malaysia):

| Step | Action | API |
|------|--------|-----|
| 1 | Create app + offer + accept | Standard Malaysia steps |
| 2 | Start txn in manual mode | `POST /transactions` with `"mode": "manual_bridge"` |
| 3 | Generate BSAS request packet | `POST /manual-bridge/transactions/{id}/advance` |
| 4 | View pending inbox | `GET /manual-bridge/pending` |
| 5 | Read request packet | `GET /manual-bridge/transactions/{id}/legs/{{1|2|3}}` |
| 6 | Trade on BSAS portal / bank desk | Off-platform |
| 7 | Paste e-certificate | `POST /transactions/{id}/legs/{n}/confirm` |
| 8 | Repeat for legs 2–3, then disburse | Advance → confirm → `POST /disbursements` |

---

### Kenya float Tawarruq (8 customer steps)

These are the same eight steps shown on `/customer/{ref}` and Kenya Ops. Call the APIs in this order. The engine rejects out-of-order steps.

**Hard rules:** Step 3 possession **before** step 4 Murabaha. Step 5 Wakala **before** step 6 liquidation.

| Step | Customer / ops label | API |
|------|----------------------|-----|
| **1** | Facility Application and Agency Mandate | `POST /kenya/customers` → `POST /kenya/applications` → `POST .../eligibility` or `POST .../eligibility/decision` |
| **2** | Float Purchase Order (Leg 1) | `POST /kenya/transactions` then `POST .../purchase` **or** `POST .../agent-dealer-purchase` |
| **3** | Supplier Transfer and Constructive Possession | `POST /kenya/transactions/{id}/possession` |
| **4** | Murabahah Deferred Sale (offer, contract, Leg 2) | `POST .../offer` → `.../accept` → `.../murabaha` → `.../murabaha/sign` → `POST .../transfer` |
| **5** | Agency Activation (Wakala) | `POST /kenya/applications/{id}/wakala` |
| **6** | Spot Sale to Secondary Purchaser (Leg 3, No-Inah) | `POST /kenya/transactions/{id}/liquidate` |
| **7** | Clearing and Settlement | `POST /kenya/applications/{id}/complete-settlement` |
| **8** | Cash Disbursement and Repayments | `POST /kenya/disbursements` then `GET .../repayments` / `POST /kenya/repayments/{id}/collect` |

**Customer tracker:** `GET /customer/applications/{ref}/journey` returns these eight steps with status `done` / `active` / `pending`.

**Step 2 supply:** use the MNO path, or register float on `Kenya Agent Dealers` and call `agent-dealer-purchase`. Mock full run: `POST /kenya/applications/{id}/run-full-flow` (`KENYA_INTEGRATION_MODE=mock`).

**Status:** `GET /kenya/applications/{id}/status` reports eligibility, offer, Murabaha, Wakala, wallet, and installments.

---

### Shariah audit (immutable ledger)

| Action | API |
|--------|-----|
| Application trail | `GET /kenya/applications/{id}/shariah-audit` |
| Verify integrity | `GET /kenya/applications/{id}/shariah-audit/verify` |
| Verify hash chain | `GET /kenya/shariah-audit/verify-chain` |
| Regulatory export | `GET /kenya/shariah-audit/export?format=csv` |

Optional Python microservice mirror: set `SHARIAH_AUDIT_SERVICE_URL` (see docs/SHARIAH_AUDIT.md).

---

### No-Inah guardrail

Liquidation is blocked if the broker is the financier, the originating MNO pool, or any `is_mno_pool` entity.
Approved path: independent OTC broker (`OTC_KENYA` seed) or live `BROKER_LIQUIDATION_API_URL`.

---

### Live integrations

| Component | Env / callback |
|-----------|----------------|
| M-Pesa B2C + STK | Daraja — `Kenya Callbacks` tag |
| Safaricom / Airtel airtime | MNO partner API + possession webhook |
| Airtel Money disburse | Same Airtel OAuth as airtime |
| Broker liquidation | `BROKER_LIQUIDATION_API_URL` |

Per-institution credentials: `Institution Integrations` tag. See INTEGRATIONS.md.

---

### Authentication

Set `AUTH_ENABLED=true` and pass `X-API-Key` (machine) or `Authorization: Bearer` (ops session). Default local dev: auth off.

In Swagger (`/docs`): `POST /ops/auth/login` → copy `access_token` → **Authorize** → BearerAuth. Change password first if `must_change_password` is true, then Authorize with the new token.

**Portal invites** (`POST /ops/auth/users`): only Super Admin (`platform_admin`) and FI Admin (`institution_admin`) may create users. Super Admin may invite Super Admin, BTI Ops, BTI Finance, FI Admin, FI Operations, FI Approver, Shariah / Audit, and Reconciliation. FI Admin may invite FI Admin, FI Operations, FI Approver, Shariah / Audit, and Reconciliation for their own tenant — not BTI-internal roles. The same rules apply to `PATCH` role.

**API keys** (`POST /institutions/{id}/api-keys`): Super Admin only. FI Admin cannot issue keys; request BTI to onboard. Preferred machine role is `api_client`.

---

### Swagger quick test (Kenya mock)

1. `GET /health` — confirm `kenya_integration_mode: mock`
2. `POST /kenya/customers` → `POST /kenya/applications`
3. `POST /kenya/applications/{id}/run-full-flow` — full synchronous demo
4. `GET /kenya/applications/{id}/shariah-audit/verify` — expect `valid: true`
"""

OPENAPI_TAGS = [
    {
        "name": "Health",
        "description": "Engine health, Amanah mode, and Kenya integration readiness flags.",
    },
    {
        "name": "Institutions",
        "description": "Banks/Saccos. Each tenant has BSAS mode, API keys (Super Admin creates keys), and integration profile.",
    },
    {
        "name": "Applications",
        "description": "Malaysia financing requests, business steps 7–8, and Shariah audit per application.",
    },
    {
        "name": "Transactions",
        "description": "Malaysia 3-leg commodity transactions (purchase → transfer → sale).",
    },
    {
        "name": "Disbursements",
        "description": "Malaysia final payout after all legs confirmed.",
    },
    {
        "name": "Malaysia Manual Bridge",
        "description": "Pre-live Malaysia BSAS path: generate request packets for the BSAS portal / bank commodity desk, list pending e-certificate paste work, and advance legs.",
    },
    {
        "name": "Audit",
        "description": "Operational append-only audit log and CSV export.",
    },
    {
        "name": "Webhooks",
        "description": "Outbound signed webhooks to institution callback URLs.",
    },
    {
        "name": "Institution Integrations",
        "description": "Per-tenant Daraja M-Pesa, Safaricom/Airtel MNO, and callback URL builder.",
    },
    {
        "name": "Kenya Ops",
        "description": "Bank ops workbench: case queues, possession desk, Wakala, repayments, broker/No-Inah view.",
    },
    {
        "name": "Customer Portal",
        "description": "Public customer tracker. `GET /customer/applications/{ref}/journey` returns the same eight Kenya (or Malaysia) steps the ops portal shows, plus certificates.",
    },
    {
        "name": "Kenya Agent Dealers",
        "description": "Float pools used for Kenya step 2 when Leg 1 is an Agent Dealer purchase. Register dealers, top up float, then call `POST /kenya/transactions/{id}/agent-dealer-purchase`.",
    },
    {
        "name": "Kenya MNO Flow",
        "description": "Kenya Tawarruq in eight steps: (1) apply and eligibility, (2) float purchase via MNO or Agent Dealer, (3) constructive possession, (4) Murabaha offer/contract/Leg 2, (5) Wakala consent, (6) No-Inah liquidation, (7) clearing, (8) wallet + repayments. Includes Shariah verify/export and `run-full-flow` mock demo.",
    },
    {
        "name": "Kenya Callbacks",
        "description": "Inbound Daraja B2C/STK and MNO possession webhooks (global + per-institution paths).",
    },
    {
        "name": "Sedania Financing",
        "description": "Bank Commodity Murabahah through AS SIDQ. Approved wakeel + muqassah + CASA, or AAOIFI Rasul, or physical delivery (qabd hakiki).",
    },
    {
        "name": "SACCO Execute",
        "description": "Inbound SACCO CBS facility request. Stamps Wa'd/Wakalah, trades through Sedania As-Sidq, vaults certificates for 7 years, and webhooks the SACCO. Buruuj never disburses principal cash.",
    },
    {
        "name": "Production Ops",
        "description": "Portal login, MFA, user invites (who may create whom), operational metrics, and Prometheus `/metrics`.",
    },
]
