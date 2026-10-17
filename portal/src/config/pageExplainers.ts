export type PageExplainContent = {
  title: string;
  lead: string;
  dealTitle: string;
  dealSteps: string[];
  note?: string;
};

export type HowItWorksContent = {
  title: string;
  intro: string;
  steps: { n: number; title: string; body: string }[];
  note?: string;
};

export const PAGE_EXPLAINS: Record<string, PageExplainContent> = {
  "/": {
    title: "What this dashboard is",
    lead: "This is the control tower for both Tawarruq tracks. It is not a cash-loan book. Kenya uses float. Malaysia uses crude palm oil on Suq Al-Sila'.",
    dealTitle: "How a deal uses it",
    dealSteps: [
      "Check the engine is online and which desk is configured.",
      "Read the book numbers: amount is commodity cost, Murabaha is what the customer owes.",
      "Open an active journey, or jump to Kenya Ops or Malaysia Manual Bridge.",
      "Setup pages (institutions, users, integrations) must exist before a live deal.",
    ],
    note: "Book Murabaha here is a 5% preview until each offer locks on the application.",
  },
  "/ops": {
    title: "What Ops Monitor is",
    lead: "Telemetry for the engine itself: who you are, request volume, and errors. It does not run a commodity leg.",
    dealTitle: "How a deal uses it",
    dealSteps: [
      "Confirm your role and institution scope before you troubleshoot.",
      "Watch pending manual-bridge e-certificates and HTTP errors.",
      "Open an active application from the list, then finish it on the track desk.",
    ],
    note: "A red counter means work is waiting, not that a trade has settled.",
  },
  "/customer": {
    title: "What the customer journey is",
    lead: "The same steps the customer sees. Kenya has eight. Malaysia has twelve. Certificates sit on the completed legs.",
    dealTitle: "How a deal uses it",
    dealSteps: [
      "Look up the application reference or phone.",
      "Read cost and Murabaha. That is what they owe, not the float or palm oil.",
      "The customer accepts the Murabaha and signs on this page. Ops cannot do that.",
    ],
    note: "This page can be opened without a portal login. Do not put internal notes here.",
  },
  "/customers": {
    title: "What a customer is",
    lead: "The financing beneficiary on an institution book. Step 1 starts here. Do not register the same person again on New case or New application.",
    dealTitle: "How a deal uses it",
    dealSteps: [
      "Register name, email, phone, wallet, KYC, AML, and score on the correct institution.",
      "Open the row. Attach or start an application from this record.",
      "When the offer locks, the engine emails the accept link. You can still copy the journey link.",
    ],
    note: "Score is institution-entered (0 to 900). Eligibility fails below 500. AML is the bank or SACCO status.",
  },
  "/mobile-lend": {
    title: "What Mobile Lend approval is",
    lead: "App users self-register with email MFA, then your institution must invite and/or approve them before they can borrow.",
    dealTitle: "How activation works",
    dealSteps: [
      "Invite a member by email (optional), or wait for a self-registered pending account.",
      "Approve with phone + credit limit. This sets KYC verified and AML clear on the customer book.",
      "Only then does Buruuj Lend unlock Get financing for that account.",
    ],
    note: "Auto-activate on claim is for members already KYC'd offline. Default path is pending until you Approve.",
  },
  "/institutions": {
    title: "What an institution is",
    lead: "A client bank or SACCO on Buruuj's engine. Buruuj Fintech is the operator, not a row here. Customers, users, and deals are scoped to an institution.",
    dealTitle: "How a deal uses it",
    dealSteps: [
      "Register the bank with a name, unique code, and Malaysia desk mode.",
      "Open Integrations for its partner credentials, then create its admin on Users.",
      "Every application and commodity leg then stays on that tenant.",
    ],
    note: "DEFAULT is the demo book and cannot be deleted. Kenya float uses Integrations, not the Malaysia desk field.",
  },
  "/users": {
    title: "What a user is",
    lead: "A portal login. Platform admin is Buruuj and sees all institutions. Other roles stay on one bank or SACCO.",
    dealTitle: "How a deal uses it",
    dealSteps: [
      "Pick the narrowest role that still lets them work.",
      "Copy the temporary password once and send it on a secure channel.",
      "They must change it before they can open Kenya Ops or Malaysia.",
    ],
    note: "Portal people use email login. API keys on Webhooks are for machines.",
  },
  "/integrations": {
    title: "What integrations are",
    lead: "Per-institution partner credentials for M-Pesa, the mobile networks, and callbacks. This is how Kenya buys float.",
    dealTitle: "How a deal uses it",
    dealSteps: [
      "Select the institution.",
      "Set Kenya mode and partner secrets. Leave a field blank to keep the current secret.",
      "Register the generated callback URLs in the partner portal.",
      "Kenya step 2 then buys from the MNO or drains an Agent Dealer pool.",
    ],
    note: "Configured means credentials are present, not that a live trade has been proven.",
  },
  "/webhooks": {
    title: "What webhooks and keys are",
    lead: "Machine access for a SACCO CBS. Issue an API key plus HMAC secret, then receive tawarruq.certificates_ready when execute finishes.",
    dealTitle: "How a deal uses it",
    dealSteps: [
      "Create an API key for the SACCO. Copy the key and the HMAC secret once.",
      "Register POST /api/tawarruq/callback on the SACCO, or a webhook URL here.",
      "The CBS calls POST /tawarruq/execute. Buruuj relays the three certificate URLs. The SACCO pays the member.",
    ],
    note: "Buruuj never disburses SACCO principal cash. HMAC is X-BTI-Signature over timestamp plus body.",
  },
  "/agent-dealers": {
    title: "What the dealer pool is",
    lead: "Dealer A's available float for Kenya step 2. Float is M-Pesa or Airtel e-value, the commodity, not cash in a current account.",
    dealTitle: "How a deal uses it",
    dealSteps: [
      "Ops register the dealer at zero float, then issue an Agent dealer login.",
      "Only that dealer login can add float and edit their business details. Bank and platform ops cannot add float.",
      "When a dealer is active, Kenya Leg 1 drains this pool instead of a live MNO buy.",
    ],
    note: "The customer never keeps this float. They repay the Murabaha after the independent sale.",
  },
  "/repayments": {
    title: "What a repayment is",
    lead: "A Murabaha instalment after disbursement. The customer is paying cost plus profit, not buying the float or palm oil again.",
    dealTitle: "How a deal uses it",
    dealSteps: [
      "Wait until the wallet or cash has been disbursed.",
      "Collect the due instalment. Overdue rows need follow-up.",
      "Paid rows stay on the board for the audit trail.",
    ],
    note: "Schedules appear only after payout. Collect from this board or from Kenya Ops step 8.",
  },
  "/transactions": {
    title: "What a transaction is",
    lead: "The commodity side of one application: three legs, certificates, and settlement. Not the customer book.",
    dealTitle: "How a deal uses it",
    dealSteps: [
      "Leg 1 buys the commodity (float or palm oil).",
      "Leg 2 transfers title to the customer after Murabaha.",
      "Leg 3 sells to an independent buyer. Then disburse.",
    ],
    note: "Open a row for certificates. Kenya No-Inah blocks sale back to the same dealer or MNO pool.",
  },
  "/shariah": {
    title: "What the Shariah ledger is",
    lead: "The append-only evidence chain for both tracks. Possession seals, certificates, and hashes sit here.",
    dealTitle: "How a deal uses it",
    dealSteps: [
      "Pick the institution and verify the hash chain.",
      "Open a case to see the step ledger and possession seal.",
      "Export CSV or JSON for a Shariah board or auditor.",
    ],
    note: "Rows cannot be edited or deleted. Application delete does not remove the chain.",
  },
};

export const HOW_IT_WORKS: Record<string, HowItWorksContent> = {
  "/": {
    title: "How the dashboard works",
    intro: "Use this page to see the book, then leave it to run the desk.",
    steps: [
      { n: 1, title: "Check health", body: "Engine online, Kenya partners, Malaysia desk mode." },
      { n: 2, title: "Read the book", body: "Cost and Murabaha totals by currency." },
      { n: 3, title: "Open a journey", body: "Customer tracker, Kenya Ops, or Malaysia bridge." },
    ],
    note: "Do not skip possession or Wakala from here. The desks enforce the order.",
  },
  "/ops": {
    title: "How Ops Monitor works",
    intro: "Read counters, then open the desk that owns the work.",
    steps: [
      { n: 1, title: "Confirm who you are", body: "Role and permissions gate every API call." },
      { n: 2, title: "Watch the queues", body: "Pending e-certs and HTTP errors." },
      { n: 3, title: "Open the case", body: "Applications list, Kenya Ops, or Malaysia." },
    ],
  },
  "/customer": {
    title: "How the tracker works",
    intro: "Lookup, then follow only the active step.",
    steps: [
      { n: 1, title: "Find the deal", body: "Reference or phone." },
      { n: 2, title: "Read the numbers", body: "Cost, profit, Murabaha." },
      { n: 3, title: "Follow the step", body: "Certificates appear when a leg confirms." },
    ],
  },
  "/customers": {
    title: "How the customer book works",
    intro: "One person, one record, then applications attach to it.",
    steps: [
      { n: 1, title: "Register", body: "Name, phone, wallet, KYC, AML, score." },
      { n: 2, title: "Open the row", body: "See applications and journey links." },
      { n: 3, title: "Start the deal", body: "Kenya Ops or New application, picking this customer." },
    ],
  },
  "/mobile-lend": {
    title: "How app activation works",
    intro: "Self-register is not enough to borrow. Your institution unlocks the limit.",
    steps: [
      { n: 1, title: "Invite or wait", body: "Send an invite, or find a pending self-registered email." },
      { n: 2, title: "Approve", body: "Confirm phone, set limit, mark KYC/AML clear." },
      { n: 3, title: "Customer borrows", body: "Buruuj Lend unlocks Get financing for that account." },
    ],
  },
  "/institutions": {
    title: "How onboarding works",
    intro: "Create the tenant before any customer or deal.",
    steps: [
      { n: 1, title: "Register the bank", body: "Name, code, Malaysia desk mode." },
      { n: 2, title: "Integrations", body: "Kenya partner credentials." },
      { n: 3, title: "Users", body: "Institution admin, then ops." },
    ],
  },
  "/users": {
    title: "How access works",
    intro: "Issue a login, hand over the temporary password, they change it.",
    steps: [
      { n: 1, title: "Pick the role", body: "Platform admin is Buruuj only." },
      { n: 2, title: "Create the user", body: "Copy the password once." },
      { n: 3, title: "They sign in", body: "Forced password change, then the desks." },
    ],
  },
  "/integrations": {
    title: "How partner setup works",
    intro: "Secrets stay on the institution. Blank keeps the current value.",
    steps: [
      { n: 1, title: "Select the bank", body: "One form per institution." },
      { n: 2, title: "Fill Kenya partners", body: "M-Pesa, Safaricom, Airtel." },
      { n: 3, title: "Register callbacks", body: "Copy URLs into the partner portal." },
    ],
  },
  "/webhooks": {
    title: "How machine access works",
    intro: "People use Users. Cores use keys and signed callbacks.",
    steps: [
      { n: 1, title: "Create the API key", body: "Copy the key and the HMAC secret once." },
      { n: 2, title: "Register the callback", body: "SACCO POST /api/tawarruq/callback, or a webhook URL here." },
      { n: 3, title: "Execute then pay", body: "CBS calls /tawarruq/execute. Certificates arrive. SACCO disburses." },
    ],
  },
  "/agent-dealers": {
    title: "How the pool works",
    intro: "The dealer adds float. Kenya step 2 drains the facility amount when a dealer is active.",
    steps: [
      { n: 1, title: "Register the dealer", body: "Till and contact. Pool starts at zero." },
      { n: 2, title: "Dealer adds float", body: "Only the Agent dealer login can top up." },
      { n: 3, title: "Run Kenya Ops", body: "Leg 1 deducts. Murabaha stays blocked until possession." },
    ],
  },
  "/repayments": {
    title: "How collections work",
    intro: "Only after disbursement. Each row is one instalment of the Murabaha.",
    steps: [
      { n: 1, title: "Filter the board", body: "Outstanding, overdue, or paid." },
      { n: 2, title: "Collect", body: "Records the instalment against the offer." },
      { n: 3, title: "Follow overdue", body: "Open the Kenya case if you need the full tape." },
    ],
  },
  "/transactions": {
    title: "How the legs work",
    intro: "Purchase, transfer, sale. Disburse only after all three confirm.",
    steps: [
      { n: 1, title: "Open the row", body: "See which certificate is missing." },
      { n: 2, title: "Confirm the leg", body: "Kenya receipt or Malaysia e-cert." },
      { n: 3, title: "Disburse", body: "After Leg 3. Customer still owes the Murabaha." },
    ],
  },
  "/shariah": {
    title: "How the audit works",
    intro: "Verify, inspect one case, then export.",
    steps: [
      { n: 1, title: "Verify the chain", body: "Institution-wide hash check." },
      { n: 2, title: "Open a case", body: "Step ledger and possession seal." },
      { n: 3, title: "Export", body: "CSV or JSON for the board." },
    ],
  },
};
