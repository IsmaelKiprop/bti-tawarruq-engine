# Live partner integrations

Kenya live mode calls Safaricom Daraja, MNO airtime partners, Airtel Money, and an independent OTC broker. Malaysia live mode calls a commodity desk (BSAS or Eiger). Local development stays on `KENYA_INTEGRATION_MODE=mock` and does not need these credentials.

Copy `.env.example` to `.env`. Per-institution values override the environment defaults from the ops portal (**Integrations**) or `PUT /api/v1/institutions/{id}/integrations`.

## Modes

| `KENYA_INTEGRATION_MODE` | Behaviour |
|--------------------------|-----------|
| `mock` | Synchronous demo. `run-full-flow` works. No partner calls. |
| `live` | Real Daraja, MNO, Airtel, and broker APIs. Results arrive on the callback URLs below. |

Set `PUBLIC_API_BASE_URL` to the public HTTPS origin partners can reach (ngrok is enough for a sandbox). The engine builds each institution's callback URLs from that origin, or from the institution's own `callback_base_url`.

```http
GET /api/v1/institutions/{id}/integrations/callback-urls
```

Register the returned URLs in that institution's Daraja and MNO portals. Paths look like:

| Partner event | Path |
|---------------|------|
| B2C result | `POST /api/v1/kenya/callbacks/{institution_id}/mpesa/b2c/result` |
| B2C timeout | `POST /api/v1/kenya/callbacks/{institution_id}/mpesa/b2c/timeout` |
| STK repayment | `POST /api/v1/kenya/callbacks/{institution_id}/mpesa/stk` |
| MNO possession | `POST /api/v1/kenya/callbacks/{institution_id}/mno/possession` |

If `CALLBACK_AUTH_TOKEN` is set, inbound callbacks must send it in `CALLBACK_AUTH_HEADER` (default `X-Callback-Token`).

## Secrets at rest

Generate a Fernet key and set `INTEGRATION_ENCRYPTION_KEY`. Institution secrets stored through the API are encrypted with that key.

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Keep the key stable. Rotating it without re-saving credentials makes stored secrets unreadable.

## M-Pesa (Daraja)

Register an app at the [Safaricom Daraja portal](https://developer.safaricom.co.ke/). Sandbox uses `MPESA_ENV=sandbox`; production uses `MPESA_ENV=production`.

| Variable | Use |
|----------|-----|
| `MPESA_CONSUMER_KEY` / `MPESA_CONSUMER_SECRET` | OAuth client credentials |
| `MPESA_SHORTCODE` | B2C shortcode (`PartyA`) |
| `MPESA_INITIATOR_NAME` | API initiator username |
| `MPESA_SECURITY_CREDENTIAL` | Initiator password already encrypted with Safaricom's public certificate (Daraja **Security Credential**). The engine sends this value as-is. |
| `MPESA_B2C_COMMAND_ID` | Default `BusinessPayment` |
| `MPESA_STK_PASSKEY` | STK Push passkey for repayment collection |
| `MPESA_B2C_RESULT_URL` / `MPESA_B2C_TIMEOUT_URL` | Optional global fallbacks. Prefer the per-institution URLs from the callback builder. |
| `MPESA_STK_CALLBACK_URL` | STK callback fallback |

B2C pays the customer wallet. STK Push collects installment repayments.

## Safaricom airtime

| Variable | Use |
|----------|-----|
| `MNO_SAFARICOM_API_URL` | Partner airtime API base |
| `MNO_SAFARICOM_API_KEY` | Partner API key |
| `MNO_SAFARICOM_DEALER_CODE` | Dealer code on purchase requests |
| `MNO_POSSESSION_CALLBACK_URL` | Where the MNO posts constructive-possession confirmation |

## Airtel Kenya

Airtime purchase and Airtel Money disbursement share one OAuth client.

| Variable | Use |
|----------|-----|
| `MNO_AIRTEL_API_URL` | Airtel API base |
| `MNO_AIRTEL_TOKEN_URL` | OAuth token URL |
| `MNO_AIRTEL_CLIENT_ID` / `MNO_AIRTEL_CLIENT_SECRET` | OAuth client |

Airtel Money is used only when all four values are set.

## Independent broker (No-Inah)

Liquidation must go to a party that is not the financier and not the originating MNO pool. Point this at that OTC desk:

| Variable | Use |
|----------|-----|
| `BROKER_LIQUIDATION_API_URL` | Broker order API |
| `BROKER_LIQUIDATION_API_KEY` | Broker API key |

## Malaysia commodity desk

`MALAYSIA_COMMODITY_DESK` is `bsas` (default) or `eiger`.

| Desk | Variables |
|------|-----------|
| BSAS | `BSAS_LIVE_API_URL`, `BSAS_LIVE_API_KEY` |
| Eiger | `EIGER_API_URL`, `EIGER_API_KEY`, `EIGER_ORDER_PATH`, `EIGER_CERTIFICATE_PATH` |

Before those APIs are live, use transaction `mode: manual_bridge`. Ops copies the request packet, trades on the desk, and pastes the e-certificate back. See [docs/LOCAL_TEST.md](docs/LOCAL_TEST.md).

## Outbound webhooks

Institutions can register their own event URLs with `POST /api/v1/webhooks`. Deliveries are signed. Timeout and retry are `WEBHOOK_TIMEOUT_SECONDS` and `WEBHOOK_MAX_RETRIES`.
