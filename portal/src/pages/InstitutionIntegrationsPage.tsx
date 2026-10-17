import { FormEvent, useEffect, useState } from "react";
import { api, type Institution, type InstitutionIntegration } from "../api/client";
import { HowItWorks, PageExplain } from "../components/PageExplain";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";
import { HOW_IT_WORKS, PAGE_EXPLAINS } from "../config/pageExplainers";
import "../components/ui.css";

export function InstitutionIntegrationsPage() {
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [institutionId, setInstitutionId] = useState("");
  const [integration, setIntegration] = useState<InstitutionIntegration | null>(null);
  const [status, setStatus] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [mpesaEnv, setMpesaEnv] = useState("sandbox");
  const [mpesaShortcode, setMpesaShortcode] = useState("");

  async function loadInstitutions() {
    const rows = await api.listInstitutions();
    setInstitutions(rows);
    if (!institutionId && rows[0]) setInstitutionId(rows[0].id);
  }

  async function loadIntegration(id: string) {
    if (!id) return;
    setLoading(true);
    setError("");
    try {
      const [row, st] = await Promise.all([
        api.getInstitutionIntegration(id),
        api.getIntegrationStatus(id).catch(() => null),
      ]);
      setIntegration(row);
      setMpesaEnv(row?.mpesa_env || "sandbox");
      setMpesaShortcode(row?.mpesa_shortcode || "");
      setStatus(
        st
          ? `M-Pesa ${st.mpesa_configured ? "configured" : "not configured"} · mode ${st.kenya_mode || "—"}`
          : "",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load integrations");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadInstitutions().catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (institutionId) loadIntegration(institutionId);
  }, [institutionId]);

  async function onSave(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const saved = await api.putInstitutionIntegration(institutionId, {
        mpesa_env: mpesaEnv,
        mpesa_shortcode: mpesaShortcode,
      });
      setIntegration(saved);
      setMessage("Integration settings saved.");
      await loadIntegration(institutionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save integrations");
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageShell wide>
      <PageExplain content={PAGE_EXPLAINS["/integrations"]} />
      <HowItWorks content={HOW_IT_WORKS["/integrations"]} />
      {error ? <Alert tone="error">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}

      <section className="panel">
        <div className="panel-header">
          <div>
            <h2>Institution integrations</h2>
            <p className="muted">M-Pesa and partner credentials for Kenya float desks.</p>
          </div>
          <select value={institutionId} onChange={(e) => setInstitutionId(e.target.value)}>
            {institutions.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </div>
        {status ? <p className="meta">{status}</p> : null}
        {loading ? (
          <LoadingPanel rows={4} />
        ) : !institutionId ? (
          <EmptyState title="No institution" description="Create an institution before configuring integrations." />
        ) : (
          <form className="grid-2" onSubmit={onSave}>
            <label>
              M-Pesa environment
              <select value={mpesaEnv} onChange={(e) => setMpesaEnv(e.target.value)}>
                <option value="sandbox">sandbox</option>
                <option value="production">production</option>
              </select>
            </label>
            <label>
              Shortcode
              <input value={mpesaShortcode} onChange={(e) => setMpesaShortcode(e.target.value)} />
            </label>
            <p className="meta span-2">
              Secrets already set: consumer key {integration?.mpesa_consumer_key_set ? "yes" : "no"}, secret{" "}
              {integration?.mpesa_consumer_secret_set ? "yes" : "no"}, passkey{" "}
              {integration?.mpesa_stk_passkey_set ? "yes" : "no"}.
            </p>
            <button className="btn btn-primary" type="submit" disabled={busy}>
              {busy ? "Saving…" : "Save"}
            </button>
          </form>
        )}
      </section>
    </PageShell>
  );
}
