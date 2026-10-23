import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, fetchHealth, type OpsMetrics } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { HowItWorks, PageExplain } from "../components/PageExplain";
import { Alert, LoadingPanel, PageShell } from "../components/PageShell";
import { APPROVAL_LIMIT_DASHBOARD, HOW_IT_WORKS, PAGE_EXPLAINS } from "../config/pageExplainers";
import { NAV_ITEMS } from "../config/navigation";
import { canSeeNavItem, getHomePath, getRoleProfile } from "../config/roles";
import "../components/ui.css";

type QuickLink = { to: string; label: string; primary?: boolean };

const ROLE_QUICK_LINKS: Record<string, QuickLink[]> = {
  platform_admin: [
    { to: "/institutions", label: "Institutions", primary: true },
    { to: "/users", label: "Users" },
    { to: "/billing", label: "Billing" },
    { to: "/reconciliation", label: "Reconciliation" },
    { to: "/shariah", label: "Shariah Audit" },
  ],
  bti_ops: [
    { to: "/ops", label: "Ops Monitor", primary: true },
    { to: "/kenya", label: "Kenya Ops" },
    { to: "/sedania", label: "Sedania Financing" },
    { to: "/malaysia", label: "Malaysia Bridge" },
    { to: "/shariah", label: "Shariah Audit" },
  ],
  bti_finance: [
    { to: "/billing", label: "Billing & invoices", primary: true },
    { to: "/ops", label: "Ops Monitor" },
  ],
  institution_admin: [
    { to: "/users", label: "Users", primary: true },
    { to: "/kenya", label: "Kenya Ops" },
    { to: "/approvals", label: "Approvals" },
    { to: "/integrations", label: "Integrations" },
    { to: "/shariah", label: "Shariah Audit" },
  ],
  institution_ops: [
    { to: "/kenya", label: "Kenya Ops", primary: true },
    { to: "/sedania", label: "Sedania Financing" },
    { to: "/customers", label: "Customers" },
    { to: "/mobile-lend", label: "Mobile Lend" },
  ],
  fi_approver: [
    { to: "/approvals", label: "Approvals queue", primary: true },
    { to: "/mobile-lend", label: "Mobile Lend" },
    { to: "/applications", label: "Applications" },
  ],
  shariah_officer: [
    { to: "/shariah", label: "Shariah Audit", primary: true },
    { to: "/applications", label: "Applications" },
    { to: "/transactions", label: "Transactions" },
  ],
  reconciler: [
    { to: "/reconciliation", label: "Reconciliation", primary: true },
    { to: "/ops", label: "Ops Monitor" },
    { to: "/transactions", label: "Transactions" },
  ],
  read_only: [
    { to: "/applications", label: "Applications", primary: true },
    { to: "/transactions", label: "Transactions" },
    { to: "/customer", label: "Customer journey" },
  ],
  agent_dealer: [{ to: "/agent-dealers", label: "My float pool", primary: true }],
};

export function DashboardPage() {
  const { user, authEnabled } = useAuth();
  const profile = getRoleProfile(user?.role);
  const [metrics, setMetrics] = useState<OpsMetrics | null>(null);
  const [health, setHealth] = useState<string>("Checking…");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const canViewMetrics = !authEnabled || Boolean(user?.permissions.includes("view_metrics"));
  const quickLinks = useMemo(() => {
    const preferred = ROLE_QUICK_LINKS[user?.role || ""] || [
      { to: getHomePath(user?.role), label: "Open workspace", primary: true },
    ];
    return preferred.filter((link) => {
      const nav = NAV_ITEMS.find((item) => item.to === link.to);
      if (!nav) return link.to === "/customer" || link.to === "/";
      return canSeeNavItem(nav, user, authEnabled);
    });
  }, [user, authEnabled]);

  useEffect(() => {
    const metricsPromise = canViewMetrics ? api.getOpsMetrics().catch(() => null) : Promise.resolve(null);
    Promise.all([metricsPromise, fetchHealth().catch(() => null)])
      .then(([m, h]) => {
        setMetrics(m);
        setHealth(h?.status || "offline");
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load dashboard"))
      .finally(() => setLoading(false));
  }, [canViewMetrics]);

  return (
    <PageShell wide>
      <PageExplain content={PAGE_EXPLAINS["/"]} />
      <HowItWorks content={HOW_IT_WORKS["/"]} />
      {error ? <Alert tone="error">{error}</Alert> : null}

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>{profile.label} workspace</h2>
            <p className="muted">
              {profile.navDescription}. Scope: {user?.institution_name || profile.workspaceFallback}.
            </p>
          </div>
          <span className="badge info">{user?.role || "guest"}</span>
        </div>
        <div className="actions-row wrap" style={{ marginTop: "0.5rem" }}>
          {quickLinks.map((link) => (
            <Link
              key={link.to}
              className={link.primary ? "btn btn-primary btn-sm" : "btn btn-secondary btn-sm"}
              to={link.to}
            >
              {link.label}
            </Link>
          ))}
        </div>
      </section>

      {user?.role !== "agent_dealer" ? (
        <section className="panel">
          <h2>What an approval limit is</h2>
          <p className="muted" style={{ marginTop: 0 }}>
            {APPROVAL_LIMIT_DASHBOARD}
          </p>
        </section>
      ) : null}

      {loading ? (
        <LoadingPanel rows={4} />
      ) : canViewMetrics ? (
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>Engine snapshot</h2>
              <p className="muted">
                {profile.scope === "platform"
                  ? "Platform-wide counters for your role."
                  : "Tenant-scoped counters for your institution."}
              </p>
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
        </section>
      ) : (
        <section className="panel">
          <h2>No metrics for this role</h2>
          <p className="muted">
            Your login ({profile.label}) does not include engine telemetry. Use the shortcuts above for your desk.
          </p>
        </section>
      )}
    </PageShell>
  );
}
