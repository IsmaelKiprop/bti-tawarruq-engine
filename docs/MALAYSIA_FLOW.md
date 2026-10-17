# Malaysia Tawarruq flow (Bursa Suq Al-Sila' and Eiger)

This is the partner-ready map for Malaysia commodity Murabaha. It matches the portal Malaysia track, Swagger, and the customer 8-step tracker.

Official references:

- [Bursa Suq Al-Sila' (BSAS)](https://www.bursamalaysia.com/trade/our_products_services/islamic_market/bursa_suq_al_sila)
- [Rules of Bursa Suq Al-Sila'](https://www.bursamalaysia.com/regulation/islamic_market/rules_of_bursa_suq_al_sila)
- [Eiger Trading Platform](https://www.eigertrading.com/site/eiger-trading-platform/)

## What is true about the partners

**BSAS** is a regulated, Shariah-governed commodity platform operated by Bursa Malaysia Islamic Services. Participants trade through the BSAS platform. There is no public commodity-trading API. Until Buruuj is admitted as a participant, the engine uses **manual_bridge**: Amanah writes a Bursa-shaped desk packet, ops send it to the BSAS desk, and ops paste the Islamic Services Receipt.

**Eiger** is a commodity Murabaha trading platform with trader, web, and API channels. Use it as the live commodity desk when the commercial path is Eiger rather than (or in addition to) Bursa. Paths are config-driven until Eiger issues the production contract.

## Modes

| Mode | When to use | How E2E works |
|------|-------------|---------------|
| `mock` | Local and CI | `POST /malaysia/applications/{id}/run-full-flow` or portal **Run mock E2E** |
| `manual_bridge` | Pre-admission Suq Al-Sila' | Portal **Start Suq Al-Sila' desk flow**, paste e-certificate per leg |
| `live` + `MALAYSIA_COMMODITY_DESK=bsas` | After BSAS connectivity is issued | `LiveBSASBackend` posts to `BSAS_LIVE_API_URL` |
| `live` + `MALAYSIA_COMMODITY_DESK=eiger` | After Eiger onboarding | `EigerTradingBackend` posts to `EIGER_API_URL` |

## Ops steps (same as portal)

1. Customer request  
2. Offer and acceptance  
3. Purchase instruction  
4. Commodity purchase (Leg 1)  
5. Purchase confirmation (e-certificate)  
6. Bank ownership confirmation  
7. Sale to customer  
8. Customer agency (Wakala)  
9. Sale instruction  
10. Commodity sale (Leg 3)  
11. Sale confirmation  
12. Disbursement and Tawarruq certificate  

Hard rules: Leg 1 confirmed before Leg 2. Customer sale and Wakala before Leg 3. All three legs confirmed before disbursement.

## Partner meeting checklist

Ask Bursa / BMIS:

1. Participant / member admission status and trading session hours  
2. Product codes (ACPO and others) and currency (MYR default)  
3. Whether connectivity is portal-only, FIX, or a private API  
4. Exact e-certificate fields they will return  
5. Who is the third-party buyer on Leg 3 (BMIS STB vs named counterparty)

Ask Eiger:

1. Sandbox URL, API key, and order/certificate paths  
2. STP vs batch vs individual transaction channel  
3. Certificate / ownership evidence format  
4. Which commodities they will book for Buruuj (metals, CPO, softs)

Set after the meeting:

```
MALAYSIA_COMMODITY_DESK=bsas   # or eiger
BSAS_LIVE_API_URL=
BSAS_LIVE_API_KEY=
EIGER_API_URL=
EIGER_API_KEY=
EIGER_ORDER_PATH=/v1/orders
EIGER_CERTIFICATE_PATH=/v1/certificates/{ref}
```

## Test locally today

1. Start API with `KENYA_INTEGRATION_MODE=mock`  
2. Portal `/malaysia` → **Run mock E2E**  
3. Or Swagger: create application → offer → accept → `POST /malaysia/applications/{id}/run-full-flow`  
4. For the real desk rehearsal: **Start Suq Al-Sila' desk flow** and paste three certificates  
5. `GET /health` shows `manual_bridge_ready`, `bsas_live_configured`, `eiger_configured`
