# Sedania AS SIDQ bank financing

Implements [BTI-TAWARRUQ FLOW FOR FINANCING - SEDANIA](BTI-TAWARRUQ%20FLOW%20FOR%20FINANCING%20-%20SEDANIA.pdf) (20 October 2026).

The bank buys telecommunication airtime on **AS SIDQ**. SEDANIA As Salam Capital is appointed **independently**. The bank credits **CASA**. Buruuj is the technology rail, not the wakeel.

## Flows

| Variant | `flow_variant` | Agency | After the independent sale |
|---------|----------------|--------|----------------------------|
| BTI Advisory approved | `approved_wakeel` | SASC as *wakeel* | Muqassah, then CASA credit |
| Proposed AAOIFI | `aaoifi_rasul` | SASC as *Rasul* | CASA credit (no muqassah) |

Delivery:

| `delivery_mode` | What happens |
|-----------------|--------------|
| `constructive` | Qabd hukmi, then SASC sells to random purchasers |
| `physical` | Customer keeps the commodity. After full settlement, SASC arranges qabd hakiki |

## Documents

1. Purchase Order
2. Commodity Invoice
3. Delivery Order
4. Trading e-Cert

Plus muqassah instruction, CASA credit advice, and physical-delivery notice when those steps run.

## API

```
POST /api/v1/sedania/financing
GET  /api/v1/sedania/financing
GET  /api/v1/sedania/financing/{id}
GET  /api/v1/sedania/financing/{id}/documents
GET  /api/v1/sedania/financing/{id}/documents/{kind}
POST /api/v1/sedania/financing/{id}/settle
POST /api/v1/sedania/financing/{id}/physical-delivery
```

Portal desk: `/sedania`. Super Admin sets **Sedania % Charge** (default **0.0035%**, range 0–100) on **Settings**. Changing it needs password and OTP. That percent is the default Murabahah charge when a facility does not send `profit_rate`. **BTI % Charge** is unique per FI (default **0.004%** for books already onboarded; set on Onboard → Commercial).

## SACCO path

`POST /api/v1/tawarruq/execute` still does not pay cash. It now appoints SASC independently and issues the same four trade documents. The SACCO CBS credits the member.

## Live Sedania

```
SEDANIA_MODE=live
SEDANIA_API_URL=
SEDANIA_API_KEY=
```

Mock is the default. Do not smash live Sedania without both `SEDANIA_API_URL` and `SEDANIA_API_KEY`.

### Spec vs this client

The financing PDF describes bank CASA / physical-delivery outcomes. The HTTP adapter in `src/tawarruq/integrations/sedania/client.py` posts Bearer JSON to invented paths on `SEDANIA_API_URL`:

| Engine method | Client path | Spec outcome |
|---------------|-------------|--------------|
| `purchase` | `POST /v1/trading/purchase` | Bank buy + qabd hukmi |
| `transfer_murabahah` | `POST /v1/trading/transfer-murabahah` | Murabahah transfer |
| `liquidate` | `POST /v1/trading/liquidate` | Independent sale |
| `arrange_physical_delivery` | `POST /v1/trading/physical-delivery` | qabd hakiki after settlement |

Those paths are the engine contract, not a published Sedania OpenAPI. Confirm them with Sedania before `SEDANIA_MODE=live`. Until then the mock client fills the same result shape.
