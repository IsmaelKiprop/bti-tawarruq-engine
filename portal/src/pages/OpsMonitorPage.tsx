import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Application, AuthContext, OpsMetrics } from "../api/client";
import { BookTape } from "../components/DealTape";
import { HowItWorks, PageExplain } from "../components/PageExplain";
import { Alert, LoadingPanel, PageShell } from "../components/PageShell";
import { previewApplicationDeal } from "../config/applicationOps";
import { HOW_IT_WORKS, PAGE_EXPLAINS } from "../config/pageExplainers";
import { displayCustomerName, formatMoney, formatWorkflowLabel } from "../lib/display";
import "../components/ui.css";

export function OpsMonitorPage() {
  const [metrics, setMetrics] = useState<OpsMetrics | null>(null);
  const [auth, setAuth] = useState<AuthContext | null>(null);
  const [activeApps, setActiveApps] = useState<Application[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    async function load() {
      setLoading(true);
      setError("");
      try {
        const [metricsData, authData, allApps] = await Promise.all([
          api.getOpsMetrics(),
          api.getAuthContext(),
          api.listApplications().catch(() => [] as Application[]),
        ]);
        if (!active) return;
        setMetrics(metricsData);
        setAuth(authData);
        setActiveApps(allApps.filter((a) => ["in_progress", "offer_accepted", "eligibility_pending"].includes(a.status)));
      } catch (err) {
        if (active) {
          setError(err instanceof Error ? err.message : "Failed to load ops metrics");
        }
      } finally {
        if (active) setLoading(false);
      }
    }

    load();
    const timer = window.setInterval(load, 30000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  return (
    <PageShell wide>
      <PageExplain content={PAGE_EXPLAINS["/ops"]} />
      <HowItWorks content={HOW_IT_WORKS["/ops"]} />
      <BookTape
        items={activeApps.map((app) => ({
          amount: app.amount_requested,
          termMonths: app.term_months,
          currency: app.currency,
        }))}
        title="Active journey numbers"
      />
      {error && <Alert tone="error">{error}</Alert>}

      {auth && (
        <section className="panel">
          <h2>Auth context</h2>
          <ul className="status-list">
            <StatusRow label="Auth enabled" ok={auth.auth_enabled} okText="Yes" noText="No (dev mode)" />
            <StatusRow label="Role" value={auth.role ?? "none"} />
            <StatusRow
              label="Platform admin"
              ok={auth.is_platform_admin}
              okText="Yes"
              noText="No"
            />
            <StatusRow label="Permissions" value={auth.permissions.join(", ") || "all (dev)"} />
          </ul>
        </section>
      )}

      {loading ? (
        <LoadingPanel rows={6} />
      ) : metrics ? (
        <>
          <section className="stat-cards">
            <StatCard label="Applications" value={metrics.applications_total} hint="In scope" />
            <StatCard label="Transactions" value={metrics.transactions_total} hint="In scope" />
            <StatCard
              label="Manual bridge"
              value={metrics.manual_bridge_pending}
              hint="Pending e-certificates"
              tone={metrics.manual_bridge_pending > 0 ? "destructive" : undefined}
            />
            <StatCard label="HTTP errors" value={metrics.http_errors_total} hint="Since process start" />
          </section>

          <div className="dashboard-grid">
            <section className="panel">
              <h2>Applications by status</h2>
              <KeyValueList data={metrics.applications_by_status} empty="No applications yet" />
            </section>
            <section className="panel">
              <h2>Transactions by status</h2>
              <KeyValueList data={metrics.transactions_by_status} empty="No transactions yet" />
            </section>
            <section className="panel">
              <h2>Platform counters</h2>
              <ul className="status-list">
                <StatusRow label="Institutions" value={String(metrics.institutions_total)} />
                <StatusRow label="Active webhooks" value={String(metrics.active_webhooks)} />
                <StatusRow label="Active API keys" value={String(metrics.active_api_keys)} />
                <StatusRow label="Audit events today" value={String(metrics.audit_events_today)} />
              </ul>
            </section>
            <section className="panel">
              <h2>HTTP telemetry</h2>
              <ul className="status-list">
                <StatusRow label="Requests" value={String(metrics.http_requests_total)} />
                <StatusRow label="Avg latency" value={`${metrics.http_latency_ms_avg} ms`} />
                <StatusRow label="Kenya mode" value={metrics.kenya_integration_mode} />
                <StatusRow
                  label="Amanah writes"
                  ok={metrics.amanah_write_enabled}
                  okText="Enabled"
                  noText="Disabled"
                />
              </ul>
            </section>
            <section className="panel span-2">
              <h2>Active Journeys</h2>
              <p className="muted" style={{ marginBottom: "0.75rem" }}>
                Applications in progress. Amount is cost. Murabaha is the 5% preview until the offer locks.
              </p>
              {activeApps.length === 0 ? (
                <p className="muted">No active journeys right now.</p>
              ) : (
                <div className="table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Customer</th>
                        <th>Ref</th>
                        <th>Cost / Murabaha</th>
                        <th>Status</th>
                        <th></th>
                      </tr>
                    </thead>
                    <tbody>
                      {activeApps.map((app) => (
                        <tr key={app.id}>
                          <td data-label="Customer">{displayCustomerName(app)}</td>
                          <td data-label="Ref" className="mono" style={{ fontSize: "0.75rem" }}>{app.customer_ref}</td>
                          <td data-label="Cost / Murabaha">
                            {(() => {
                              const deal = previewApplicationDeal({
                                amount: app.amount_requested,
                                termMonths: app.term_months,
                              });
                              return (
                                <>
                                  <div>{formatMoney(app.currency, deal.cost)}</div>
                                  <div className="meta">Murabaha {formatMoney(app.currency, deal.total)}</div>
                                </>
                              );
                            })()}
                          </td>
                          <td data-label="Status">
                            <span className={`badge ${app.status === "in_progress" ? "info" : "warning"}`}>
                              {formatWorkflowLabel(app.status, app.current_phase)}
                            </span>
                          </td>
                          <td>
                            <Link className="btn btn-secondary btn-sm" to={`/customer/${app.customer_ref}`} target="_blank">
                              Journey
                            </Link>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="panel span-2">
              <h2>Top paths</h2>
              <KeyValueList data={metrics.http_top_paths} empty="No requests recorded yet" />
              <p className="muted meta">
                Prometheus scrape: <code>/metrics</code> · Last updated {new Date(metrics.timestamp).toLocaleString()}
              </p>
            </section>
          </div>
        </>
      ) : null}
    </PageShell>
  );
}

function StatCard({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string | number;
  hint: string;
  tone?: "destructive";
}) {
  return (
    <article className={`stat-card${tone ? ` tone-${tone}` : ""}`}>
      <span className="stat-card-label">{label}</span>
      <strong className="stat-card-value">{value}</strong>
      <span className="stat-card-hint">{hint}</span>
    </article>
  );
}

function StatusRow({
  label,
  ok,
  okText = "Yes",
  noText = "No",
  value,
}: {
  label: string;
  ok?: boolean;
  okText?: string;
  noText?: string;
  value?: string;
}) {
  return (
    <li className="status-row">
      <span>{label}</span>
      {value !== undefined ? (
        <span className="meta">{value}</span>
      ) : (
        <span className={`badge ${ok ? "success" : "warning"}`}>{ok ? okText : noText}</span>
      )}
    </li>
  );
}

function KeyValueList({ data, empty }: { data: Record<string, number>; empty: string }) {
  const entries = Object.entries(data);
  if (entries.length === 0) {
    return <p className="muted">{empty}</p>;
  }
  return (
    <ul className="status-list">
      {entries.map(([key, count]) => (
        <li key={key} className="status-row">
          <span>{key}</span>
          <span className="badge">{count}</span>
        </li>
      ))}
    </ul>
  );
}
