import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, fetchHealth, type OpsMetrics } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Alert, LoadingPanel, PageShell } from "../components/PageShell";
import { NAV_ITEMS } from "../config/navigation";
import { canSeeNavItem, getHomePath, getRoleProfile } from "../config/roles";

type QuickLink = { to: string; label: string; primary?: boolean };

const ROLE_QUICK_LINKS: Record<string, QuickLink[]> = {
  platform_admin: [
    { to: "/institutions", label: "Institutions", primary: true },
    { to: "/users", label: "Users" },
    { to: "/billing", label: "Billing" },
    { to: "/reconciliation", label: "Recon" },
    { to: "/documentation", label: "Docs" },
  ],
  bti_ops: [
    { to: "/ops", label: "Ops", primary: true },
    { to: "/kenya", label: "Kenya" },
    { to: "/sedania", label: "Sedania" },
    { to: "/malaysia", label: "Malaysia" },
    { to: "/documentation", label: "Docs" },
  ],
  bti_finance: [
    { to: "/billing", label: "Billing", primary: true },
    { to: "/ops", label: "Ops" },
    { to: "/documentation", label: "Docs" },
  ],
  institution_admin: [
    { to: "/users", label: "Users", primary: true },
    { to: "/kenya", label: "Kenya" },
    { to: "/approvals", label: "Approvals" },
    { to: "/documentation", label: "Docs" },
  ],
  institution_ops: [
    { to: "/kenya", label: "Kenya", primary: true },
    { to: "/sedania", label: "Sedania" },
    { to: "/customers", label: "Customers" },
    { to: "/documentation", label: "Docs" },
  ],
  fi_approver: [
    { to: "/approvals", label: "Approvals", primary: true },
    { to: "/mobile-lend", label: "Mobile Lend" },
    { to: "/documentation", label: "Docs" },
  ],
  shariah_officer: [
    { to: "/shariah", label: "Shariah", primary: true },
    { to: "/applications", label: "Applications" },
    { to: "/documentation", label: "Docs" },
  ],
  reconciler: [
    { to: "/reconciliation", label: "Recon", primary: true },
    { to: "/ops", label: "Ops" },
    { to: "/documentation", label: "Docs" },
  ],
  read_only: [
    { to: "/applications", label: "Applications", primary: true },
    { to: "/transactions", label: "Transactions" },
    { to: "/documentation", label: "Docs" },
  ],
  agent_dealer: [{ to: "/agent-dealers", label: "My float", primary: true }],
};

function money(value: number | undefined | null): string {
  if (value == null || Number.isNaN(value)) return "—";
  return new Intl.NumberFormat(undefined, {
    maximumFractionDigits: 0,
  }).format(value);
}

function pct(value: number | undefined | null): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${value.toFixed(1)}%`;
}

function statusRows(map: Record<string, number> | undefined, limit = 5) {
  if (!map) return [];
  return Object.entries(map)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit);
}

const pillClass =
  "inline-flex items-center rounded-sm border border-border bg-surface-elevated px-2 py-0.5 text-[0.7rem] uppercase tracking-wide text-muted";
const kpiClass =
  "rounded-sm border border-border bg-surface px-3 py-2.5 flex flex-col gap-0.5 min-h-[4.5rem]";
const panelClass = "rounded-sm border border-border bg-surface p-3 flex flex-col gap-2 min-w-0";

export function DashboardPage() {
  const { user, authEnabled } = useAuth();
  const profile = getRoleProfile(user?.role);
  const [metrics, setMetrics] = useState<OpsMetrics | null>(null);
  const [health, setHealth] = useState<string>("…");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const canViewMetrics = !authEnabled || Boolean(user?.permissions.includes("view_metrics"));
  const quickLinks = useMemo(() => {
    const preferred = ROLE_QUICK_LINKS[user?.role || ""] || [
      { to: getHomePath(user?.role), label: "Workspace", primary: true },
    ];
    return preferred.filter((link) => {
      const nav = NAV_ITEMS.find((item) => item.to === link.to);
      if (!nav) return link.to === "/documentation" || link.to === "/";
      return canSeeNavItem(nav, user, authEnabled);
    });
  }, [user, authEnabled]);

  useEffect(() => {
    let alive = true;
    async function load() {
      setLoading(true);
      try {
        const metricsPromise = canViewMetrics ? api.getOpsMetrics().catch(() => null) : Promise.resolve(null);
        const [m, h] = await Promise.all([metricsPromise, fetchHealth().catch(() => null)]);
        if (!alive) return;
        setMetrics(m);
        setHealth(h?.status || "offline");
        setError("");
      } catch (err) {
        if (!alive) return;
        setError(err instanceof Error ? err.message : "Failed to load dashboard");
      } finally {
        if (alive) setLoading(false);
      }
    }
    load();
    const timer = window.setInterval(load, 30_000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, [canViewMetrics]);

  const appStatuses = statusRows(metrics?.applications_by_status);
  const txnStatuses = statusRows(metrics?.transactions_by_status);
  const maxApp = Math.max(1, ...appStatuses.map(([, n]) => n));
  const maxTxn = Math.max(1, ...txnStatuses.map(([, n]) => n));
  const healthLive = health === "ok" || health === "degraded";

  return (
    <PageShell wide>
      {error ? <Alert tone="error">{error}</Alert> : null}

      <section className="flex flex-col gap-3">
        <header className="grid gap-3 rounded-sm border border-border bg-surface p-3 sm:grid-cols-[1fr_auto] lg:grid-cols-[1fr_auto_auto] lg:items-center">
          <div className="min-w-0">
            <h2 className="m-0 text-lg font-semibold tracking-tight text-foreground">{profile.label}</h2>
            <p className="m-0 mt-0.5 text-sm text-muted">
              {user?.institution_name || profile.workspaceFallback}
              {metrics?.timestamp ? ` · updated ${new Date(metrics.timestamp).toLocaleTimeString()}` : null}
            </p>
          </div>
          <div className="flex flex-wrap gap-1.5">
            <span className={`${pillClass}${healthLive ? " border-success/40 text-success" : ""}`}>{health}</span>
            <span className={pillClass}>{user?.role || "guest"}</span>
            <span className={pillClass}>{metrics?.kenya_integration_mode || "—"}</span>
          </div>
          <nav className="flex flex-wrap gap-1.5 sm:col-span-2 lg:col-span-1 lg:justify-end">
            {quickLinks.map((link) => (
              <Link
                key={link.to}
                className={link.primary ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm"}
                to={link.to}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </header>

        {loading && !metrics ? (
          <LoadingPanel rows={5} />
        ) : canViewMetrics && metrics ? (
          <>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-4">
              <article className={kpiClass}>
                <span className="text-[0.7rem] uppercase tracking-wide text-muted">Applications</span>
                <strong className="text-xl font-semibold tabular-nums leading-none">{metrics.applications_total}</strong>
                <small className="text-xs text-muted">
                  {metrics.applications_open ?? 0} open · {metrics.applications_completed ?? 0} done
                </small>
              </article>
              <article className={kpiClass}>
                <span className="text-[0.7rem] uppercase tracking-wide text-muted">Transactions</span>
                <strong className="text-xl font-semibold tabular-nums leading-none">{metrics.transactions_total}</strong>
                <small className="text-xs text-muted">
                  {metrics.transactions_open ?? 0} in flight · {metrics.manual_bridge_pending} bridge
                </small>
              </article>
              <article className={kpiClass}>
                <span className="text-[0.7rem] uppercase tracking-wide text-muted">Approvals queue</span>
                <strong className="text-xl font-semibold tabular-nums leading-none">{metrics.pending_approvals ?? 0}</strong>
                <small className="text-xs text-muted">Pending maker-checker</small>
              </article>
              <article className={kpiClass}>
                <span className="text-[0.7rem] uppercase tracking-wide text-muted">Completion</span>
                <strong className="text-xl font-semibold tabular-nums leading-none">{pct(metrics.completion_rate_pct)}</strong>
                <small className="text-xs text-muted">{metrics.applications_failed ?? 0} failed / escalated</small>
              </article>
              <article className={kpiClass}>
                <span className="text-[0.7rem] uppercase tracking-wide text-muted">Book requested</span>
                <strong className="text-xl font-semibold tabular-nums leading-none">{money(metrics.book_amount_requested)}</strong>
                <small className="text-xs text-muted">Sum of amount_requested</small>
              </article>
              <article className={kpiClass}>
                <span className="text-[0.7rem] uppercase tracking-wide text-muted">Disbursed</span>
                <strong className="text-xl font-semibold tabular-nums leading-none">{money(metrics.disbursed_volume)}</strong>
                <small className="text-xs text-muted">{money(metrics.week_disbursed_volume)} last 7 days</small>
              </article>
              <article className={`${kpiClass} border-primary/35 bg-primary/5`}>
                <span className="text-[0.7rem] uppercase tracking-wide text-muted">Projected 30d volume</span>
                <strong className="text-xl font-semibold tabular-nums leading-none text-primary">
                  {money(metrics.projected_30d_volume)}
                </strong>
                <small className="text-xs text-muted">7-day run rate × 30/7</small>
              </article>
              <article className={`${kpiClass} border-primary/35 bg-primary/5`}>
                <span className="text-[0.7rem] uppercase tracking-wide text-muted">Projected open book</span>
                <strong className="text-xl font-semibold tabular-nums leading-none text-primary">
                  {money(metrics.projected_open_book)}
                </strong>
                <small className="text-xs text-muted">Book × completion rate</small>
              </article>
            </div>

            <div className="grid gap-2 lg:grid-cols-3">
              <section className={panelClass}>
                <div className="flex items-baseline justify-between gap-2">
                  <h3 className="m-0 text-sm font-semibold">Application mix</h3>
                  <Link className="text-xs text-primary hover:underline" to="/applications">
                    View
                  </Link>
                </div>
                <ul className="m-0 flex list-none flex-col gap-2 p-0">
                  {appStatuses.length === 0 ? (
                    <li className="muted text-sm">No applications in scope yet.</li>
                  ) : (
                    appStatuses.map(([status, count]) => (
                      <li key={status}>
                        <div className="mb-1 flex justify-between gap-2 text-xs">
                          <span className="truncate text-muted">{status}</span>
                          <strong className="tabular-nums">{count}</strong>
                        </div>
                        <div className="h-1.5 overflow-hidden rounded-sm bg-border/60">
                          <span
                            className="block h-full rounded-sm bg-primary"
                            style={{ width: `${(count / maxApp) * 100}%` }}
                          />
                        </div>
                      </li>
                    ))
                  )}
                </ul>
              </section>

              <section className={panelClass}>
                <div className="flex items-baseline justify-between gap-2">
                  <h3 className="m-0 text-sm font-semibold">Transaction mix</h3>
                  <Link className="text-xs text-primary hover:underline" to="/transactions">
                    View
                  </Link>
                </div>
                <ul className="m-0 flex list-none flex-col gap-2 p-0">
                  {txnStatuses.length === 0 ? (
                    <li className="muted text-sm">No commodity transactions yet.</li>
                  ) : (
                    txnStatuses.map(([status, count]) => (
                      <li key={status}>
                        <div className="mb-1 flex justify-between gap-2 text-xs">
                          <span className="truncate text-muted">{status}</span>
                          <strong className="tabular-nums">{count}</strong>
                        </div>
                        <div className="h-1.5 overflow-hidden rounded-sm bg-border/60">
                          <span
                            className="block h-full rounded-sm bg-accent"
                            style={{ width: `${(count / maxTxn) * 100}%` }}
                          />
                        </div>
                      </li>
                    ))
                  )}
                </ul>
              </section>

              <section className={panelClass}>
                <div className="flex items-baseline justify-between gap-2">
                  <h3 className="m-0 text-sm font-semibold">Platform pulse</h3>
                  <Link className="text-xs text-primary hover:underline" to="/ops">
                    Ops
                  </Link>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {[
                    ["Institutions", metrics.institutions_total],
                    ["API keys", metrics.active_api_keys],
                    ["Webhooks", metrics.active_webhooks],
                    ["Audit today", metrics.audit_events_today],
                    ["HTTP req", metrics.http_requests_total],
                    ["HTTP err", metrics.http_errors_total],
                    ["Latency avg", `${Math.round(metrics.http_latency_ms_avg)} ms`],
                    ["Auth", metrics.auth_enabled ? "on" : "off"],
                  ].map(([label, value]) => (
                    <div key={String(label)} className="rounded-sm border border-border/70 bg-surface-elevated px-2 py-1.5">
                      <span className="block text-[0.65rem] uppercase tracking-wide text-muted">{label}</span>
                      <strong className="text-sm tabular-nums">{value}</strong>
                    </div>
                  ))}
                </div>
              </section>
            </div>
          </>
        ) : (
          <section className={`${panelClass} max-w-xl`}>
            <h3 className="m-0 text-sm font-semibold">{profile.label} desk</h3>
            <p className="muted m-0 text-sm">
              This role does not include telemetry. Use shortcuts above
              {user?.role !== "agent_dealer" ? (
                <>
                  {" "}
                  or open <Link to="/documentation">Documentation</Link>
                </>
              ) : null}
              .
            </p>
          </section>
        )}
      </section>
    </PageShell>
  );
}
