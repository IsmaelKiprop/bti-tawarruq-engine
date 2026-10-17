import type { Application } from "../api/client";

export function isGeneratedCustomerRef(value?: string | null) {
  return Boolean(value && /^CUST-/i.test(value.trim()));
}

export function displayCustomerName(app: Pick<Application, "customer_name" | "customer_ref">) {
  const name = app.customer_name?.trim();
  if (name && !isGeneratedCustomerRef(name)) return name;
  return "Name not recorded";
}

export function formatMoney(currency: string | undefined, amount: string | number) {
  const code = (currency || "KES").toUpperCase();
  const numeric = typeof amount === "number" ? amount : Number(amount);
  if (Number.isFinite(numeric)) {
    return `${code} ${numeric.toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  }
  return `${code} ${amount}`;
}

export function formatWorkflowLabel(status: string, phase?: string | null) {
  const raw = (phase || status || "").replace(/_/g, " ").trim();
  if (!raw) return "Unknown";
  return raw.charAt(0).toUpperCase() + raw.slice(1);
}
