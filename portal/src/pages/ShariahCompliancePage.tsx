import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Institution, KenyaOpsCase, ShariahAuditEntry } from "../api/client";
import { DealTape } from "../components/DealTape";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";

export function ShariahCompliancePage() {
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [institutionId, setInstitutionId] = useState("");
  const [cases, setCases] = useState<KenyaOpsCase[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [audit, setAudit] = useState<ShariahAuditEntry[]>([]);
  const [chain, setChain] = useState<Record<string, unknown> | null>(null);
  const [integrity, setIntegrity] = useState<{
    valid: boolean;
    possession_sealed: boolean;
    entry_count: number;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    api
      .listInstitutions()
      .then((items) => {
        setInstitutions(items);
        if (items[0]) setInstitutionId(items[0].id);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    api
      .listKenyaOpsCases("all")
      .then(setCases)
      .catch(() => setCases([]));
  }, []);

  async function verifyChain() {
    setError("");
    setMessage("");
    try {
      const result = await api.verifyShariahChain(institutionId || undefined);
      setChain(result);
      setMessage("Institution ledger chain verified.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chain verify failed");
    }
  }

  async function loadApplicationAudit(id: string) {
    setSelectedId(id);
    setError("");
    try {
      const [entries, verify] = await Promise.all([
        api.getKenyaShariahAudit(id),
        api.verifyKenyaShariah(id),
      ]);
      setAudit(entries);
      setIntegrity({
        valid: verify.valid,
        possession_sealed: verify.possession_sealed,
        entry_count: verify.entry_count,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load audit");
    }
  }

  async function exportLedger(format: "csv" | "json") {
    setError("");
    try {
      await api.downloadShariahExport({
        format,
        institution_id: institutionId || undefined,
        application_id: selectedId || undefined,
      });
      setMessage(`Shariah export (${format}) downloaded.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    }
  }

  return (
    <PageShell wide>
      <div className="page-grid">
        <section className="panel">
          <h2>Regulatory export</h2>
          {loading ? (
            <LoadingPanel rows={3} />
          ) : (
            <>
              <label>
                Institution
                <select
                  className="select-input"
                  value={institutionId}
                  onChange={(e) => setInstitutionId(e.target.value)}
                >
                  {institutions.map((inst) => (
                    <option key={inst.id} value={inst.id}>
                      {inst.name}
                    </option>
                  ))}
                </select>
              </label>
              <div className="actions-row wrap" style={{ marginTop: "0.75rem" }}>
                <button type="button" className="btn btn-primary btn-sm" onClick={verifyChain}>
                  Verify hash chain
                </button>
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => exportLedger("csv")}>
                  Export CSV
                </button>
                <button type="button" className="btn btn-secondary btn-sm" onClick={() => exportLedger("json")}>
                  Export JSON
                </button>
              </div>
            </>
          )}
          {chain && (
            <pre className="code-block" style={{ marginTop: "1rem" }}>
              {JSON.stringify(chain, null, 2)}
            </pre>
          )}
        </section>

        <section className="panel">
          <h2>Application integrity</h2>
          <p className="muted">Pick a Kenya case to verify possession seal + ledger</p>
          <select
            className="select-input"
            value={selectedId}
            onChange={(e) => e.target.value && loadApplicationAudit(e.target.value)}
          >
            <option value="">Select application…</option>
            {cases.map((c) => (
              <option key={c.application_id} value={c.application_id}>
                {c.customer_name} · {c.application_id.slice(0, 8)}…
              </option>
            ))}
          </select>
          {integrity && (
            <ul className="status-list" style={{ marginTop: "1rem" }}>
              <li className="status-row">
                <span>Valid</span>
                <span className={`badge ${integrity.valid ? "success" : "warning"}`}>
                  {integrity.valid ? "Yes" : "No"}
                </span>
              </li>
              <li className="status-row">
                <span>Possession sealed</span>
                <span className={`badge ${integrity.possession_sealed ? "success" : "warning"}`}>
                  {integrity.possession_sealed ? "Yes" : "No"}
                </span>
              </li>
              <li className="status-row">
                <span>Entries</span>
                <span className="meta">{integrity.entry_count}</span>
              </li>
            </ul>
          )}
          {selectedId && (
            <Link className="btn btn-secondary btn-sm" style={{ marginTop: "0.75rem" }} to={`/kenya?case=${selectedId}`}>
              Open in Kenya ops
            </Link>
          )}
          {selectedId
            ? (() => {
                const selectedCase = cases.find((item) => item.application_id === selectedId);
                if (!selectedCase) return null;
                return (
                  <DealTape
                    amount={selectedCase.amount_requested}
                    termMonths={selectedCase.term_months}
                    offer={selectedCase.offer}
                    installmentsTotal={selectedCase.installments_total}
                    installmentsPaid={selectedCase.installments_paid}
                  />
                );
              })()
            : null}
        </section>

        {(error || message) && (
          <div className="span-2">
            {error && <Alert tone="error">{error}</Alert>}
            {message && <Alert tone="success">{message}</Alert>}
          </div>
        )}

        <section className="panel span-2">
          <h2>Audit entries</h2>
          {audit.length === 0 ? (
            <EmptyState
              title="No entries loaded"
              description="Select an application to inspect Step_ID, Asset_Ref, actors, and payload hashes."
            />
          ) : (
            <ul className="audit-list">
              {audit.map((entry) => (
                <li key={entry.id}>
                  <span className="audit-action">{entry.step_id}</span>
                  <span className="meta">
                    {entry.actor_from} → {entry.actor_to}
                  </span>
                  <span className="meta mono">asset: {entry.asset_ref_no || "—"}</span>
                  <span className="meta mono">hash: {entry.payload_hash.slice(0, 16)}…</span>
                  <span className="meta">{new Date(entry.timestamp).toLocaleString()}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </PageShell>
  );
}
