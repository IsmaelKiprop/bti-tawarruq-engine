/**
 * Single source of truth for the explanatory layer of the ops portal.
 *
 * The portal walks three different parties through one Tawarruq transaction, and
 * users kept losing track of who does what. Every guide, legend and flow diagram
 * in the UI reads from this file so the story stays consistent across pages.
 */

export type ActorId =
  | "customer"
  | "bank"
  | "sacco"
  | "bti"
  | "amanah"
  | "bursa"
  | "sedania"
  | "partner"
  | "shariah";

export interface Actor {
  id: ActorId;
  name: string;
  short: string;
  role: string;
  kind: "internal" | "external" | "automation" | "human";
}

export const ACTORS: Record<ActorId, Actor> = {
  customer: {
    id: "customer",
    name: "End customer",
    short: "Customer",
    role: "Requests financing, accepts the Murabaha offer, appoints the bank as selling agent, repays instalments.",
    kind: "human",
  },
  bank: {
    id: "bank",
    name: "Institution / bank ops",
    short: "Bank",
    role: "Owns the customer relationship: prices the offer, signs the contract, instructs Buruuj, collects repayments.",
    kind: "human",
  },
  sacco: {
    id: "sacco",
    name: "Mwalimu SACCO (CBS)",
    short: "SACCO",
    role: "Calls POST /tawarruq/execute for a pre-approved member, receives the three certificates, then disburses cash on its own ledger / M-Pesa.",
    kind: "external",
  },
  bti: {
    id: "bti",
    name: "Buruuj Fintech engine",
    short: "Buruuj",
    role: "This platform. Executes commodity legs, stamps Wa'd and Wakalah, vaults certificates, and relays the Shariah trail. Does not handle SACCO principal cash.",
    kind: "internal",
  },
  amanah: {
    id: "amanah",
    name: "Amanah AI worker",
    short: "Amanah",
    role: "Automation inside Buruuj. Watches accepted offers, advances legs in order, escalates when a leg stalls or amounts mismatch.",
    kind: "automation",
  },
  bursa: {
    id: "bursa",
    name: "Bursa Malaysia (BSAS)",
    short: "Bursa",
    role: "External commodity exchange. Executes the trade, applies fees, and issues the e-certificate receipt.",
    kind: "external",
  },
  sedania: {
    id: "sedania",
    name: "Sedania As Salam Capital / AS SIDQ",
    short: "SASC",
    role: "Independent wakeel or Rasul. Matches airtime on AS SIDQ, issues the trade pack, and sells to random purchasers.",
    kind: "external",
  },
  partner: {
    id: "partner",
    name: "Kenya partners",
    short: "Partners",
    role: "Safaricom or Airtel float supply (MNO or Agent Dealer), M-Pesa wallet payouts, and the independent broker that buys the commodity.",
    kind: "external",
  },
  shariah: {
    id: "shariah",
    name: "Shariah audit service",
    short: "Shariah",
    role: "Independent append-only ledger. Mirrors every step so compliance can verify the chain was never edited.",
    kind: "internal",
  },
};

export const ACTOR_ORDER: ActorId[] = [
  "customer",
  "sacco",
  "bank",
  "bti",
  "amanah",
  "sedania",
  "bursa",
  "partner",
  "shariah",
];

export interface FlowStep {
  step: number;
  title: string;
  detail: string;
  /** Who performs the step. First actor is the owner. */
  actors: ActorId[];
  /** Where in the portal this step is done or observed. */
  route?: string;
  routeLabel?: string;
  /** Whether ops must act, or the engine handles it. */
  mode: "manual" | "automated" | "external";
}

export interface FlowPhase {
  id: string;
  title: string;
  summary: string;
  steps: FlowStep[];
}

export interface ProcessTrack {
  id: string;
  name: string;
  subtitle: string;
  route: string;
  phases: FlowPhase[];
}

export const MALAYSIA_TRACK: ProcessTrack = {
  id: "malaysia",
  name: "Malaysia: Bursa Suq Al-Sila' (BSAS)",
  subtitle:
    "Crude palm oil Tawarruq on Bursa Suq Al-Sila' (desk packet until admission) or the Eiger Trading Platform when that desk is live.",
  route: "/malaysia",
  phases: [
    {
      id: "initiation",
      title: "Phase 1 — Initiation",
      summary: "The bank agrees terms with the customer, then instructs Buruuj to buy the commodity.",
      steps: [
        {
          step: 1,
          title: "Customer request",
          detail:
            "The bank opens a financing request for an onboarded customer under the Tawarruq arrangement.",
          actors: ["customer", "bank"],
          route: "/customers",
          routeLabel: "Customers",
          mode: "manual",
        },
        {
          step: 2,
          title: "Offer and acceptance",
          detail:
            "The bank presents cost price plus markup. The customer accepts, which locks the Murabaha price.",
          actors: ["bank", "customer"],
          route: "/applications",
          routeLabel: "Applications",
          mode: "manual",
        },
        {
          step: 3,
          title: "Purchase instruction",
          detail: "The bank instructs Buruuj Fintech to execute the commodity purchase for the accepted offer.",
          actors: ["bank", "bti"],
          route: "/malaysia",
          routeLabel: "Malaysia Manual Bridge",
          mode: "manual",
        },
        {
          step: 4,
          title: "Commodity purchase (Leg 1)",
          detail:
            "Buruuj buys the commodity as agent through the Bursa BSAS platform. In manual-bridge mode the engine emits a desk packet for BSAS Ops.",
          actors: ["bti", "amanah", "bursa"],
          route: "/malaysia",
          routeLabel: "Malaysia Manual Bridge",
          mode: "automated",
        },
      ],
    },
    {
      id: "procurement",
      title: "Phase 2 — Commodity procurement",
      summary: "Bursa confirms the trade, Buruuj records ownership, and the bank sells the commodity onward.",
      steps: [
        {
          step: 5,
          title: "Purchase confirmation",
          detail:
            "The BSAS platform confirms the purchase, applies transaction fees, and issues the e-certificate (Islamic Services Receipt).",
          actors: ["bursa"],
          route: "/malaysia",
          routeLabel: "Paste e-certificate",
          mode: "external",
        },
        {
          step: 6,
          title: "Bank ownership confirmation",
          detail: "Buruuj confirms to the bank that commodity ownership has transferred to the bank.",
          actors: ["bti"],
          route: "/transactions",
          routeLabel: "Transactions",
          mode: "automated",
        },
        {
          step: 7,
          title: "Sale to customer",
          detail: "The bank sells the commodity to the customer on deferred payment at cost plus markup.",
          actors: ["bank", "customer"],
          route: "/applications",
          routeLabel: "Applications",
          mode: "automated",
        },
        {
          step: 8,
          title: "Customer agency (Wakala)",
          detail: "The customer appoints the bank as agent to sell the commodity on their behalf.",
          actors: ["customer", "bank"],
          route: "/applications",
          routeLabel: "Applications",
          mode: "automated",
        },
      ],
    },
    {
      id: "liquidation",
      title: "Phase 3 — Sale and disbursement",
      summary: "The commodity is sold to a third party and the cash reaches the customer with a certificate.",
      steps: [
        {
          step: 9,
          title: "Sale instruction",
          detail: "The bank instructs Buruuj to sell the commodity on the customer's behalf.",
          actors: ["bank", "bti"],
          route: "/malaysia",
          routeLabel: "Malaysia Manual Bridge",
          mode: "manual",
        },
        {
          step: 10,
          title: "Commodity sale (Leg 3)",
          detail: "Buruuj executes the sale on the BSAS platform to a third-party buyer.",
          actors: ["bti", "bursa"],
          route: "/malaysia",
          routeLabel: "Malaysia Manual Bridge",
          mode: "automated",
        },
        {
          step: 11,
          title: "Sale confirmation and funds",
          detail: "BSAS confirms the sale and credits proceeds to the Buruuj account for settlement.",
          actors: ["bursa", "bti"],
          route: "/transactions",
          routeLabel: "Transactions",
          mode: "external",
        },
        {
          step: 12,
          title: "Disbursement and certificate",
          detail:
            "Funds are disbursed to the customer. Buruuj issues the Tawarruq certificate confirming the full transaction.",
          actors: ["bti", "customer"],
          route: "/transactions",
          routeLabel: "Transactions",
          mode: "automated",
        },
      ],
    },
  ],
};

export const SEDANIA_FINANCING_TRACK: ProcessTrack = {
  id: "sedania-financing",
  name: "Sedania: AS SIDQ bank financing",
  subtitle:
    "BTI Advisory approved flow: SASC as independent wakeel, muqassah, bank credits CASA. AAOIFI variant uses Rasul. Physical delivery keeps the commodity.",
  route: "/sedania",
  phases: [
    {
      id: "cmp",
      title: "Steps 1 to 2: Mandate",
      summary: "Customer enters the Commodity Murabahah Program and may appoint SASC independently.",
      steps: [
        {
          step: 1,
          title: "Financing contract and CMP",
          detail: "Customer applies, signs the financing contract, and enters the CMP. API: POST /sedania/financing.",
          actors: ["customer", "bank"],
          route: "/sedania",
          routeLabel: "Sedania Financing",
          mode: "manual",
        },
        {
          step: 2,
          title: "Appoint SASC",
          detail: "Approved flow appoints SASC as wakeel. AAOIFI flow appoints SASC as Rasul (messenger).",
          actors: ["customer", "sedania"],
          mode: "automated",
        },
      ],
    },
    {
      id: "trade",
      title: "Steps 3 to 5: AS SIDQ trade",
      summary: "Bank buys airtime, takes qabd hukmi, then sells on Murabahah.",
      steps: [
        {
          step: 3,
          title: "Spot purchase",
          detail: "Bank purchases telecommunication airtime on a spot and credit basis via AS SIDQ. Documents: Purchase Order and Commodity Invoice.",
          actors: ["bank", "sedania"],
          mode: "external",
        },
        {
          step: 4,
          title: "Qabd hukmi",
          detail: "Supplier delivers via AS SIDQ. Delivery Order proves constructive possession before any sale to the customer.",
          actors: ["sedania", "bank"],
          mode: "external",
        },
        {
          step: 5,
          title: "Murabahah deferred sale",
          detail: "Bank sells at cost plus profit on deferred terms. Trading e-Cert is issued.",
          actors: ["bank", "customer", "sedania"],
          mode: "external",
        },
      ],
    },
    {
      id: "exit",
      title: "Steps 6 to 8: Sale, set-off, CASA",
      summary: "Independent sale, muqassah on the approved flow, then the bank credits CASA. Physical delivery skips this.",
      steps: [
        {
          step: 6,
          title: "Independent sale",
          detail: "SASC sells to random purchasers on AS SIDQ as wakeel or Rasul.",
          actors: ["sedania", "customer"],
          mode: "external",
        },
        {
          step: 7,
          title: "Muqassah",
          detail: "Purchaser authorizes the bank to pay the customer, then agrees to pay the seller for set-off. Skipped on the Rasul flow.",
          actors: ["bank", "sedania"],
          mode: "automated",
        },
        {
          step: 8,
          title: "CASA credit",
          detail: "The bank credits the customer's Current or Savings Account.",
          actors: ["bank", "customer"],
          mode: "automated",
        },
      ],
    },
  ],
};

export const KENYA_TRACK: ProcessTrack = {
  id: "kenya",
  name: "Kenya: float / airtime Tawarruq",
  subtitle:
    "The same eight steps the customer sees. Buruuj buys float from the MNO or an Agent Dealer, seals possession, then liquidates through an independent broker and pays out via M-Pesa.",
  route: "/kenya",
  phases: [
    {
      id: "application",
      title: "Step 1: Application",
      summary: "Register the customer, create the facility, then let the engine score eligibility.",
      steps: [
        {
          step: 1,
          title: "Facility Application and Agency Mandate",
          detail:
            "Pick the customer already on the books, then create the application. The engine records the Wa'd (undertaking to purchase). Register a new person only if they are not on Customers yet. API: POST /kenya/applications, POST /kenya/applications/{id}/eligibility.",
          actors: ["customer", "bank", "bti"],
          route: "/customers",
          routeLabel: "Customers",
          mode: "manual",
        },
      ],
    },
    {
      id: "possession",
      title: "Steps 2 to 3: Purchase and possession",
      summary: "Buy the float commodity and prove constructive possession before any sale to the customer.",
      steps: [
        {
          step: 2,
          title: "Float Purchase Order",
          detail:
            "Leg 1. Buy float from Safaricom or Airtel (MNO path) or drain an Agent Dealer pool when a dealer is active. API: POST /kenya/transactions then POST .../purchase, or POST .../agent-dealer-purchase.",
          actors: ["bti", "amanah", "partner"],
          route: "/kenya",
          routeLabel: "Kenya Ops",
          mode: "automated",
        },
        {
          step: 3,
          title: "Supplier Transfer and Constructive Possession",
          detail:
            "The supplier receipt is sealed with an asset hash so the sequence cannot be back-dated. Murabaha stays blocked until this is done. API: POST /kenya/transactions/{id}/possession.",
          actors: ["partner", "bti", "shariah"],
          route: "/kenya",
          routeLabel: "Kenya Ops",
          mode: "external",
        },
      ],
    },
    {
      id: "contract",
      title: "Steps 4 to 5: Murabaha and Wakala",
      summary: "Sell the float to the customer at cost plus profit, then take agency consent.",
      steps: [
        {
          step: 4,
          title: "Murabahah Deferred Sale",
          detail:
            "Generate and accept the offer, sign the contract, then transfer title (Leg 2). API: POST .../offer, .../accept, .../murabaha, .../murabaha/sign, POST .../transfer.",
          actors: ["bank", "customer", "bti"],
          route: "/kenya",
          routeLabel: "Kenya Ops",
          mode: "manual",
        },
        {
          step: 5,
          title: "Agency Activation",
          detail:
            "The customer appoints Buruuj as wakeel. Liquidation stays blocked until this consent is recorded. API: POST /kenya/applications/{id}/wakala.",
          actors: ["customer", "bti"],
          route: "/kenya",
          routeLabel: "Kenya Ops",
          mode: "manual",
        },
      ],
    },
    {
      id: "settlement",
      title: "Steps 6 to 8: Liquidation and payout",
      summary: "Sell to an independent buyer, clear proceeds, pay the wallet, then collect instalments.",
      steps: [
        {
          step: 6,
          title: "Spot Sale to Secondary Purchaser",
          detail:
            "No-Inah: sell at spot to an independent broker, never the originating MNO or dealer pool. API: POST /kenya/transactions/{id}/liquidate.",
          actors: ["bti", "partner", "shariah"],
          route: "/kenya",
          routeLabel: "Kenya Ops",
          mode: "automated",
        },
        {
          step: 7,
          title: "Clearing and Settlement",
          detail:
            "Platform clearing of the spot proceeds before wallet credit. API: POST /kenya/applications/{id}/complete-settlement.",
          actors: ["bti"],
          route: "/kenya",
          routeLabel: "Kenya Ops",
          mode: "automated",
        },
        {
          step: 8,
          title: "Cash Disbursement and Repayments",
          detail:
            "Credit M-Pesa or Airtel Money, then collect instalments against the Murabaha schedule. API: POST /kenya/disbursements, GET .../repayments, POST /kenya/repayments/{id}/collect.",
          actors: ["bti", "partner", "bank", "customer"],
          route: "/repayments",
          routeLabel: "Repayments",
          mode: "manual",
        },
      ],
    },
  ],
};

export const SACCO_TRACK: ProcessTrack = {
  id: "sacco",
  name: "Kenya SACCO: Sedania As-Sidq",
  subtitle:
    "Mwalimu CBS starts the facility. Buruuj stamps Wa'd and Wakalah, Sedania trades airtime, then the SACCO pays the member. Buruuj never handles principal cash.",
  route: "/webhooks",
  phases: [
    {
      id: "inbound",
      title: "Steps 1 to 2: Mandate",
      summary: "The SACCO instructs Buruuj for a pre-approved member. Buruuj stamps the legal tokens.",
      steps: [
        {
          step: 1,
          title: "Inbound facility request",
          detail:
            "Mwalimu CBS calls POST /api/v1/tawarruq/execute with customer_id, amount, and tenor. Authenticate with X-API-Key and HMAC (X-BTI-Signature).",
          actors: ["sacco", "bti"],
          route: "/webhooks",
          routeLabel: "API keys",
          mode: "external",
        },
        {
          step: 2,
          title: "Digital contract stamping",
          detail:
            "Buruuj signs the board-approved Wa'd (promise to buy) and Wakalah (liquidation agency) templates. Buruuj does not draft the legal text.",
          actors: ["bti", "shariah"],
          mode: "automated",
        },
      ],
    },
    {
      id: "sedania-trade",
      title: "Steps 3 to 8: Sedania trade",
      summary: "Sedania allocates airtime, sells it on Murabahah, then liquidates to an independent buyer.",
      steps: [
        {
          step: 3,
          title: "Spot purchase",
          detail: "Buruuj calls Sedania POST /v1/trading/purchase to acquire airtime credit units for the SACCO.",
          actors: ["bti", "sedania"],
          mode: "external",
        },
        {
          step: 4,
          title: "Asset acquisition confirmation",
          detail:
            "Sedania returns HTTP 200 with batch ID, inventory serials, and Certificate 1 (Purchase Confirmation). This is Qabd Hukmi.",
          actors: ["sedania", "bti"],
          mode: "external",
        },
        {
          step: 5,
          title: "Deferred Murabahah sale",
          detail: "Buruuj calls POST /v1/trading/transfer-murabahah with cost plus profit markup.",
          actors: ["bti", "sedania"],
          mode: "external",
        },
        {
          step: 6,
          title: "Murabahah confirmation",
          detail: "Sedania returns Certificate 2 (Murabahah Sale Receipt). The member now owns the asset at the deferred price.",
          actors: ["sedania", "bti"],
          mode: "external",
        },
        {
          step: 7,
          title: "Spot liquidation via agency",
          detail:
            "Buruuj, as wakeel, calls POST /v1/trading/liquidate so Sedania sells the airtime into the telco market. This avoids Bai' al-Inah.",
          actors: ["bti", "sedania"],
          mode: "external",
        },
        {
          step: 8,
          title: "Liquidation confirmation",
          detail: "Sedania returns Certificate 3 (Sale and Liquidation Confirmation).",
          actors: ["sedania", "bti"],
          mode: "external",
        },
      ],
    },
    {
      id: "sacco-payout",
      title: "Steps 9 to 10: Relay and payout",
      summary: "Buruuj hands the audit trail to the SACCO. Cash never enters Buruuj.",
      steps: [
        {
          step: 9,
          title: "Webhook and certificate relay",
          detail:
            "Buruuj POSTs tawarruq.certificates_ready to the SACCO callback with the three vault URLs. Payloads are retained for 7 years.",
          actors: ["bti", "sacco"],
          route: "/webhooks",
          routeLabel: "Webhooks",
          mode: "automated",
        },
        {
          step: 10,
          title: "Cash disbursement",
          detail:
            "The SACCO CBS credits the member (FOSA or M-Pesa) and opens the deferred loan ledger. Buruuj does not build this payout.",
          actors: ["sacco", "customer"],
          mode: "external",
        },
      ],
    },
  ],
};

export const TRACKS: ProcessTrack[] = [SEDANIA_FINANCING_TRACK, SACCO_TRACK, KENYA_TRACK, MALAYSIA_TRACK];

/** Which parties own which side of the platform — used on the dashboard. */
export interface ResponsibilitySplit {
  actor: ActorId;
  owns: string[];
  neverDoes: string;
}

export const RESPONSIBILITY_SPLIT: ResponsibilitySplit[] = [
  {
    actor: "bti",
    owns: [
      "Executes the three commodity legs in strict order",
      "Stamps Wa'd and Wakalah, and vaults Sedania certificate payloads for 7 years",
      "Relays certificate URLs to the SACCO CBS so it can disburse",
    ],
    neverDoes:
      "Never handles SACCO principal cash, never matches the commodity order book, and never drafts legal contract language.",
  },
  {
    actor: "bursa",
    owns: [
      "Executes the commodity trade on the BSAS platform",
      "Applies exchange transaction fees",
      "Issues the e-certificate (Islamic Services Receipt)",
    ],
    neverDoes: "Never sees customer KYC, repayment schedules, or wallet details.",
  },
  {
    actor: "amanah",
    owns: [
      "Picks up accepted offers and advances the next pending leg",
      "Re-checks that leg amounts match the accepted offer",
      "Escalates stalled certificates instead of guessing",
    ],
    neverDoes: "Never skips a leg or invents a certificate number.",
  },
  {
    actor: "bank",
    owns: [
      "Customer onboarding, pricing, and contract signing",
      "Instructing Buruuj to buy and later sell the commodity",
      "Collecting instalments from the customer",
    ],
    neverDoes: "Never touches exchange execution or the audit ledger directly.",
  },
  {
    actor: "sacco",
    owns: [
      "Pre-approves the member and calls POST /tawarruq/execute",
      "Receives the three certificate URLs on /api/tawarruq/callback",
      "Disburses KES to the member on its own CBS / M-Pesa rail",
    ],
    neverDoes: "Never calls Sedania directly or stamps Wa'd / Wakalah.",
  },
  {
    actor: "sedania",
    owns: [
      "Matches airtime inventory from the telco pool",
      "Issues Certificate 1, Certificate 2, and Certificate 3",
      "Liquidates to an independent purchaser",
    ],
    neverDoes: "Never sees SACCO identity-provider logins or member cash payout.",
  },
];

export interface GuideLink {
  to: string;
  label: string;
}

export interface PageGuideContent {
  /** One-line answer to "why am I on this page". */
  summary: string;
  /** Which track and phase this page belongs to. */
  stage: string;
  /** Actors involved, owner first. */
  actors: ActorId[];
  /** What the person in front of the screen actually does here. */
  youDo: string[];
  /** What happens without the user, so nobody waits on the wrong thing. */
  engineDoes: string[];
  /** Where the work came from and where it goes next. */
  comesFrom?: GuideLink;
  goesTo?: GuideLink;
  /** Optional caveats that prevent common mistakes. */
  watchOut?: string[];
}

export const PAGE_GUIDES: Record<string, PageGuideContent> = {
  "/": {
    summary:
      "Start here. This is the control tower for both Tawarruq tracks and tells you whether the engine and its partners are reachable.",
    stage: "Overview — all phases",
    actors: ["bti", "amanah", "bursa", "partner"],
    youDo: [
      "Check the engine is online and which integration mode is active",
      "Read the end-to-end flow below to see who owns each step",
      "Jump into the track you are working on today",
    ],
    engineDoes: [
      "Reports live partner configuration from the health endpoint",
      "Counts applications and commodity transactions in your scope",
    ],
    goesTo: { to: "/kenya", label: "Kenya Ops" },
    watchOut: [
      "\"Configured\" means credentials are present, not that a live trade has been proven.",
      "Book Murabaha is a 5% preview until each offer locks. Amount is commodity cost, not a cash loan.",
    ],
  },
  "/ops": {
    summary:
      "Operational telemetry for the platform itself: who you are signed in as, request volumes, and error counts.",
    stage: "Overview — platform monitoring",
    actors: ["bti"],
    youDo: [
      "Confirm your role and permissions before troubleshooting an access issue",
      "Watch HTTP errors and latency when something feels slow",
    ],
    engineDoes: [
      "Refreshes metrics every 30 seconds",
      "Exposes the same counters at /metrics for Prometheus",
    ],
    watchOut: [
      "Active journey Murabaha on this page is a 5% preview until the offer locks.",
    ],
  },
  "/institutions": {
    summary:
      "Onboard a client bank or SACCO. Buruuj Fintech is the operator, not a row on this list. Customers, users, and deals are scoped to an institution created here.",
    stage: "Setup — before any financing exists",
    actors: ["bti", "bank"],
    youDo: [
      "Register the bank with a display name, a unique code, and the Malaysia desk mode",
      "Open Integrations for that institution, then create its institution admin on Users",
    ],
    engineDoes: [
      "Creates the tenant and writes an audit event",
      "Scopes customers, applications, keys, and users to that institution",
    ],
    goesTo: { to: "/integrations", label: "Integrations" },
    watchOut: [
      "Only platform admins can register institutions.",
      "DEFAULT is the built-in demo book and cannot be deleted.",
      "BSAS mode is the Malaysia commodity desk default. Kenya float uses Integrations, not this field.",
    ],
  },
  "/users": {
    summary:
      "Issue portal logins. Admins create the user, hand over a temporary password, and the user must change it on first sign-in.",
    stage: "Setup — access control",
    actors: ["bti", "bank"],
    youDo: [
      "Pick the role from the list: platform admin is Buruuj only; other roles stay on one institution",
      "Copy the temporary password once and send it through a secure channel",
    ],
    engineDoes: [
      "Forces a password change before the new user can reach any other page",
      "Records the role that gates every API call they make",
    ],
    comesFrom: { to: "/institutions", label: "Institutions" },
  },
  "/kenya": {
    summary:
      "The Kenya workbench for the same eight steps the customer sees: apply, buy float, seal possession, Murabaha, Wakala, independent sale, clear, then pay and collect.",
    stage: "Kenya track: steps 1 to 8",
    actors: ["bti", "amanah", "partner", "bank", "customer"],
    youDo: [
      "Pick a customer from the book, then create a case. Do not register the same person again",
      "Open a case and run only the next action it names. Step 3 before step 4. Step 5 before step 6",
    ],
    engineDoes: [
      "Blocks any step whose prerequisite is missing, so the order stays Shariah-valid",
      "Uses an Agent Dealer pool for Leg 1 when a dealer is active, otherwise the MNO path",
      "Rejects a broker that is the originating MNO or dealer pool (No-Inah guard)",
    ],
    comesFrom: { to: "/customers", label: "Customers" },
    goesTo: { to: "/repayments", label: "Repayments" },
    watchOut: [
      "Step 3 possession must be sealed before step 4 Murabaha. Step 5 Wakala must be recorded before step 6 liquidation.",
      "Float is the digital commodity (M-Pesa or Airtel e-value), not cash in a bank account.",
    ],
  },
  "/customer": {
    summary:
      "The customer-facing tracker. It shows the same eight Kenya (or Malaysia) steps, live status, and certificates.",
    stage: "Both tracks: customer visibility",
    actors: ["customer", "bti"],
    youDo: [
      "Look up a journey by application reference or phone",
      "Share the /customer/{ref} link so the customer can follow progress",
    ],
    engineDoes: [
      "Polls the journey while a step is active",
      "Shows certificates after each confirmed commodity leg",
    ],
    comesFrom: { to: "/customers", label: "Customers" },
    goesTo: { to: "/kenya", label: "Kenya Ops" },
    watchOut: [
      "This page is public without login. Do not put internal notes on the customer tracker.",
      "Cost is the commodity. Murabaha is what the customer owes after disbursement.",
    ],
  },
  "/customers": {
    summary:
      "Step 1 starts here: register the financing beneficiary, then open or share their journey.",
    stage: "Kenya track: step 1",
    actors: ["bank", "customer"],
    youDo: [
      "Add the customer to the correct institution book (name, phone, wallet)",
      "Open a row to copy the journey link or start a Kenya application",
    ],
    engineDoes: ["Stores the customer on that institution and records KYC status"],
    goesTo: { to: "/kenya", label: "Kenya Ops" },
    watchOut: [
      "Do not register the same person again on New application or Kenya New case.",
      "Score is institution-entered. Eligibility fails below 500.",
    ],
  },
  "/agent-dealers": {
    summary:
      "Float is mobile-money stock (M-Pesa or Airtel e-value). This page holds Dealer A's pool for Kenya step 2. When a dealer is active, Leg 1 drains this pool instead of a live MNO purchase.",
    stage: "Kenya track: step 2 supply",
    actors: ["bti", "partner", "bank"],
    youDo: [
      "Register a dealer with till and contact. Pool starts at zero.",
      "Issue an Agent dealer login so they can add float. Ops cannot top up.",
    ],
    engineDoes: [
      "Uses the dealer pool on Start float purchase when a dealer is active",
      "Leaves the pool untouched only when ops explicitly starts an MNO purchase",
    ],
    goesTo: { to: "/kenya", label: "Kenya Ops" },
    watchOut: [
      "Insufficient dealer float blocks step 2. The dealer must add float from their desk.",
    ],
  },
  "/repayments": {
    summary:
      "Collect Murabaha instalments after the customer has been paid, and see which accounts are overdue.",
    stage: "Kenya track: step 8, after disbursement",
    actors: ["bank", "bti", "customer"],
    youDo: [
      "Record or trigger instalment collection for a financed customer",
      "Follow up on overdue accounts",
    ],
    engineDoes: [
      "Tracks paid versus outstanding instalments against the accepted offer",
      "Logs each collection into the audit trail",
    ],
    comesFrom: { to: "/kenya", label: "Kenya Ops" },
    watchOut: [
      "These are Murabaha instalments after disbursement, not a second purchase of the float.",
    ],
  },
  "/shariah": {
    summary:
      "Compliance view. Verify the audit chain has not been tampered with and export the ledger for a Shariah board or auditor.",
    stage: "Cross-cutting — evidence for both tracks",
    actors: ["shariah", "bti"],
    youDo: [
      "Verify the hash chain for an institution or a single application",
      "Export the ledger as JSON or CSV for review",
    ],
    engineDoes: [
      "Refuses updates and deletes on ledger rows — it is append-only by design",
      "Links every entry to the certificate or possession seal that evidences it",
    ],
  },
  "/malaysia": {
    summary:
      "The Malaysia workbench for the same twelve steps the customer sees: request, offer, instruct, Leg 1 buy, e-cert, bank ownership, sale to customer, Wakala, sale instruction, Leg 3 sale, confirm, then disburse.",
    stage: "Malaysia track: steps 1 to 12",
    actors: ["bti", "amanah", "bursa", "bank"],
    youDo: [
      "Pick a customer from the book, then start the desk flow. Do not register the same person again",
      "Copy the Bursa packet, paste the e-certificate, and run only the next unanswered leg. Leg 1 before Leg 2. Sale and Wakala before Leg 3",
    ],
    engineDoes: [
      "Formats the packet with bid, profit, Murabaha total, product code, and Agent purchase type",
      "Advances to the next leg only once the current certificate is confirmed",
      "Blocks disbursement until all three legs are confirmed",
    ],
    goesTo: { to: "/transactions", label: "Transactions" },
    watchOut: [
      "Suq Al-Sila' executes the trade. Nothing settles until the e-certificate is pasted, unless mock E2E or a live Eiger/BSAS API is configured.",
      "The commodity is crude palm oil (ACPO), not cash. Bid is cost. Murabaha is cost plus profit.",
    ],
  },
  "/applications": {
    summary:
      "The customer-side book for both tracks. Amount is commodity cost. Murabaha is cost plus profit. Open a row for the locked offer, or start from a customer already on Customers.",
    stage: "Both tracks: step 1, then the desk",
    actors: ["bank", "customer", "bti"],
    youDo: [
      "Find a request and open it to see cost, profit, Murabaha total, and the next desk",
      "Do not treat the amount as a cash loan. Kenya uses float. Malaysia uses palm oil",
    ],
    engineDoes: ["Moves status forward as offers are accepted and legs confirm"],
    goesTo: { to: "/transactions", label: "Transactions" },
    watchOut: [
      "List Murabaha is a 5% preview until the offer locks on the detail page.",
      "Finish commodity legs on Kenya Ops or Malaysia Manual Bridge, not only on this list.",
    ],
  },
  "/applications/new": {
    summary:
      "Where a Tawarruq journey begins: pick the onboarded customer, set cost and profit, then lock the Murabaha offer.",
    stage: "Both tracks: step 1",
    actors: ["customer", "bank"],
    youDo: [
      "Select the customer already on the books. Do not register the same person again",
      "Set amount, profit rate, term, and purpose. The live tape is the Murabaha the customer will owe",
    ],
    engineDoes: [
      "Links the deal to that customer record and records the Wa'd",
      "Generates the institution-scoped application reference",
      "Accepts the offer, then opens the Malaysia desk packet or a mock transaction",
    ],
    comesFrom: { to: "/customers", label: "Customers" },
    goesTo: { to: "/applications", label: "Applications" },
    watchOut: [
      "Amount is commodity cost, not a cash loan. KES deals show the Kenya 98% spot preview. MYR deals do not.",
      "Manual bridge opens Malaysia. A live Kenya desk should start from Kenya Ops.",
    ],
  },
  "/transactions": {
    summary:
      "The commodity side of the deal: three legs, their certificates, and settlement status.",
    stage: "Both tracks — phases 2 and 3",
    actors: ["bti", "amanah", "bursa"],
    youDo: ["Inspect a leg that is stuck and see exactly which certificate is missing"],
    engineDoes: [
      "Keeps legs in purchase, transfer, sale order",
      "Marks the transaction complete only when all three legs are confirmed",
    ],
    comesFrom: { to: "/applications", label: "Applications" },
    watchOut: [
      "Amount on a transaction is commodity cost. Murabaha is what the customer still owes after Leg 3.",
    ],
  },
  "/integrations": {
    summary:
      "Per-institution partner credentials and callback URLs for M-Pesa, the mobile networks, and the broker.",
    stage: "Setup — before live trading",
    actors: ["bti", "partner"],
    youDo: [
      "Select the institution and fill in its partner credentials",
      "Register the generated callback URLs in the partner portal",
    ],
    engineDoes: [
      "Encrypts secrets at rest and only reports whether each secret is set",
      "Falls back to platform defaults when an institution value is blank",
    ],
    comesFrom: { to: "/institutions", label: "Institutions" },
  },
  "/webhooks": {
    summary:
      "SACCO CBS credentials and callbacks. Create an API key plus HMAC secret, then receive tawarruq.certificates_ready after execute.",
    stage: "SACCO execute — steps 1 and 9",
    actors: ["sacco", "bti"],
    youDo: [
      "Create an API key for the SACCO CBS and copy the HMAC secret once",
      "Register the SACCO callback URL (typically POST /api/tawarruq/callback)",
    ],
    engineDoes: [
      "Verifies inbound HMAC on POST /tawarruq/execute",
      "Signs outbound certificate webhooks and vaults payloads for 7 years",
    ],
    watchOut: [
      "Buruuj never disburses SACCO principal cash.",
      "Portal people should use the login page. API keys are for the CBS.",
    ],
  },
};

export function getPageGuide(pathname: string): PageGuideContent | null {
  if (PAGE_GUIDES[pathname]) return PAGE_GUIDES[pathname];
  if (pathname.startsWith("/customers")) return PAGE_GUIDES["/customers"];
  if (pathname.startsWith("/customer") || pathname.startsWith("/journey")) return PAGE_GUIDES["/customer"];
  if (pathname.startsWith("/agent-dealers") || pathname.startsWith("/dealers")) {
    return PAGE_GUIDES["/agent-dealers"];
  }
  if (pathname.startsWith("/applications/")) return PAGE_GUIDES["/applications"];
  if (pathname.startsWith("/transactions/")) return PAGE_GUIDES["/transactions"];
  return null;
}
