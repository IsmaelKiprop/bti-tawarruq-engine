import { useEffect, useState } from "react";
import { api, fetchHealth, type HealthPayload, type OpsMetrics } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Alert, LoadingPanel, PageShell } from "../components/PageShell";

const kpiClass =
  "rounded-sm border border-border bg-surface px-3 py-2.5 flex flex-col gap-0.5 min-h-[4.5rem]";

function formatUptime(seconds: number | undefined): string {
  if (seconds == null || Number.isNaN(seconds) || seconds < 0) return "—";
  const since = new Date(Date.now() - seconds * 1000);
  return `up since ${since.toLocaleString()}`;
}

function formatPct(value: number | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return `${Math.round(value)}%`;
}

export function DashboardPage() {
  const { user, authEnabled } = useAuth();
  const [metrics, setMetrics] = useState<OpsMetrics | null>(null);
  const [health, setHealth] = useState<HealthPayload | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const canViewMetrics = !authEnabled || Boolean(user?.permissions.includes("view_metrics"));
  const canSeeInstitutions = !authEnabled || Boolean(user?.permissions.includes("manage_institutions"));

  useEffect(() => {
    let alive = true;
    async function load() {
      setLoading(true);
      try {
        const metricsPromise = canViewMetrics ? api.getOpsMetrics().catch(() => null) : Promise.resolve(null);
        const [m, h] = await Promise.all([metricsPromise, fetchHealth().catch(() => null)]);
        if (!alive) return;
        setMetrics(m);
        setHealth(h);
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

  const uptimePct = health?.uptime_pct ?? (health?.status === "ok" ? 100 : 0);

  return (
    <PageShell wide>
      {error ? <Alert tone="error">{error}</Alert> : null}

      {loading && !health && !metrics ? (
        <LoadingPanel rows={2} />
      ) : (
        <div className={`grid gap-2 ${canSeeInstitutions ? "grid-cols-2 max-w-xl" : "max-w-xs"}`}>
          {canSeeInstitutions ? (
            <article className={kpiClass}>
              <span className="text-[0.7rem] uppercase tracking-wide text-muted">FIs</span>
              <strong className="text-xl font-semibold tabular-nums leading-none">
                {metrics?.institutions_total ?? "—"}
              </strong>
              <small className="text-xs text-muted">Institutions in the directory</small>
            </article>
          ) : null}
          <article className={kpiClass}>
            <span className="text-[0.7rem] uppercase tracking-wide text-muted">Uptime</span>
            <strong className="text-xl font-semibold tabular-nums leading-none">{formatPct(uptimePct)}</strong>
            <small className="text-xs text-muted">{formatUptime(health?.uptime_seconds)}</small>
          </article>
        </div>
      )}
    </PageShell>
  );
}
