# Buruuj Lend — complete mobile app

Timiza-style Shariah lending for Kenya with high-security email auth and **institution approval** before borrowing.

## Hybrid onboarding (required)

1. Customer **self-registers** (email + strong password + MFA)
2. Status stays **pending** until the institution acts
3. Institution either:
   - **Invites** by email (ops portal → Mobile Lend), customer claims `BL-…` code, and/or
   - **Approves** the pending account (phone + credit limit + KYC/AML clear)
4. Only then: `can_borrow=true`, limit unlocks, **Get financing** works

Buruuj Fintech is the platform operator. The **client bank/SACCO** owns the customer and liquidity.

## What is included

| Area | Features |
|------|----------|
| Auth | Register, email verify, login MFA, forgot/reset password, change password |
| Approval | Pending / approved / rejected · invite claim · ops activate |
| Main tabs | Home · My loan · Account |
| Lending | Apply → Offer → Sign → Auto-disburse → Success |
| Servicing | Status + STK repayments |
| Ops portal | **Mobile Lend** page: invite + approve queue |

## Run

```powershell
# Engine
cd bti-tawarruq-engine
.venv\Scripts\Activate.ps1
python -m tawarruq.cli serve --host 0.0.0.0 --port 8000

# Portal (approve borrowers)
cd portal
npm install
npm run dev

# Mobile
cd mobile
npm install
$env:EXPO_PUBLIC_API_URL="http://<your-lan-ip>:8000/api/v1"
npx expo start
```

## Demo path

1. Register + verify in the app (use `dev_code` when SMTP is off)
2. Sign in with MFA
3. Home shows **Awaiting institution approval**
4. Portal → **Mobile Lend** → Approve with `254…` phone and limit  
   (or create invite → Account → Claim `BL-…`)
5. Reload app Home → limit appears → **Get financing**

## Smoke (engine)

```powershell
python scripts/smoke_mobile_hybrid.py
```

Uses a temporary institution API key when `AUTH_ENABLED=true`.

## Auth notes

- Password: 12+ chars with upper, lower, number, symbol
- MFA email code on every login
- Without SMTP, API returns `dev_code` and files mail under `data/customer_mail/`
- Ops approve/invite: portal session or `X-API-Key` (institution admin/ops)
