import { Fragment, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api, type AuditEvent, type AuditFeed, type Institution } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { IconChevronRight, IconInstitutions, IconShariah, IconUsers } from "../components/icons";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";

const GROUP_FILTERS = [
  { value: "", label: "All groups" },
  { value: "auth", label: "Auth" },
  { value: "users", label: "Users" },
  { value: "institutions", label: "Institutions" },
  { value: "integrations", label: "Integrations" },
  { value: "deals", label: "Deals" },
  { value: "kenya", label: "Kenya" },
  { value: "malaysia", label: "Malaysia" },
  { value: "sedania", label: "Sedania" },
  { value: "approvals", label: "Approvals" },
  { value: "finance", label: "Finance" },
  { value: "ops", label: "Ops" },
  { value: "ui", label: "UI" },
];

const pillClass =
  "inline-flex items-center gap-1.5 rounded-sm border border-border bg-surface-elevated px-2 py-0.5 text-[0.7rem] uppercase tracking-wide text-muted";

function flattenEvents(feed: AuditFeed): AuditEvent[] {
  const fromFlat = feed.events?.length ? feed.events : [];
  const fromGroups = feed.groups.flatMap((group) => group.events);
  const map = new Map<string, AuditEvent>();
  for (const event of [...fromFlat, ...fromGroups]) {
    map.set(event.id, event);
  }
  return [...map.values()].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
  );
}

function groupTone(group: string | null | undefined) {
  const key = (group || "").toLowerCase();
  if (key === "auth" || key === "users") return "bg-primary/15 text-primary border-primary/30";
  if (key === "institutions" || key === "integrations") return "bg-accent/15 text-accent-foreground border-accent/35";
  if (key === "kenya" || key === "malaysia" || key === "sedania" || key === "deals") {
    return "bg-success/10 text-success border-success/30";
  }
  if (key === "approvals" || key === "finance") return "bg-warning/15 text-foreground border-warning/40";
  return "bg-surface-elevated text-muted border-border";
}

function detailSnippet(event: AuditEvent) {
  if (event.details) return event.details;
  const bits = [
    event.http_method,
    event.http_path,
    event.http_status != null ? `→ ${event.http_status}` : null,
  ].filter(Boolean);
  return bits.length ? bits.join(" ") : "Portal or API operation";
}

function metaChip(event: AuditEvent) {
  if (event.entity_id) return `${event.entity_type || "entity"}=${event.entity_id}`;
  if (event.evidence_ref) return `evidence=${event.evidence_ref}`;
  if (event.http_path) return event.http_path;
  return null;
}

export function AuditTrailPage() {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const canPickInstitution =
    user?.role === "platform_admin" || user?.role === "bti_ops" || user?.role === "bti_finance";

  const [feed, setFeed] = useState<AuditFeed | null>(null);
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState("");
  const [openId, setOpenId] = useState("");

  const institutionId = searchParams.get("institution") || "";
  const actionGroup = searchParams.get("group") || "";

  const institutionNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of institutions) map.set(item.id, item.name);
    return map;
  }, [institutions]);

  const scopeLabel = useMemo(() => {
    if (feed?.cross_tenant) {
      if (!institutionId) return "All institutions";
      return institutionNameById.get(institutionId) || institutionId;
    }
    return user?.institution_name || "Your institution";
  }, [feed, institutionId, institutionNameById, user?.institution_name]);

  const rows = useMemo(() => (feed ? flattenEvents(feed) : []), [feed]);

  async function load(isRefresh = false) {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const [audit, books] = await Promise.all([
        api.getOpsAuditFeed({
          institution_id: institutionId || undefined,
          action_group: actionGroup || undefined,
          limit: 300,
          grouped: true,
        }),
        canPickInstitution
          ? api.listInstitutions().catch(() => [] as Institution[])
          : Promise.resolve([] as Institution[]),
      ]);
      setFeed(audit);
      setInstitutions(books);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load audit feed");
      setFeed(null);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    void load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [institutionId, actionGroup, canPickInstitution]);

  function patchParams(next: Record<string, string>) {
    const params = new URLSearchParams(searchParams);
    for (const [key, value] of Object.entries(next)) {
      if (!value) params.delete(key);
      else params.set(key, value);
    }
    setSearchParams(params);
  }

  return (
    <PageShell wide>
      <section className="audit-page">
        <header className="audit-page-header">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <IconShariah size={16} className="text-muted" />
              <h2>Audit trail</h2>
            </div>
            <p className="audit-sub">
              Grouped portal and API operations · {scopeLabel}
              {refreshing ? " · refreshing" : null}
            </p>
          </div>
          <div className="audit-filters">
            {canPickInstitution ? (
              <label>
                <span className="inline-flex items-center gap-1">
                  <IconInstitutions size={12} />
                  Institution
                </span>
                <select value={institutionId} onChange={(e) => patchParams({ institution: e.target.value })}>
                  <option value="">All</option>
                  {institutions.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <label>
              <span className="inline-flex items-center gap-1">
                <IconUsers size={12} />
                Group
              </span>
              <select value={actionGroup} onChange={(e) => patchParams({ group: e.target.value })}>
                {GROUP_FILTERS.map((item) => (
                  <option key={item.value || "all"} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={() => void load(true)}
              disabled={refreshing}
            >
              Refresh
            </button>
          </div>
        </header>

        {error ? <Alert tone="error">{error}</Alert> : null}

        <section className="audit-logs-panel">
          <div className="audit-logs-head">
            <div>
              <h3>Audit logs</h3>
              <p>Latest mutating calls and logins in scope</p>
            </div>
            <span className={pillClass}>
              {loading && !feed ? "…" : `${rows.length} record${rows.length === 1 ? "" : "s"}`}
            </span>
          </div>

          {loading && !feed ? (
            <LoadingPanel rows={5} />
          ) : rows.length === 0 ? (
            <EmptyState
              title="No audit events"
              description="Mutating API calls and logins appear here once operators use the desks."
            />
          ) : (
            <div className="audit-table-wrap">
              <table className="audit-table">
                <thead>
                  <tr>
                    <th className="col-action">Action</th>
                    <th className="col-actor">Actor</th>
                    <th className="col-institution">Institution</th>
                    <th className="col-group">Group</th>
                    <th className="col-when">When</th>
                    <th className="col-toggle" />
                  </tr>
                </thead>
                <tbody>
                  {rows.map((event) => {
                    const open = openId === event.id;
                    const chip = metaChip(event);
                    const institutionLabel = event.institution_id
                      ? institutionNameById.get(event.institution_id) || event.institution_id
                      : feed?.cross_tenant
                        ? "Platform"
                        : scopeLabel;
                    return (
                      <Fragment key={event.id}>
                        <tr className={open ? "bg-surface-elevated" : undefined}>
                          <td className="col-action" data-label="Action">
                            <button
                              type="button"
                              className="audit-action-btn"
                              onClick={() => setOpenId(open ? "" : event.id)}
                              aria-expanded={open}
                            >
                              <strong>{event.action}</strong>
                              <span className="audit-detail">{detailSnippet(event)}</span>
                              {chip ? <span className="audit-chip">{chip}</span> : null}
                            </button>
                          </td>
                          <td className="col-actor" data-label="Actor">
                            <span className="audit-cell-inline">
                              <IconUsers size={14} className="shrink-0 text-muted" />
                              <span>{event.actor || "system"}</span>
                            </span>
                          </td>
                          <td className="col-institution" data-label="Institution">
                            <span className="audit-cell-inline">
                              <IconInstitutions size={14} className="shrink-0 text-muted" />
                              <span>{institutionLabel}</span>
                            </span>
                          </td>
                          <td className="col-group" data-label="Group">
                            <span
                              className={`inline-flex rounded-sm border px-1.5 py-0.5 text-[0.7rem] uppercase tracking-wide ${groupTone(event.action_group)}`}
                            >
                              {event.action_group || "ops"}
                            </span>
                          </td>
                          <td className="col-when audit-when" data-label="When">
                            {new Date(event.timestamp).toLocaleString()}
                          </td>
                          <td className="col-toggle">
                            <button
                              type="button"
                              className="audit-expand"
                              aria-label={open ? "Hide details" : "Show details"}
                              aria-expanded={open}
                              onClick={() => setOpenId(open ? "" : event.id)}
                            >
                              <IconChevronRight
                                size={14}
                                className={`transition-transform ${open ? "rotate-90" : ""}`}
                              />
                            </button>
                          </td>
                        </tr>
                        {open ? (
                          <tr className="audit-detail-row">
                            <td colSpan={6}>
                              <div className="audit-detail-grid">
                                <DetailCell label="HTTP">
                                  {event.http_method || event.http_path || event.http_status != null
                                    ? `${event.http_method || ""} ${event.http_path || ""}${event.http_status != null ? ` → ${event.http_status}` : ""}`.trim()
                                    : "—"}
                                </DetailCell>
                                <DetailCell label="Entity">
                                  {event.entity_type || event.entity_id
                                    ? `${event.entity_type || "entity"} ${event.entity_id || ""}`.trim()
                                    : "—"}
                                </DetailCell>
                                <DetailCell label="Evidence">{event.evidence_ref || "—"}</DetailCell>
                                <DetailCell label="Group id">
                                  <span className="font-mono text-xs">{event.group_id || "—"}</span>
                                </DetailCell>
                                {event.details ? (
                                  <DetailCell label="Details" className="audit-detail-span">
                                    {event.details}
                                  </DetailCell>
                                ) : null}
                                {event.institution_id && canPickInstitution ? (
                                  <div className="audit-detail-span">
                                    <Link
                                      className="text-xs text-primary hover:underline"
                                      to={`/institutions/${event.institution_id}`}
                                    >
                                      Open institution
                                    </Link>
                                  </div>
                                ) : null}
                              </div>
                            </td>
                          </tr>
                        ) : null}
                      </Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </section>
    </PageShell>
  );
}

function DetailCell({
  label,
  children,
  className = "",
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`min-w-0 ${className}`}>
      <span className="block text-[0.65rem] uppercase tracking-wide text-muted">{label}</span>
      <span className="break-words text-foreground">{children}</span>
    </div>
  );
}
