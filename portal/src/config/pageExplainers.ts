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

export const APPROVAL_LIMIT_FIELD =
  "Maximum deal amount this person may approve. FI Operations queues Murabaha, liquidation, or disbursement. FI Approver must approve it. If the deal is larger than this limit, approve is rejected. The engine uses the lower of this amount and the institution limit. Leave blank to inherit the institution cap only. Set this when inviting FI Approver.";

export const INSTITUTION_LIMIT_FIELD =
  "Bank or SACCO cap for queued deals. The engine uses the lower of this and the approver's personal limit. Blank means no institution cap.";

export const MAKER_CHECKER_STEPS_FIELD =
  "Which actions wait for an FI Approver. Default: murabaha, liquidation, disbursement. Remove a word to run that step immediately.";

export const APPROVAL_LIMIT_DASHBOARD =
  "Approval limit is the maximum deal amount a person may approve. FI Operations starts Murabaha, liquidation, or disbursement. That step queues. FI Approver must approve it. If the deal is larger than their limit, the approve is rejected. There are two places for it: the user (Users) and the institution (Institutions). The engine uses the lower of the two. Leave the user field blank and they inherit the institution limit only. Leave both blank and there is no amount cap. Set a user limit when inviting FI Approver.";

export const PAGE_EXPLAINS: Record<string, PageExplainContent> = {
  "/": {
    title: "What this dashboard is",
    lead: "Super Admin sees customer institution charts and a primary onboard action. Other roles see engine uptime for their scope.",
    dealTitle: "How you use it",
    dealSteps: [
      "Onboard a customer financial institution first if the book is empty.",
      "Read type and regulator charts, monthly onboarding, and Active / Dormant / Deactivated counts.",
      "Invite FI Admin only after the institution is Active.",
      "API client requests from FI Admin appear on Dashboard. Issue the key there and copy it once.",
    ],
  },
  "/institutions/onboard": {
    title: "What FI onboarding is",
    lead: "A KYC wizard for a customer financial institution. Super Admin activate is immediate. BTI Ops submit waits for Super Admin approval.",
    dealTitle: "How you use it",
    dealSteps: [
      "Complete Identity, Regulatory, Ownership, Representatives, Settlement, then Commercial.",
      "Next is blocked until the current page is complete. You cannot skip ahead. Save draft keeps incomplete work.",
      "Super Admin: Activate institution. BTI Ops: Submit for Super Admin approval.",
    ],
    note: "Document fields take a reference (filename or ticket id) in this slice. File upload comes later.",
  },
  "/sedania": {
    title: "What Sedania Financing is",
    lead: "Bank Commodity Murabahah on AS SIDQ. SEDANIA As Salam Capital is appointed independently as wakeel (approved) or Rasul (AAOIFI). The bank credits CASA. Physical delivery is the keep-the-commodity path.",
    dealTitle: "How a deal uses it",
    dealSteps: [
      "Pick the customer and the flow: approved wakeel, or AAOIFI Rasul.",
      "Run financing. The engine buys airtime, seals qabd hukmi, then sells on Murabahah.",
      "On the approved flow, muqassah set-off comes before the CASA credit.",
      "If the customer keeps the commodity, settle the deferred price, then arrange physical delivery.",
    ],
    note: "Documents on this desk are Purchase Order, Commodity Invoice, Delivery Order, and Trading e-Cert.",
  },
  "/ops": {
    title: "What Ops Monitor is",
    lead: "Telemetry for the engine itself: who you are, request volume, and errors. It does not run a commodity leg.",
    dealTitle: "How a deal uses it",
    dealSteps: [
      "Confirm your role and institution scope before you troubleshoot.",
      "Watch the counters your role is allowed to see: engine health, and your book if you operate a desk.",
      "Open an active application from the list, then finish it on the track desk.",
    ],
    note: "A red counter means work is waiting, not that a trade has settled.",
  },
  "/kenya": {
    title: "What Kenya Ops is",
    lead: "The Kenya workbench for the eight float steps: apply, buy float, seal possession, Murabaha, Wakala, independent sale, clear, then pay and collect. The commodity is prepaid airtime / mobile money float, not cash credit.",
    dealTitle: "How a deal uses it",
    dealSteps: [
      "Pick a customer from the book, then create a case. Do not register the same person again.",
      "Run only the next action the case names. Possession before Murabaha. Wakala before liquidation.",
      "When a dealer is active, Leg 1 drains the Agent Dealer pool; otherwise it uses the MNO path.",
      "Disburse only after the independent sale and clearing. The customer still owes the Murabaha.",
    ],
    note: "No-Inah rejects a broker that is the originating MNO or dealer pool. Amount on the case is float cost the institution must possess.",
  },
  "/malaysia": {
    title: "What Malaysia Manual Bridge is",
    lead: "The Malaysia workbench for the twelve Suq Al-Sila' steps. The commodity is crude palm oil (ACPO), not cash. Until Buruuj is admitted to BSAS, this page writes a desk packet for Ops and you paste the e-certificate.",
    dealTitle: "How a deal uses it",
    dealSteps: [
      "Pick the onboarded customer, lock the Murabaha offer, then instruct Leg 1 buy.",
      "Copy the Bursa packet, paste the Islamic Services Receipt, and advance only the next unanswered leg.",
      "After bank ownership, sell to the customer (Leg 2), record Wakala, then sell independently (Leg 3).",
      "Disburse only when all three legs are confirmed. The customer repays Murabaha, not the palm oil.",
    ],
    note: "Mock E2E skips live Bursa for local testing. Bid is cost. Murabaha is cost plus profit.",
  },
  "/applications": {
    title: "What an application is",
    lead: "An application is the financing request — step 1 of both Tawarruq tracks. It is not a cash loan. Kenya uses float. Malaysia uses crude palm oil on Suq Al-Sila'.",
    dealTitle: "How a deal uses it",
    dealSteps: [
      "Pick the customer already on Customers. Do not register the same person again.",
      "Capture bid or facility amount, profit rate, term, and purpose. The engine records the Wa'd.",
      "Generate and accept the Murabaha offer. That locks cost plus disclosed profit.",
      "Finish commodity legs on Kenya Ops or Malaysia Manual Bridge, not only on this list.",
    ],
    note: "List Murabaha is a 5% preview until the offer locks on the detail page. The customer still owes the Murabaha, not the float or the palm oil.",
  },
  "/applications/new": {
    title: "What New application does",
    lead: "Where a Tawarruq journey begins: pick the onboarded customer, set cost and profit, then lock the Murabaha offer.",
    dealTitle: "How a deal uses it",
    dealSteps: [
      "Select the customer already on the books. Do not register the same person again.",
      "Set amount, profit rate, term, and purpose. The live tape is the Murabaha the customer will owe.",
      "Accept the offer, then open the Malaysia desk packet or continue on Kenya Ops.",
    ],
    note: "Amount is commodity cost, not a cash loan. KES deals show the Kenya 98% spot preview. MYR deals do not.",
  },
  "/approvals": {
    title: "What maker-checker approvals are",
    lead: "Dual control for queued commodity steps. FI Operations starts Murabaha, liquidation, or disbursement. FI Approver must approve it.",
    dealTitle: "How a deal uses it",
    dealSteps: [
      "FI Operations queues a step that the institution marked for maker-checker.",
      "FI Approver decides approve or reject. You cannot approve a request you initiated.",
      "Approval limit is the maximum deal amount you may authorize. The engine uses the lower of your personal limit and the institution limit.",
    ],
    note: "If the deal is larger than the effective limit, approve is rejected.",
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
    lead: "A customer financial institution on BTI's engine. BTI is the operator and is not a row here. Onboarding lives on the KYC wizard. Manage holds engine settings only.",
    dealTitle: "How you use the directory",
    dealSteps: [
      "Onboard a bank, SACCO, or other financial institution from Onboard FI.",
      "Filter by lifecycle: draft, pending approval, active, dormant, or deactivated.",
      "Resume KYC on drafts. Super Admin approves BTI Ops submissions from this list.",
      "Open Manage for BSAS mode, deal maker-checker, billing fee, and tenant audit.",
    ],
    note: "Invite FI Admin only after the institution is Active. Deal maker-checker stays on Manage, not on the KYC wizard.",
  },
  "/institution": {
    title: "What FI profile is",
    lead: "FI Admin sees their own KYC profile. They cannot edit onboarding. They request an API client; Super Admin issues the key.",
    dealTitle: "How you use it",
    dealSteps: [
      "Read the KYC BTI captured when the institution was onboarded.",
      "Request API Client when your core banking or app needs a machine key.",
      "While Super Admin reviews it, this page shows Pending. After they issue it, copy the key and HMAC here.",
    ],
    note: "Draft and pending FIs cannot request an API client.",
  },
  "/users": {
    title: "What a user is",
    lead: "A portal login. Platform admin is Buruuj and sees all institutions. Other roles stay on one bank or SACCO. The directory is lean; open Manage for profile, HR, and audit.",
    dealTitle: "How a deal uses it",
    dealSteps: [
      "Invite with the narrowest role that still lets them work.",
      "A temporary password is generated and emailed via SMTP when configured.",
      "They must change it on first sign-in before desks open. Activate, deactivate, and HR edits live on the manage page.",
      "Approval limit is the maximum deal amount that person may approve. Set it on FI Approver. The engine uses the lower of this and the institution limit.",
      "Staff set their own name and HR fields on Settings. Admins can override the same fields on User management.",
    ],
    note: "Super Admin and BTI Ops invite FI Admin only after the FI is Active. Super Admin may also invite Super Admin, BTI Ops, BTI Finance, Shariah / Audit, and Reconciliation. FI Admin invites FI Ops, FI Approver, and the other FI desk roles for their institution. Super Admin and BTI Ops do not invite FI Ops or FI Approver. API keys are Super Admin only.",
  },
  "/settings": {
    title: "What settings cover",
    lead: "Your own portal account: profile/HR record, password, MFA, theme, and shortcuts for desks you can open.",
    dealTitle: "How you use it",
    dealSteps: [
      "Keep display name and HR fields current so admins see the same staff record on Users → Manage.",
      "Change password after an invite or whenever policy requires.",
      "Enable authenticator or email MFA; privileged Buruuj roles should keep MFA on.",
      "Use role workspace links for institutions, users, billing, and ops when your permissions allow.",
    ],
    note: "Process explainers for desks live under Documentation, not on Settings.",
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
    lead: "Machine access for a SACCO CBS. Super Admin onboards the API key. FI Admin requests that key from BTI, then registers callbacks.",
    dealTitle: "How a deal uses it",
    dealSteps: [
      "Super Admin creates the institution API key on this page. Copy the key and HMAC secret once.",
      "FI Admin cannot issue keys — request BTI to onboard, then register POST /api/tawarruq/callback here.",
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
    intro: "Super Admin starts with customer FI charts. Other roles read uptime.",
    steps: [
      { n: 1, title: "Onboard first", body: "If there is no customer institution, use Onboard FI." },
      { n: 2, title: "Read the book", body: "Type, regulator, monthly onboarding, and Active / Dormant / Deactivated." },
      { n: 3, title: "Staff after Active", body: "Invite FI Admin from Users only when the institution is Active." },
    ],
  },
  "/institutions/onboard": {
    title: "How FI onboarding works",
    intro: "One KYC category per page. Super Admin activate is immediate. BTI Ops waits for Super Admin.",
    steps: [
      { n: 1, title: "Capture KYC", body: "Identity through Commercial. Next is blocked until the page is complete." },
      { n: 2, title: "Submit", body: "Review, then Super Admin activates or BTI Ops submits for approval." },
      { n: 3, title: "Activate or wait", body: "Super Admin goes live now. BTI Ops waits for approve." },
    ],
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
  "/kenya": {
    title: "How Kenya Ops works",
    intro: "One case, eight steps, in order. Float is the commodity.",
    steps: [
      { n: 1, title: "Create the case", body: "Customer from the book, facility amount, term, profit." },
      { n: 2, title: "Buy float", body: "Dealer pool when active, otherwise MNO." },
      { n: 3, title: "Seal possession", body: "Required before Murabaha." },
      { n: 4, title: "Murabaha then Wakala", body: "Sell to customer, then appoint the wakeel." },
      { n: 5, title: "Independent sale", body: "No-Inah. Then clear, disburse, collect." },
    ],
  },
  "/malaysia": {
    title: "How the Malaysia bridge works",
    intro: "Twelve steps. Packet out, e-certificate in, then the next leg.",
    steps: [
      { n: 1, title: "Start the desk", body: "Customer, bid, profit, Murabaha offer." },
      { n: 2, title: "Leg 1", body: "Send the packet. Paste the Islamic Services Receipt." },
      { n: 3, title: "Sale and Wakala", body: "Leg 2 to the customer, then wakeel appointment." },
      { n: 4, title: "Leg 3 and disburse", body: "Independent BSAS sale, then payout." },
    ],
  },
  "/applications": {
    title: "How applications work",
    intro: "This book is the customer side. Commodity legs live on the desks.",
    steps: [
      { n: 1, title: "Find the request", body: "Open a row for cost, profit, Murabaha, and status." },
      { n: 2, title: "Lock the offer", body: "Accept on detail. List Murabaha is only a preview until then." },
      { n: 3, title: "Open the desk", body: "Kenya Ops or Malaysia Manual Bridge for the legs." },
    ],
  },
  "/applications/new": {
    title: "How New application works",
    intro: "Pick the customer, set cost and term, lock the offer.",
    steps: [
      { n: 1, title: "Select the customer", body: "Same record as Customers." },
      { n: 2, title: "Set the facility", body: "Amount is commodity cost. Term is instalments." },
      { n: 3, title: "Create", body: "Then accept the offer and open the right desk." },
    ],
  },
  "/approvals": {
    title: "How maker-checker works",
    intro: "Queue, dual control, then execute.",
    steps: [
      { n: 1, title: "Ops queues", body: "Murabaha, liquidation, or disbursement when dual control is on." },
      { n: 2, title: "Approver decides", body: "Cannot approve own request. Limit caps the deal size." },
      { n: 3, title: "Engine runs", body: "Approved steps execute. Rejected steps stay blocked." },
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
    title: "How the directory works",
    intro: "Onboarding is the KYC wizard. This page is the customer institution directory.",
    steps: [
      { n: 1, title: "Onboard", body: "Open Onboard FI. Super Admin activate is immediate. BTI Ops submit waits for Super Admin." },
      { n: 2, title: "Directory", body: "Search and filter by lifecycle. Resume drafts. Approve pending submissions." },
      { n: 3, title: "Manage later", body: "Engine settings (BSAS, deal maker-checker, fee) stay on Manage. Invite FI Admin only after Active." },
    ],
    note: "Deal maker-checker is for Murabaha, liquidation, and disbursement. It is not used on FI onboarding.",
  },
  "/users": {
    title: "How access works",
    intro: "Invite by email. SMTP delivers the temporary password; first login forces a change. Manage opens the admin profile, HR, and audit trail.",
    steps: [
      { n: 1, title: "Pick the role", body: "Choose the named role your login may create. Super Admin sees every desk role. FI Admin sees FI desk roles only." },
      { n: 2, title: "Invite", body: "Password is emailed (or shown once if SMTP is off). Set approval limit when inviting FI Approver: max deal they may authorize. Blank inherits the institution cap." },
      { n: 3, title: "Manage", body: "Use the manage icon for activate/deactivate, resend invite, HR fields, and the audit trail for that login." },
      { n: 4, title: "They sign in", body: "Forced password change, then they complete profile/HR on Settings." },
    ],
  },
  "/settings": {
    title: "How settings work",
    intro: "Self-service for the signed-in login. Admins still govern roles and access from Users.",
    steps: [
      { n: 1, title: "Profile & HR", body: "Update name, job title, department, employee number, phone, and office." },
      { n: 2, title: "Security", body: "Change password and enable MFA (authenticator or email)." },
      { n: 3, title: "Shortcuts", body: "Open desks your role can reach without hunting the sidebar." },
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
  "/sedania": {
    title: "How Sedania financing works",
    intro: "AS SIDQ trades telecommunication airtime. SASC sells independently. The bank pays CASA.",
    steps: [
      { n: 1, title: "Enter the CMP", body: "Customer signs the financing contract and may appoint SASC." },
      { n: 2, title: "Trade on AS SIDQ", body: "Bank buys, takes qabd hukmi, then sells on Murabahah." },
      { n: 3, title: "Pay or deliver", body: "Muqassah then CASA, or physical delivery after full settlement." },
    ],
    note: "SACCO execute still pays on the SACCO CBS. This desk is the bank CASA path.",
  },
  "/webhooks": {
    title: "How machine access works",
    intro: "People use Users. Cores use keys and signed callbacks.",
    steps: [
      { n: 1, title: "Onboard the API key", body: "Super Admin issues it. FI Admin requests BTI if they do not have one." },
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
