import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, fetchHealth, type HealthPayload, type InstitutionSummary, type OpsMetrics } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";
import { INSTITUTION_TYPES, REGULATORS } from "../config/fiKyc";

const kpiClass =
  "rounded-sm border border-border bg-surface px-3 py-2.5 flex flex-col gap-0.5 min-h-[4.5rem]";

function formatUptime(seconds: number | undefined): string {
  if (seconds == null || Number.isNaN(seconds) || seconds < 0) return "-";
  const since = new Date(Date.now() - seconds * 1000);
  return `up since ${since.toLocaleString()}`;
}

function formatPct(value: number | undefined): string {
  if (value == null || Number.isNaN(value)) return "-";
  return `${Math.round(value)}%`;
}

function typeLabel(key: string) {
  return INSTITUTION_TYPES.find((opt) => opt.value === key)?.label || key.replace(/_/g, " ");
}

function regulatorLabel(key: string) {
  return REGULATORS.find((opt) => opt.value === key)?.label || key.replace(/_/g, " ");
}

const SLICE_FILLS = [
  "var(--color-foreground)",
  "var(--color-muted)",
  "var(--color-primary)",
  "var(--color-border)",
  "var(--color-secondary)",
];

function PieChart({ slices }: { slices: { label: string; value: number }[] }) {
  const total = slices.reduce((sum, slice) => sum + slice.value, 0);
  if (!total) {
    return <p className="m-0 text-sm text-muted">No customer institutions yet.</p>;
  }
  let angle = -90;
  const paths = slices.map((slice, index) => {
    const sweep = (slice.value / total) * 360;
    const start = angle;
    angle += sweep;
    const large = sweep > 180 ? 1 : 0;
    const startRad = (start * Math.PI) / 180;
    const endRad = (angle * Math.PI) / 180;
    const x1 = 50 + 40 * Math.cos(startRad);
    const y1 = 50 + 40 * Math.sin(startRad);
    const x2 = 50 + 40 * Math.cos(endRad);
    const y2 = 50 + 40 * Math.sin(endRad);
    return {
      label: slice.label,
      value: slice.value,
      d: `M 50 50 L ${x1} ${y1} A 40 40 0 ${large} 1 ${x2} ${y2} Z`,
      fill: SLICE_FILLS[index % SLICE_FILLS.length],
      opacity: 0.35 + ((index % 4) * 0.15),
    };
  });
  return (
    <div className="grid gap-3 sm:grid-cols-[8rem_1fr] sm:items-center">
      <svg viewBox="0 0 100 100" className="h-32 w-32" role="img" aria-label="Distribution chart">
        {paths.map((path) => (
          <path key={path.label} d={path.d} fill={path.fill} fillOpacity={path.opacity} />
        ))}
      </svg>
      <ul className="m-0 grid list-none gap-1 p-0 text-sm">
        {paths.map((path) => (
          <li key={path.label} className="flex items-center justify-between gap-3">
            <span>{path.label}</span>
            <strong className="tabular-nums">{path.value}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

function BarChart({ bars }: { bars: { label: string; value: number }[] }) {
  const max = Math.max(...bars.map((bar) => bar.value), 1);
  if (!bars.length) {
    return <p className="m-0 text-sm text-muted">No onboarding dates yet.</p>;
  }
  return (
    <div className="grid gap-2" role="img" aria-label="Onboarded financial institutions by month">
      {bars.map((bar) => (
        <div key={bar.label} className="grid grid-cols-[4.5rem_1fr_2rem] items-center gap-2 text-sm">
          <span className="text-muted">{bar.label}</span>
          <div className="h-5 rounded-sm border border-border bg-surface-elevated">
            <div
              className="h-full rounded-sm bg-foreground/70"
              style={{ width: `${Math.max(8, (bar.value / max) * 100)}%` }}
            />
          </div>
          <strong className="tabular-nums">{bar.value}</strong>
        </div>
      ))}
    </div>
  );
}

export function DashboardPage() {
  const { user, authEnabled } = useAuth();
  const [metrics, setMetrics] = useState<OpsMetrics | null>(null);
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [summary, setSummary] = useState<InstitutionSummary | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const canViewMetrics = !authEnabled || Boolean(user?.permissions.includes("view_metrics"));
  const isSuperAdmin = user?.role === "platform_admin" || (!authEnabled && Boolean(user?.permissions.includes("manage_institutions")));
  const canSeeInstitutions = isSuperAdmin || Boolean(user?.permissions.includes("manage_institutions"));

  useEffect(() => {
    let alive = true;
    async function load() {
      setLoading(true);
      try {
        const metricsPromise = canViewMetrics ? api.getOpsMetrics().catch(() => null) : Promise.resolve(null);
        const summaryPromise = canSeeInstitutions ? api.getInstitutionSummary().catch(() => null) : Promise.resolve(null);
        const [m, h, s] = await Promise.all([metricsPromise, fetchHealth().catch(() => null), summaryPromise]);
        if (!alive) return;
        setMetrics(m);
        setHealth(h);
        setSummary(s);
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
  }, [canViewMetrics, canSeeInstitutions]);

  const uptimePct = health?.uptime_pct ?? (health?.status === "ok" ? 100 : 0);
  const typeSlices = useMemo(
    () =>
      Object.entries(summary?.by_type || {})
        .filter(([, value]) => value > 0)
        .map(([key, value]) => ({ label: typeLabel(key), value })),
    [summary],
  );
  const regulatorSlices = useMemo(
    () =>
      Object.entries(summary?.by_regulator || {})
        .filter(([, value]) => value > 0)
        .map(([key, value]) => ({ label: regulatorLabel(key), value })),
    [summary],
  );
  const monthBars = useMemo(
    () => Object.entries(summary?.by_month || {}).map(([label, value]) => ({ label, value })),
    [summary],
  );

  return (
    <PageShell wide>
      {error ? <Alert tone="error">{error}</Alert> : null}

      {canSeeInstitutions ? (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <p className="m-0 text-sm text-muted">Customer financial institutions on this engine.</p>
          <Link className="btn btn-primary" to="/institutions/onboard">
            Onboard financial institution
          </Link>
        </div>
      ) : null}

      {loading && !health && !metrics && !summary ? (
        <LoadingPanel rows={2} />
      ) : (
        <div className={`grid gap-2 ${canSeeInstitutions ? "grid-cols-2 sm:grid-cols-4" : "max-w-xs"}`}>
          {canSeeInstitutions ? (
            <>
              <article className={kpiClass}>
                <span className="text-[0.7rem] uppercase tracking-wide text-muted">Active</span>
                <strong className="text-xl font-semibold tabular-nums leading-none">{summary?.active ?? metrics?.institutions_total ?? "-"}</strong>
                <small className="text-xs text-muted">Ready for FI Admin</small>
              </article>
              <article className={kpiClass}>
                <span className="text-[0.7rem] uppercase tracking-wide text-muted">Dormant</span>
                <strong className="text-xl font-semibold tabular-nums leading-none">{summary?.dormant ?? 0}</strong>
                <small className="text-xs text-muted">Paused tenants</small>
              </article>
              <article className={kpiClass}>
                <span className="text-[0.7rem] uppercase tracking-wide text-muted">Deactivated</span>
                <strong className="text-xl font-semibold tabular-nums leading-none">{summary?.deactivated ?? 0}</strong>
                <small className="text-xs text-muted">Closed tenants</small>
              </article>
            </>
          ) : null}
          <article className={kpiClass}>
            <span className="text-[0.7rem] uppercase tracking-wide text-muted">Uptime</span>
            <strong className="text-xl font-semibold tabular-nums leading-none">{formatPct(uptimePct)}</strong>
            <small className="text-xs text-muted">{formatUptime(health?.uptime_seconds)}</small>
          </article>
        </div>
      )}

      {canSeeInstitutions && !loading && (summary?.total ?? 0) === 0 ? (
        <EmptyState
          title="No customer institution yet"
          description="Onboard a bank or SACCO. Super Admin activate is immediate."
          action={
            <Link className="btn btn-primary btn-sm" to="/institutions/onboard">
              Onboard financial institution
            </Link>
          }
        />
      ) : null}

      {canSeeInstitutions && summary && summary.total > 0 ? (
        <div className="mt-3 grid gap-3 lg:grid-cols-3">
          <section className="rounded-sm border border-border bg-surface p-3">
            <h3 className="m-0 mb-3 text-sm font-semibold">By institution type</h3>
            <PieChart slices={typeSlices} />
          </section>
          <section className="rounded-sm border border-border bg-surface p-3">
            <h3 className="m-0 mb-3 text-sm font-semibold">By regulator</h3>
            <PieChart slices={regulatorSlices} />
          </section>
          <section className="rounded-sm border border-border bg-surface p-3">
            <h3 className="m-0 mb-3 text-sm font-semibold">Onboarded over time</h3>
            <BarChart bars={monthBars} />
          </section>
        </div>
      ) : null}
    </PageShell>
  );
}
