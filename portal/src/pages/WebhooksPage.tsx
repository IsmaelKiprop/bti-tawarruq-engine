import { FormEvent, useEffect, useState } from "react";
import { api, type Institution, type Webhook } from "../api/client";
import { HowItWorks, PageExplain } from "../components/PageExplain";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";
import { HOW_IT_WORKS, PAGE_EXPLAINS } from "../config/pageExplainers";
import "../components/ui.css";

export function WebhooksPage() {
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [items, setItems] = useState<Webhook[]>([]);
  const [institutionId, setInstitutionId] = useState("");
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [secret, setSecret] = useState("");
  const [busy, setBusy] = useState(false);

  async function load(instId?: string) {
    setLoading(true);
    try {
      const [inst, hooks] = await Promise.all([
        api.listInstitutions(),
        api.listWebhooks(instId || undefined),
      ]);
      setInstitutions(inst);
      setItems(hooks);
      if (!institutionId && inst[0]) setInstitutionId(inst[0].id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load webhooks");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const created = await api.registerWebhook({
        institution_id: institutionId,
        url,
        events: ["application.*", "transaction.*"],
      });
      setSecret(created.secret);
      setUrl("");
      setMessage("Webhook registered.");
      await load(institutionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to register webhook");
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageShell wide>
      <PageExplain content={PAGE_EXPLAINS["/webhooks"]} />
      <HowItWorks content={HOW_IT_WORKS["/webhooks"]} />
      {error ? <Alert tone="error">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}
      {secret ? <Alert tone="info">Webhook secret (copy once): {secret}</Alert> : null}

      <section className="panel">
        <h2>Register webhook</h2>
        <form className="grid-2" onSubmit={onCreate}>
          <label>
            Institution
            <select value={institutionId} onChange={(e) => setInstitutionId(e.target.value)} required>
              {institutions.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Callback URL
            <input value={url} onChange={(e) => setUrl(e.target.value)} required />
          </label>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? "Saving…" : "Register"}
          </button>
        </form>
      </section>

      <section className="panel">
        <h2>Webhooks</h2>
        {loading ? (
          <LoadingPanel rows={3} />
        ) : items.length === 0 ? (
          <EmptyState title="No webhooks" description="Register a callback URL for system-to-system events." />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>URL</th>
                  <th>Events</th>
                  <th>Active</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.url}</td>
                    <td>{item.events.join(", ")}</td>
                    <td>{item.active ? "Yes" : "No"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </PageShell>
  );
}
