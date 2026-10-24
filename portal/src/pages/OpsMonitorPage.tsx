import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, Application, AuthContext, OpsMetrics } from "../api/client";
import { Alert, LoadingPanel, PageShell, statusBadgeClass } from "../components/PageShell";
import { IconExternal, IconMonitor } from "../components/icons";
import { previewApplicationDeal } from "../config/applicationOps";
import { displayCustomerName, formatMoney, formatWorkflowLabel } from "../lib/display";

const pillClass =
  "inline-flex items-center gap-1.5 rounded-sm border border-border bg-surface-elevated px-2 py-0.5 text-[0.7rem] uppercase tracking-wide text-muted";
const kpiClass =
  "rounded-sm border border-border bg-surface px-3 py-2.5 flex flex-col gap-0.5 min-h-[4.75rem]";
const panelClass = "rounded-sm border border-border bg-surface p-3 flex flex-col gap-2.5 min-w-0";

function rankEntries(map: Record<string, number> | undefined, limit = 6) {
  if (!map) return [];
  return Object.entries(map)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit);
}

function errorRate(metrics: OpsMetrics) {
  if (!metrics.http_requests_total) return 0;
  return (metrics.http_errors_total / metrics.http_requests_total) * 100;
}

export function OpsMonitorPage() {
  const [metrics, setMetrics] = useState<OpsMetrics | null>(null);
  const [auth, setAuth] = useState<AuthContext | null>(null);
  const [activeApps, setActiveApps] = useState<Application[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    let alive = true;

    async function load(isRefresh: boolean) {
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      setError("");
      try {
        const [metricsData, authData, allApps] = await Promise.all([
          api.getOpsMetrics(),
          api.getAuthContext(),
          api.listApplications().catch(() => [] as Application[]),
        ]);
        if (!alive) return;
        setMetrics(metricsData);
        setAuth(authData);
        setActiveApps(
          allApps.filter((a) =>
            ["in_progress", "offer_accepted", "eligibility_pending"].includes(a.status),
          ),
        );
      } catch (err) {
        if (alive) {
          setError(err instanceof Error ? err.message : "Failed to load ops metrics");
        }
      } finally {
        if (!alive) return;
        setLoading(false);
        setRefreshing(false);
      }
    }

    void load(false);
    const timer = window.setInterval(() => void load(true), 30_000);
    return () => {
      alive = false;
      window.clearInterval(timer);
    };
  }, []);

  const appStatuses = useMemo(() => rankEntries(metrics?.applications_by_status), [metrics]);
  const txnStatuses = useMemo(() => rankEntries(metrics?.transactions_by_status), [metrics]);
  const topPaths = useMemo(() => rankEntries(metrics?.http_top_paths, 8), [metrics]);
  const httpStatuses = useMemo(() => rankEntries(metrics?.http_by_status, 6), [metrics]);

  const maxApp = Math.max(1, ...appStatuses.map(([, n]) => n));
  const maxTxn = Math.max(1, ...txnStatuses.map(([, n]) => n));
  const maxPath = Math.max(1, ...topPaths.map(([, n]) => n));
  const maxHttp = Math.max(1, ...httpStatuses.map(([, n]) => n));

  const bridgeAlert = (metrics?.manual_bridge_pending ?? 0) > 0;
  const errorAlert = (metrics?.http_errors_total ?? 0) > 0;
  const latencyHot = (metrics?.http_latency_ms_avg ?? 0) >= 500;
  const errPct = metrics ? errorRate(metrics) : 0;

  return (
    <PageShell wide>
      <section className="flex flex-col gap-3">
        <header className="grid gap-3 rounded-sm border border-border bg-surface p-3 sm:grid-cols-[1fr_auto] lg:items-center">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <IconMonitor size={16} className="text-muted" />
              <h2 className="m-0 text-lg font-semibold tracking-tight text-foreground">Ops Monitor</h2>
            </div>
            <p className="m-0 mt-0.5 text-sm text-muted">
              Engine telemetry and live desks
              {metrics?.timestamp ? ` · ${new Date(metrics.timestamp).toLocaleString()}` : null}
              {refreshing ? " · refreshing" : null}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-1.5 sm:justify-end">
            <span className={`${pillClass} border-success/40 text-success`}>
              <span className="size-1.5 rounded-full bg-success" aria-hidden />
              Live · 30s
            </span>
            {auth ? (
              <>
                <span className={pillClass}>{auth.role ?? "none"}</span>
                <span className={pillClass}>
                  {auth.auth_enabled ? "Auth on" : "Auth off"}
                </span>
                {auth.is_platform_admin ? <span className={pillClass}>Platform</span> : null}
              </>
            ) : null}
            {metrics ? (
              <span className={pillClass}>{metrics.kenya_integration_mode}</span>
            ) : null}
            <Link className="btn btn-secondary btn-sm" to="/kenya">
              Kenya
            </Link>
            <Link className="btn btn-secondary btn-sm" to="/malaysia">
              Malaysia
            </Link>
            <Link className="btn btn-secondary btn-sm" to="/approvals">
              Approvals
            </Link>
          </div>
        </header>

        {error ? <Alert tone="error">{error}</Alert> : null}

        {loading && !metrics ? (
          <LoadingPanel rows={8} />
        ) : metrics ? (
          <>
            <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
              <Kpi
                label="Manual bridge"
                value={metrics.manual_bridge_pending}
                hint="Pending e-certificates"
                tone={bridgeAlert ? "alert" : undefined}
                to="/malaysia"
              />
              <Kpi
                label="HTTP errors"
                value={metrics.http_errors_total}
                hint={`${errPct.toFixed(2)}% of requests`}
                tone={errorAlert ? "alert" : undefined}
              />
              <Kpi
                label="Avg latency"
                value={`${Math.round(metrics.http_latency_ms_avg)} ms`}
                hint={latencyHot ? "Elevated" : "Since process start"}
                tone={latencyHot ? "warn" : undefined}
              />
              <Kpi
                label="Approvals queue"
                value={metrics.pending_approvals ?? 0}
                hint="Maker-checker waiting"
                to="/approvals"
              />
            </div>

            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
              <Kpi label="Applications" value={metrics.applications_total} hint={`${metrics.applications_open ?? 0} open`} compact />
              <Kpi label="Transactions" value={metrics.transactions_total} hint={`${metrics.transactions_open ?? 0} in flight`} compact />
              <Kpi label="Institutions" value={metrics.institutions_total} hint="In directory" compact />
              <Kpi label="API keys" value={metrics.active_api_keys} hint="Active" compact />
              <Kpi label="Webhooks" value={metrics.active_webhooks} hint="Active" compact />
              <Kpi label="Audit today" value={metrics.audit_events_today} hint="Events logged" compact />
            </div>

            <div className="grid gap-2 lg:grid-cols-3">
              <section className={panelClass}>
                <div className="flex items-baseline justify-between gap-2">
                  <h3 className="m-0 text-sm font-semibold">Application mix</h3>
                  <Link className="text-xs text-primary hover:underline" to="/applications">
                    View
                  </Link>
                </div>
                <Distribution rows={appStatuses} max={maxApp} empty="No applications yet" bar="bg-primary" />
              </section>

              <section className={panelClass}>
                <div className="flex items-baseline justify-between gap-2">
                  <h3 className="m-0 text-sm font-semibold">Transaction mix</h3>
                  <Link className="text-xs text-primary hover:underline" to="/transactions">
                    View
                  </Link>
                </div>
                <Distribution rows={txnStatuses} max={maxTxn} empty="No transactions yet" bar="bg-accent" />
              </section>

              <section className={panelClass}>
                <div className="flex items-baseline justify-between gap-2">
                  <h3 className="m-0 text-sm font-semibold">HTTP status</h3>
                  <span className="text-xs tabular-nums text-muted">{metrics.http_requests_total} req</span>
                </div>
                <Distribution rows={httpStatuses} max={maxHttp} empty="No requests yet" bar="bg-foreground/70" />
                <div className="mt-auto grid grid-cols-2 gap-1.5 border-t border-border pt-2">
                  <MiniStat
                    label="Amanah writes"
                    value={metrics.amanah_write_enabled ? "On" : "Off"}
                    ok={metrics.amanah_write_enabled}
                  />
                  <MiniStat label="Auth" value={metrics.auth_enabled ? "On" : "Off"} ok={metrics.auth_enabled} />
                </div>
              </section>
            </div>

            <div className="grid gap-2 xl:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
              <section className={panelClass}>
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h3 className="m-0 text-sm font-semibold">Active journeys</h3>
                  <span className="text-xs tabular-nums text-muted">{activeApps.length} open</span>
                </div>
                {activeApps.length === 0 ? (
                  <p className="m-0 text-sm text-muted">No applications in progress right now.</p>
                ) : (
                  <div className="table-wrap -mx-1">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Customer</th>
                          <th>Ref</th>
                          <th>Cost / Murabaha</th>
                          <th>Status</th>
                          <th />
                        </tr>
                      </thead>
                      <tbody>
                        {activeApps.map((app) => {
                          const deal = previewApplicationDeal({
                            amount: app.amount_requested,
                            termMonths: app.term_months,
                          });
                          return (
                            <tr key={app.id}>
                              <td data-label="Customer">{displayCustomerName(app)}</td>
                              <td data-label="Ref" className="mono text-xs">
                                {app.customer_ref}
                              </td>
                              <td data-label="Cost / Murabaha">
                                <div className="tabular-nums">{formatMoney(app.currency, deal.cost)}</div>
                                <div className="meta">Murabaha {formatMoney(app.currency, deal.total)}</div>
                              </td>
                              <td data-label="Status">
                                <span className={statusBadgeClass(app.status)}>
                                  {formatWorkflowLabel(app.status, app.current_phase)}
                                </span>
                              </td>
                              <td>
                                <Link
                                  className="btn btn-secondary btn-sm inline-flex items-center gap-1"
                                  to={`/customer/${encodeURIComponent(app.customer_ref)}`}
                                  target="_blank"
                                  rel="noreferrer"
                                >
                                  Journey
                                  <IconExternal size={12} />
                                </Link>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>

              <section className={panelClass}>
                <div className="flex items-baseline justify-between gap-2">
                  <h3 className="m-0 text-sm font-semibold">Top paths</h3>
                  <span className="text-xs text-muted">
                    Prometheus <code className="text-[0.7rem]">/metrics</code>
                  </span>
                </div>
                {topPaths.length === 0 ? (
                  <p className="m-0 text-sm text-muted">No requests recorded yet.</p>
                ) : (
                  <ul className="m-0 flex list-none flex-col gap-2 p-0">
                    {topPaths.map(([path, count]) => (
                      <li key={path}>
                        <div className="mb-1 flex justify-between gap-2 text-xs">
                          <span className="truncate font-mono text-muted" title={path}>
                            {path}
                          </span>
                          <strong className="shrink-0 tabular-nums">{count}</strong>
                        </div>
                        <div className="h-1 overflow-hidden rounded-sm bg-border/60">
                          <span
                            className="block h-full rounded-sm bg-primary/80"
                            style={{ width: `${(count / maxPath) * 100}%` }}
                          />
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </div>
          </>
        ) : null}
      </section>
    </PageShell>
  );
}

function Kpi({
  label,
  value,
  hint,
  tone,
  compact,
  to,
}: {
  label: string;
  value: string | number;
  hint: string;
  tone?: "alert" | "warn";
  compact?: boolean;
  to?: string;
}) {
  const toneClass =
    tone === "alert"
      ? "border-destructive/40 bg-destructive/5"
      : tone === "warn"
        ? "border-warning/50 bg-warning/10"
        : "";
  const valueClass =
    tone === "alert" ? "text-destructive" : tone === "warn" ? "text-warning" : "text-foreground";

  const body = (
    <article className={`${kpiClass} ${toneClass} ${compact ? "min-h-[4rem]" : ""}`}>
      <span className="text-[0.7rem] uppercase tracking-wide text-muted">{label}</span>
      <strong className={`font-semibold tabular-nums leading-none ${compact ? "text-lg" : "text-2xl"} ${valueClass}`}>
        {value}
      </strong>
      <small className="text-xs text-muted">{hint}</small>
    </article>
  );

  if (!to) return body;
  return (
    <Link to={to} className="block no-underline text-inherit hover:opacity-90 focus-visible:outline-none">
      {body}
    </Link>
  );
}

function Distribution({
  rows,
  max,
  empty,
  bar,
}: {
  rows: [string, number][];
  max: number;
  empty: string;
  bar: string;
}) {
  if (rows.length === 0) {
    return <p className="m-0 text-sm text-muted">{empty}</p>;
  }
  return (
    <ul className="m-0 flex list-none flex-col gap-2 p-0">
      {rows.map(([key, count]) => (
        <li key={key}>
          <div className="mb-1 flex justify-between gap-2 text-xs">
            <span className="truncate text-muted">{key}</span>
            <strong className="tabular-nums">{count}</strong>
          </div>
          <div className="h-1.5 overflow-hidden rounded-sm bg-border/60">
            <span className={`block h-full rounded-sm ${bar}`} style={{ width: `${(count / max) * 100}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

function MiniStat({ label, value, ok }: { label: string; value: string; ok?: boolean }) {
  return (
    <div className="rounded-sm border border-border/70 bg-surface-elevated px-2 py-1.5">
      <span className="block text-[0.65rem] uppercase tracking-wide text-muted">{label}</span>
      <strong className={`text-sm tabular-nums ${ok === false ? "text-warning" : ""}`}>{value}</strong>
    </div>
  );
}
