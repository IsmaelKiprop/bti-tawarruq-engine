import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fetchHealth, type OpsMetrics } from "../api/client";
import { HowItWorks, PageExplain } from "../components/PageExplain";
import { Alert, LoadingPanel, PageShell } from "../components/PageShell";
import { HOW_IT_WORKS, PAGE_EXPLAINS } from "../config/pageExplainers";
import "../components/ui.css";

export function DashboardPage() {
  const [metrics, setMetrics] = useState<OpsMetrics | null>(null);
  const [health, setHealth] = useState<string>("Checking…");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([api.getOpsMetrics().catch(() => null), fetchHealth().catch(() => null)])
      .then(([m, h]) => {
        setMetrics(m);
        setHealth(h?.status || "offline");
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load dashboard"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <PageShell wide>
      <PageExplain content={PAGE_EXPLAINS["/"]} />
      <HowItWorks content={HOW_IT_WORKS["/"]} />
      {error ? <Alert tone="error">{error}</Alert> : null}
      {loading ? (
        <LoadingPanel rows={4} />
      ) : (
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Engine snapshot</h2>
              <p className="muted">Health and book counters for both Tawarruq tracks.</p>
            </div>
            <span className="badge info">{health}</span>
          </div>
          <div className="info-grid">
            <div className="info-item">
              <span>Applications</span>
              <strong>{metrics?.applications_total ?? "—"}</strong>
            </div>
            <div className="info-item">
              <span>Transactions</span>
              <strong>{metrics?.transactions_total ?? "—"}</strong>
            </div>
            <div className="info-item">
              <span>Manual bridge pending</span>
              <strong>{metrics?.manual_bridge_pending ?? "—"}</strong>
            </div>
            <div className="info-item">
              <span>Kenya mode</span>
              <strong>{metrics?.kenya_integration_mode ?? "—"}</strong>
            </div>
          </div>
          <div className="actions-row wrap" style={{ marginTop: "1rem" }}>
            <Link className="btn btn-primary btn-sm" to="/sedania">
              Sedania Financing
            </Link>
            <Link className="btn btn-secondary btn-sm" to="/kenya">
              Kenya Ops
            </Link>
            <Link className="btn btn-secondary btn-sm" to="/malaysia">
              Malaysia Bridge
            </Link>
            <Link className="btn btn-secondary btn-sm" to="/applications">
              Applications
            </Link>
            <Link className="btn btn-secondary btn-sm" to="/customer">
              Customer journey
            </Link>
          </div>
        </section>
      )}
    </PageShell>
  );
}
