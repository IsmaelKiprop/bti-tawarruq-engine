import { computeKenyaDeal, DEFAULT_PROFIT_RATE_PCT } from "./kenyaOps";

export { DEFAULT_PROFIT_RATE_PCT };

export const APPLICATION_EXPLAIN = {
  title: "What an application is",
  lead: "An application is the financing request. It is step 1 of both Tawarruq tracks. It is not a cash loan. The commodity is float in Kenya or crude palm oil on Suq Al-Sila' in Malaysia.",
  dealTitle: "How a deal uses it",
  dealSteps: [
    "Pick the customer already on Customers. Do not register the same person again.",
    "Capture bid or facility amount, profit rate, term, and purpose. The engine records the Wa'd.",
    "Generate and accept the Murabaha offer. That locks cost plus disclosed profit.",
    "Kenya then buys float, seals possession, and runs the eight-step desk.",
    "Malaysia then writes a Bursa desk packet, pastes the e-certificate, and runs the twelve-step desk.",
  ],
  book: "This book is the customer side of the deal. Commodity legs live on Kenya Ops or Malaysia Manual Bridge. The customer still owes the Murabaha, not the float or the palm oil.",
};

export const APPLICATION_STEP_GUIDE = [
  { n: 1, title: "Pick the customer", body: "Use the same record as Customers. The application attaches to that person." },
  { n: 2, title: "Capture the facility", body: "Amount is the commodity cost (float or palm oil bid). Term is how many instalments they repay." },
  { n: 3, title: "Wa'd and offer", body: "The engine records the undertaking to purchase, then prices cost plus profit." },
  { n: 4, title: "Accept the offer", body: "Murabaha total locks. Nothing is disbursed yet." },
  { n: 5, title: "Open the right desk", body: "Kenya cases go to Kenya Ops. Malaysia cases go to the Suq Al-Sila' bridge." },
  { n: 6, title: "Run the commodity legs", body: "Buy, possess, sell to the customer, appoint the wakeel, then sell independently." },
  { n: 7, title: "Disburse", body: "Cash or wallet credit after the last leg. The customer still owes the Murabaha." },
];

export function previewApplicationDeal(input: {
  amount: string | number;
  termMonths: number;
  profitRatePct?: number;
  offer?: { cost_price: string; profit_amount: string; total_payable: string } | null;
}) {
  return computeKenyaDeal({
    amount: input.amount,
    termMonths: input.termMonths,
    profitRatePct: input.profitRatePct ?? DEFAULT_PROFIT_RATE_PCT,
    offer: input.offer,
  });
}

export function applicationUsesSpot(currency?: string | null) {
  return (currency || "KES").toUpperCase() === "KES";
}
