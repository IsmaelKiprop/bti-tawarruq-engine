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

/** Page guides live under Documentation — keep this map empty so desks stay operational. */
export const PAGE_GUIDES: Record<string, PageGuideContent> = {};

export function getPageGuide(_pathname: string): PageGuideContent | null {
  return null;
}
