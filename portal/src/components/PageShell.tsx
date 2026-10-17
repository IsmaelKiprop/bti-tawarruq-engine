import type { ReactNode } from "react";

export function PageShell({
  children,
  wide,
}: {
  children: ReactNode;
  wide?: boolean;
}) {
  return <div className={`page-shell${wide ? " page-shell-wide" : ""}`}>{children}</div>;
}

export function Alert({
  tone,
  children,
}: {
  tone: "error" | "success" | "info";
  children: ReactNode;
}) {
  return <div className={`alert alert-${tone}`} role="alert">{children}</div>;
}

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <p>{description}</p>
      {action}
    </div>
  );
}

export function LoadingPanel({ rows = 4 }: { rows?: number }) {
  return (
    <div className="skeleton-list" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="skeleton-line" />
      ))}
    </div>
  );
}

export function statusBadgeClass(status: string) {
  const normalized = status.toLowerCase();
  if (
    normalized.includes("complete") ||
    normalized.includes("confirm") ||
    normalized.includes("accept") ||
    normalized.includes("active") ||
    normalized === "done" ||
    normalized === "ok"
  ) {
    return "badge success";
  }
  if (
    normalized.includes("fail") ||
    normalized.includes("reject") ||
    normalized.includes("error") ||
    normalized.includes("escalat")
  ) {
    return "badge destructive";
  }
  if (
    normalized.includes("pending") ||
    normalized.includes("await") ||
    normalized.includes("draft") ||
    normalized.includes("offer")
  ) {
    return "badge warning";
  }
  if (normalized.includes("progress") || normalized.includes("current")) {
    return "badge info";
  }
  return "badge";
}
