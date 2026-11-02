# Sedania AS SIDQ bank financing

Implements [BTI-TAWARRUQ FLOW FOR FINANCING - SEDANIA](BTI-TAWARRUQ%20FLOW%20FOR%20FINANCING%20-%20SEDANIA.pdf) (20 October 2026) on the desk, and [AsSidq Tawarruq 2.0_API Specifications Document.pdf](AsSidq%20Tawarruq%202.0_API%20Specifications%20Document.pdf) (v2.1, 30 July 2026) on the wire.

The bank buys telecommunication airtime on **AS SIDQ**. SEDANIA As Salam Capital is appointed **independently**. The bank credits **CASA**. Buruuj is the technology rail, not the wakeel.

## As-Sidq HTTP contract

| Spec | Engine |
|------|--------|
| `POST /api/v1/trading` | Submit one commodity trade (`ref_no`, `cust_name`, `cust_id`, `trading_amount`, `profit_amount` or `selling_price`, `product_code`, `keep_commodity`) |
| Trading Callback API | `POST /api/v1/sedania/callback` — Sedania POSTs the final outcome here |
| `GET /api/v1/trading/status?ref_no=` | Desk **Refresh As-Sidq status** |
| `POST /api/v1/cancellation/request` | Desk **Cancel on As-Sidq** |
| Certificate URL `/api/v1/streamPdf?...` | Downloaded after callback; password `{SEDANIA_INSTITUTION_PREFIX}@{ref_no}` |

HTTP 200 on submit means **accepted**, not completed. Final outcome is `status_code` on the callback: 200 COMPLETE, 203 KEEP, 400 CANCELED, 500 FAILED. Duplicate `ref_no` is 422 — recover with Get Status, never a new reference.

Optional: `X-Req-Signature` (Base64 SHA-256 of the JSON body) when `SEDANIA_SIGN_REQUESTS=true`. Optional AES-256-CBC on `cust_name` / `cust_id` when `SEDANIA_ENCRYPT_CUSTOMER=true`.

UAT base URL from the spec: `https://twq-uat.assidqlink.com`. Set it on `SEDANIA_API_URL`. Do not set `SEDANIA_MODE=live` without `SEDANIA_API_KEY`. Mock is the default and still completes in one desk click.

## Flows

| Variant | `flow_variant` | Agency | After the independent sale |
|---------|----------------|--------|----------------------------|
| BTI Advisory approved | `approved_wakeel` | SASC as *wakeel* | Muqassah, then CASA credit |
| Proposed AAOIFI | `aaoifi_rasul` | SASC as *Rasul* | CASA credit (no muqassah) |

Delivery:

| `delivery_mode` | As-Sidq `keep_commodity` | What happens |
|-----------------|--------------------------|--------------|
| `constructive` | `N` | Callback COMPLETE. SASC sold independently. Bank credits CASA. |
| `physical` | `Y` | Callback KEEP. Customer keeps the commodity. After full settlement, SASC arranges qabd hakiki (no As-Sidq physical-delivery API). |

## Documents

1. Purchase Order
2. Commodity Invoice
3. Delivery Order
4. Trading e-Cert
5. As-Sidq master certificate (password-protected PDF when live)

Plus muqassah instruction, CASA credit advice, and physical-delivery notice when those steps run. Cert A / B / C from the callback are vaulted as purchase / Murabahah / liquidation.

## API

```
POST /api/v1/sedania/financing
GET  /api/v1/sedania/financing
GET  /api/v1/sedania/financing/{id}
GET  /api/v1/sedania/financing/{id}/documents
GET  /api/v1/sedania/financing/{id}/documents/{kind}
POST /api/v1/sedania/financing/{id}/status
POST /api/v1/sedania/financing/{id}/cancel
POST /api/v1/sedania/financing/{id}/settle
POST /api/v1/sedania/financing/{id}/physical-delivery
POST /api/v1/sedania/callback
```

Portal desk: `/sedania`. Super Admin sets **Sedania % Charge** (default **0.0035%**, range 0–100) on **Settings**. Changing it needs password and OTP. That percent is the default Murabahah charge when a facility does not send `profit_rate`. **BTI % Charge** is unique per FI (default **0.004%** for books already onboarded; set on Onboard → Commercial).

Register the public callback with Sedania:

`https://ops.buruujfintech.com/api/v1/sedania/callback`

If `SEDANIA_CALLBACK_TOKEN` is set, Sedania must send it as `X-Callback-Token` or `Authorization: Bearer`. Leave it empty if they cannot.

## SACCO path

`POST /api/v1/tawarruq/execute` submits the same As-Sidq Trading API, then relays vault URLs to the SACCO CBS. The SACCO CBS credits the member.

## Live Sedania

```
SEDANIA_MODE=mock
SEDANIA_API_URL=https://twq-uat.assidqlink.com
SEDANIA_API_KEY=
SEDANIA_PRODUCT_CODE=P01
SEDANIA_INSTITUTION_PREFIX=BTI
SEDANIA_SIGN_REQUESTS=false
SEDANIA_ENCRYPT_CUSTOMER=false
SEDANIA_AES_KEY=
SEDANIA_CALLBACK_TOKEN=
```

Mock is the default. Do not smash live Sedania without both `SEDANIA_API_URL` and `SEDANIA_API_KEY`.
