# Kenya float Tawarruq flow

Multi-tenant Kenya airtime/float financing aligned with Shariah Tawarruq structure. The engine enforces **correct step order** and **No-Inah** independence at liquidation.

The **customer tracker**, **Kenya Ops**, and **Swagger** all use the same eight steps:

| Step | Label | API |
|------|-------|-----|
| 1 | Facility Application and Agency Mandate | `POST /kenya/customers`, `POST /kenya/applications`, `POST .../eligibility` |
| 2 | Float Purchase Order (Leg 1) | `POST /kenya/transactions` then `POST .../purchase` **or** `POST .../agent-dealer-purchase` |
| 3 | Supplier Transfer and Constructive Possession | `POST /kenya/transactions/{id}/possession` |
| 4 | Murabahah Deferred Sale | `POST .../offer` → `accept` → `murabaha` → `sign` → `POST .../transfer` |
| 5 | Agency Activation (Wakala) | `POST /kenya/applications/{id}/wakala` |
| 6 | Spot Sale to Secondary Purchaser | `POST /kenya/transactions/{id}/liquidate` |
| 7 | Clearing and Settlement | `POST /kenya/applications/{id}/complete-settlement` |
| 8 | Cash Disbursement and Repayments | `POST /kenya/disbursements`, `GET .../repayments`, `POST /kenya/repayments/{id}/collect` |

Customer view: `GET /customer/applications/{ref}/journey`. Portal: `/customer/{ref}` and `/kenya`.

## Actors

| Actor | Role |
|-------|------|
| **Customer** | Requests financing via Expo app; accepts Murabaha; appoints Wakala |
| **Financier / Bank** | Institution tenant; buys commodity (Leg 1); holds constructive possession |
| **MNO** | Safaricom / Airtel — airtime/float purchase and possession confirmation |
| **Third-party broker** | Independent OTC desk — buys commodity at spot (Leg 3); never financier or MNO pool |
| **Platform (Buruuj)** | Engine + Amanah orchestration + Shariah audit |

The tables below list API sub-actions inside those eight steps.

## Phase 1: Purchase and possession (steps 1 to 3)

| Step | API | Shariah step | Notes |
|------|-----|--------------|-------|
| 1 | `POST /kenya/customers` + `POST /kenya/applications` | `FINANCING_REQUEST` | Customer registers; financing amount requested |
| 2 | `POST /kenya/applications/{id}/eligibility` | `ELIGIBILITY_CHECK` | Credit score, AML, KYC, liquidity pool |
| 3 | `POST /kenya/transactions` | `MURABAHA_PURCHASE` | Financier initiates MNO transaction |
| 4a | `POST /kenya/transactions/{id}/purchase` | — | Leg 1 — bulk airtime/float purchase |
| 4b | `POST /kenya/transactions/{id}/possession` | `CONSTRUCTIVE_POSSESSION` | MNO receipt ID + batch hash; **blocks Phase 2 until sealed** |

**Rule:** Murabaha offer endpoints return `400` until purchase leg is confirmed and possession is cryptographically sealed.

## Phase 2: Murabaha sale to customer (step 4)

| Step | API | Shariah step |
|------|-----|--------------|
| 5 | `GET /kenya/applications/{id}/offer` | — |
| 5 | `POST /kenya/applications/{id}/offer` | — |
| 6 | `POST /kenya/applications/{id}/accept` | — |
| 7 | `POST /kenya/applications/{id}/murabaha` | `MURABAHA_OFFER` |
| 7 | `POST /kenya/applications/{id}/murabaha/sign` | Customer acceptance logged |

Cost price = principal; profit margin and total deferred payment are on the offer.

## Phase 3: Liquidation and disbursement (steps 5 to 8)

| Step | API | Shariah step |
|------|-----|--------------|
| 8 | `POST /kenya/transactions/{id}/transfer` | `OWNERSHIP_TRANSFER` |
| 9 | `POST /kenya/applications/{id}/wakala` | `WAKALA_APPOINTMENT` |
| 10 | `POST /kenya/transactions/{id}/liquidate` | `THIRD_PARTY_LIQUIDATION` |
| 10 | `POST /kenya/applications/{id}/complete-settlement` | Transfer (if pending) + liquidate + disburse |
| 11 | (automatic on disburse) | `WALLET_DISBURSEMENT` |

### Wakala consent (required)

Customer must explicitly appoint the platform as agent **after** ownership transfer:

```json
POST /api/v1/kenya/applications/{id}/wakala
{
  "consent_ref": "WAKALA-CONSENT-001",
  "notes": "I appoint Buruuj as my agent to sell airtime to an independent broker"
}
```

`POST .../liquidate` returns `400` if Wakala is not recorded.

### No-Inah guardrail

Liquidation is blocked when the counterparty is:

- The financier institution (same code/id)
- The originating MNO entity (`SAFARICOM_MNO`, `AIRTEL_MNO`)
- Any broker flagged `is_mno_pool=true`
- Same code as the commodity
- A non-independent agency broker

Approved path uses seeded broker `OTC_KENYA` or a live broker API (`BROKER_LIQUIDATION_API_URL`).

## Phase 4: Repayment (step 8 continued)

| Step | API | Shariah step |
|------|-----|--------------|
| Schedule | Created on disburse | `REPAYMENT_SCHEDULED` |
| Collect | `POST /kenya/repayments/{id}/collect` | `REPAYMENT_RECEIVED` |

Installments use Murabaha `total_payable` divided by term. STK Push in live mode; mock marks paid synchronously.

## Mobile app mapping

The Expo app in `mobile/` implements the same sequence:

| Screen | Kenya steps |
|--------|-------------|
| Apply | 1 to 3 (register, eligibility, purchase, possession) |
| Offer | 4 (offer and accept) |
| Contract | 4 (murabaha and sign) |
| Settlement | 4 to 7 (transfer, Wakala, liquidate, complete-settlement) |
| Status / Repayments | 8 |

Set `EXPO_PUBLIC_API_URL` to your engine base (LAN IP on device).

## Amanah worker

When `AMANAH_ENABLED=true`, the worker:

1. Auto-creates MNO transactions after eligibility passes
2. Advances mock legs synchronously (purchase → possession → offer → murabaha → transfer → Wakala → liquidate → disburse)
3. In live mode, polls pending legs and waits for MNO/M-Pesa callbacks

## Mock one-click demo

Requires `KENYA_INTEGRATION_MODE=mock`:

```http
POST /api/v1/kenya/applications/{id}/run-full-flow
```

Runs all steps including Wakala consent ref `run-full-flow-wakala`.

## Status endpoint

```http
GET /api/v1/kenya/applications/{id}/status
```

Returns: `eligibility_passed`, `offer_accepted`, `murabaha_signed`, `wakala_appointed`, `wallet_credited`, transaction phase, installment counts.
