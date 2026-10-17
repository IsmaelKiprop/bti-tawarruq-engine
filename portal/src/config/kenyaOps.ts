export const DEFAULT_PROFIT_RATE_PCT = 5;

export type KenyaQueueId =
  | "all"
  | "eligibility"
  | "purchase"
  | "possession"
  | "murabaha"
  | "wakala"
  | "settlement"
  | "repay"
  | "done";

export const KENYA_QUEUES: { id: KenyaQueueId; label: string; hint: string }[] = [
  { id: "all", label: "All", hint: "Every open Kenya case on this book." },
  { id: "eligibility", label: "Eligibility", hint: "Waiting on facility application and agency mandate." },
  { id: "purchase", label: "Purchase", hint: "Waiting to buy float from MNO or agent dealer." },
  { id: "possession", label: "Possession", hint: "Waiting on supplier transfer / possession seal." },
  { id: "murabaha", label: "Murabaha", hint: "Offer, accept, contract, or Leg 2 title transfer." },
  { id: "wakala", label: "Wakala", hint: "Customer must appoint Buruuj as selling agent." },
  { id: "settlement", label: "Settlement", hint: "Independent sale, clearing, or disbursement." },
  { id: "repay", label: "Repay", hint: "Disbursed cases collecting Murabaha instalments." },
  { id: "done", label: "Done", hint: "Completed Kenya journeys." },
];

export const KENYA_STEP_GUIDE = [
  { n: 1, title: "Facility application", body: "Pick the customer, capture amount and term, open the case." },
  { n: 2, title: "Float purchase", body: "Buy float from the MNO or an agent dealer pool." },
  { n: 3, title: "Possession", body: "Seal constructive possession with the supplier receipt before Murabaha." },
  { n: 4, title: "Murabaha", body: "Lock cost plus profit, customer accepts, contract and Leg 2." },
  { n: 5, title: "Wakala", body: "Customer appoints Buruuj as wakeel for the independent sale." },
  { n: 6, title: "Spot sale", body: "Sell float to a secondary purchaser (No-Inah)." },
  { n: 7, title: "Clearing", body: "Settle cash legs after the commodity sale." },
  { n: 8, title: "Disburse & repay", body: "Credit the customer wallet, then collect Murabaha instalments." },
];

export type KenyaDealPreview = {
  cost: number;
  profitRatePct: number;
  profit: number;
  total: number;
  installment: number;
  termMonths: number;
  currency: string;
};

function toNumber(value: string | number | null | undefined): number {
  if (typeof value === "number") return Number.isFinite(value) ? value : 0;
  const n = Number(String(value ?? "").replace(/,/g, ""));
  return Number.isFinite(n) ? n : 0;
}

export function computeKenyaDeal(input: {
  amount: string | number;
  termMonths: number;
  profitRatePct?: number;
  currency?: string;
  offer?: { cost_price: string; profit_amount: string; total_payable: string } | null;
}): KenyaDealPreview {
  const termMonths = Math.max(1, Number(input.termMonths) || 1);
  const profitRatePct = input.profitRatePct ?? DEFAULT_PROFIT_RATE_PCT;
  const currency = (input.currency || "KES").toUpperCase();

  if (input.offer) {
    const cost = toNumber(input.offer.cost_price);
    const profit = toNumber(input.offer.profit_amount);
    const total = toNumber(input.offer.total_payable) || cost + profit;
    return {
      cost,
      profitRatePct: cost > 0 ? Number(((profit / cost) * 100).toFixed(2)) : profitRatePct,
      profit,
      total,
      installment: total / termMonths,
      termMonths,
      currency,
    };
  }

  const cost = toNumber(input.amount);
  const profit = Number(((cost * profitRatePct) / 100).toFixed(2));
  const total = Number((cost + profit).toFixed(2));
  return {
    cost,
    profitRatePct,
    profit,
    total,
    installment: total / termMonths,
    termMonths,
    currency,
  };
}
