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
export const PRODUCT_TYPES = ["Airtime"] as const;

export function deskPayload(record: { payload?: Record<string, unknown> } | null, key: string): Record<string, string> {
  const raw = record?.payload?.[key];
  if (!raw || typeof raw !== "object") return {};
  return Object.fromEntries(Object.entries(raw as Record<string, unknown>).map(([name, value]) => [name, value == null ? "" : String(value)]));
}

export function deskTimestamps(record: { payload?: Record<string, unknown> } | null): Record<string, string> {
  return deskPayload(record, "timestamps");
}

export const DESK_STATUS_LABELS: Record<string, string> = {
  draft: "Draft",
  pending_approval: "Pending approval",
  returned: "Returned",
  approved: "Approved",
  in_progress: "In progress",
  complete: "Complete",
};

export function deskStatusLabel(status?: string | null): string {
  if (!status) return "—";
  return DESK_STATUS_LABELS[status] || status.replace(/_/g, " ");
}

export function deskCustomerName(record: { payload?: Record<string, unknown> } | null): string {
  return deskPayload(record, "origination").customer_name || "";
}

export function deskDateKey(value?: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value.slice(0, 10);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

export function maxDeskStep(currentStep: number, status: string): number {
  if (status === "draft") return 1;
  if (status === "returned") return 1;
  if (status === "pending_approval") return 2;
  if (status === "complete") return 8;
  return Math.min(8, Math.max(1, currentStep));
}
