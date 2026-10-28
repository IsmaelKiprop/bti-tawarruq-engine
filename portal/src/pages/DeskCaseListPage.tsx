import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type DeskCase } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";
import { deskCustomerName, deskDateKey, deskPayload, deskStatusLabel } from "../config/fiDesk";

const filterClass = "flex min-w-[10rem] flex-col gap-1 text-xs uppercase tracking-wide text-muted";
const inputClass = "rounded-sm border border-border bg-surface-elevated px-2.5 py-1.5 text-sm normal-case tracking-normal text-foreground";

type DeskListMode = "queue" | "workflows";

function formatWhen(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export function DeskCaseListPage({ mode }: { mode: DeskListMode }) {
  const { user } = useAuth();
  const isQueue = mode === "queue";
  const [items, setItems] = useState<DeskCase[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [officer, setOfficer] = useState("all");
  const [customer, setCustomer] = useState("all");
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const [date, setDate] = useState("");

  useEffect(() => {
    setLoading(true);
    api
      .listDeskCases(user?.institution_id || undefined)
      .then((rows) => {
        setItems(rows);
        setError("");
      })
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load cases"))
      .finally(() => setLoading(false));
  }, [user?.institution_id]);

  const officers = useMemo(() => {
    const names = new Set(items.map((item) => item.requested_by_name).filter(Boolean) as string[]);
    return Array.from(names).sort();
  }, [items]);

  const customers = useMemo(() => {
    const names = new Set(items.map((item) => deskCustomerName(item)).filter(Boolean));
    return Array.from(names).sort();
  }, [items]);

  const statuses = useMemo(() => {
    const values = new Set(items.map((item) => item.status).filter(Boolean));
    return Array.from(values);
  }, [items]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return items.filter((item) => {
      if (isQueue && officer !== "all" && item.requested_by_name !== officer) return false;
      if (!isQueue && customer !== "all" && deskCustomerName(item) !== customer) return false;
      if (status !== "all" && item.status !== status) return false;
      if (date && deskDateKey(item.created_at) !== date) return false;
      if (needle) {
        const hay = [deskCustomerName(item), item.requested_by_name, item.assigned_approver_name]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();
        if (!hay.includes(needle)) return false;
      }
      return true;
    });
  }, [items, isQueue, officer, customer, query, status, date]);

  return (
    <PageShell wide>
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="m-0 text-lg font-semibold">{isQueue ? "Approval Queue" : "All Workflows"}</h2>
          <p className="muted m-0 mt-1 text-sm">
            {isQueue
              ? `${filtered.length} of ${items.length} requests assigned to you.`
              : `${filtered.length} of ${items.length} origination cases.`}
          </p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          {isQueue ? (
            <label className={filterClass}>
              Search
              <input
                className={inputClass}
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Customer or requester"
              />
            </label>
          ) : null}
          {isQueue ? (
            <label className={filterClass}>
              Requesting officer
              <select className={inputClass} value={officer} onChange={(e) => setOfficer(e.target.value)}>
                <option value="all">All</option>
                {officers.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <label className={filterClass}>
              Customer
              <select className={inputClass} value={customer} onChange={(e) => setCustomer(e.target.value)}>
                <option value="all">All</option>
                {customers.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label className={filterClass}>
            Status
            <select className={inputClass} value={status} onChange={(e) => setStatus(e.target.value)}>
              <option value="all">All</option>
              {statuses.map((value) => (
                <option key={value} value={value}>
                  {deskStatusLabel(value)}
                </option>
              ))}
            </select>
          </label>
          <label className={filterClass}>
            {isQueue ? "Date requested" : "Date"}
            <input className={inputClass} type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </label>
        </div>
      </header>

      {error ? <Alert tone="error">{error}</Alert> : null}

      <section className="panel">
        {loading ? (
          <LoadingPanel rows={4} />
        ) : filtered.length === 0 ? (
          <EmptyState
            title={isQueue ? "No requests in this queue" : "No workflows"}
            description="Clear a filter, or open Origination to start a case."
          />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  {isQueue ? (
                    <>
                      <th>Customer</th>
                      <th>Requesting officer</th>
                    </>
                  ) : (
                    <th>Customer</th>
                  )}
                  <th>Amount</th>
                  <th>Status</th>
                  <th>{isQueue ? "Date requested" : "Date"}</th>
                  <th>Step</th>
                  <th className="w-[1%]">Open</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => {
                  const orig = deskPayload(item, "origination");
                  return (
                    <tr key={item.id}>
                      {isQueue ? (
                        <>
                          <td>
                            <div className="font-medium">{deskCustomerName(item) || "—"}</div>
                            <div className="meta">{item.id.slice(0, 8)}</div>
                          </td>
                          <td>{item.requested_by_name || "—"}</td>
                        </>
                      ) : (
                        <td>
                          <div className="font-medium">{deskCustomerName(item) || "—"}</div>
                          <div className="meta">{item.id.slice(0, 8)}</div>
                        </td>
                      )}
                      <td>{orig.approved_facility_amount || "—"}</td>
                      <td>{deskStatusLabel(item.status)}</td>
                      <td>{formatWhen(item.created_at)}</td>
                      <td>{item.current_step}</td>
                      <td>
                        <Link className="btn btn-secondary btn-sm" to={`/origination?case=${item.id}`}>
                          Open
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
    </PageShell>
  );
}
