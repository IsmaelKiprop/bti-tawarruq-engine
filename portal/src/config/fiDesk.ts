export const DESK_STEPS = [
  { n: 1, id: "origination", title: "Origination" },
  { n: 2, id: "approval", title: "Approval" },
  { n: 3, id: "initiate", title: "Initiate Tawarruq" },
  { n: 4, id: "murabaha", title: "Murabaha Sale" },
  { n: 5, id: "resale", title: "Commodity Resale" },
  { n: 6, id: "proceeds", title: "Resale Proceeds" },
  { n: 7, id: "clearing", title: "Clearing" },
  { n: 8, id: "complete", title: "Complete" },
] as const;

export const DOCUMENT_TYPES = ["National ID", "Passport", "Alien ID", "Other"];
export const PRODUCT_TYPES = ["Airtime float", "Mobile money float", "Other"];

export function deskPayload(record: { payload?: Record<string, unknown> } | null, key: string): Record<string, string> {
  const raw = record?.payload?.[key];
  if (!raw || typeof raw !== "object") return {};
  return Object.fromEntries(Object.entries(raw as Record<string, unknown>).map(([name, value]) => [name, value == null ? "" : String(value)]));
}

export function deskTimestamps(record: { payload?: Record<string, unknown> } | null): Record<string, string> {
  return deskPayload(record, "timestamps");
}

export function maxDeskStep(currentStep: number, status: string): number {
  if (status === "draft") return 1;
  if (status === "returned") return 1;
  if (status === "pending_approval") return 2;
  if (status === "complete") return 8;
  return Math.min(8, Math.max(1, currentStep));
}
