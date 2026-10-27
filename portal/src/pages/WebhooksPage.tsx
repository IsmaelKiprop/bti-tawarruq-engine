import { FormEvent, useEffect, useState } from "react";
import { api, type ApiKeyRecord, type Institution, type Webhook } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";
import { SecretCopyPanel } from "../components/SecretCopyPanel";

export function WebhooksPage() {
  const { user } = useAuth();
  const isSuperAdmin = user?.role === "platform_admin";
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [items, setItems] = useState<Webhook[]>([]);
  const [apiKeys, setApiKeys] = useState<ApiKeyRecord[]>([]);
  const [institutionId, setInstitutionId] = useState("");
  const [url, setUrl] = useState("");
  const [keyName, setKeyName] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [secret, setSecret] = useState("");
  const [issuedKey, setIssuedKey] = useState("");
  const [issuedHmac, setIssuedHmac] = useState("");
  const [busy, setBusy] = useState(false);
  const [keyBusy, setKeyBusy] = useState(false);

  async function load(instId?: string) {
    setLoading(true);
    try {
      const [inst, hooks] = await Promise.all([
        api.listInstitutions(),
        api.listWebhooks(instId || undefined),
      ]);
      setInstitutions(inst);
      setItems(hooks);
      const nextId = instId || institutionId || inst[0]?.id || "";
      if (!institutionId && inst[0]) setInstitutionId(inst[0].id);
      if (nextId && isSuperAdmin) {
        setApiKeys(await api.listApiKeys(nextId).catch(() => [] as ApiKeyRecord[]));
      } else {
        setApiKeys([]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load webhooks");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [isSuperAdmin]);

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

  async function onCreateKey(event: FormEvent) {
    event.preventDefault();
    setKeyBusy(true);
    setError("");
    setMessage("");
    setIssuedKey("");
    setIssuedHmac("");
    try {
      const created = await api.createApiKey(institutionId, keyName.trim() || "fi-core-banking", "api_client");
      setIssuedKey(created.api_key);
      setIssuedHmac(created.hmac_secret || "");
      setKeyName("");
      setMessage("API key created. Copy the key and HMAC secret now — they are not shown again.");
      await load(institutionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create API key");
    } finally {
      setKeyBusy(false);
    }
  }

  return (
    <PageShell wide>
      {error ? <Alert tone="error">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}
      {secret ? (
        <SecretCopyPanel
          title="Webhook secret"
          note="Copy now. It is not shown again."
          secrets={[{ id: "webhook", label: "Signing secret", value: secret }]}
        />
      ) : null}
      {issuedKey ? (
        <SecretCopyPanel
          title="API client issued"
          note="Copy these for the FI. They also appear on FI profile."
          secrets={[
            { id: "key", label: "API key", value: issuedKey },
            { id: "hmac", label: "HMAC secret", value: issuedHmac },
          ]}
        />
      ) : null}

      {isSuperAdmin ? (
        <section className="panel">
          <h2>Onboard API key</h2>
          <form className="grid-2" onSubmit={onCreateKey}>
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
              Key name
              <input
                value={keyName}
                onChange={(e) => setKeyName(e.target.value)}
                placeholder="fi-core-banking"
                required
              />
            </label>
            <button className="btn btn-primary" type="submit" disabled={keyBusy || !institutionId}>
              {keyBusy ? "Creating…" : "Create API key"}
            </button>
          </form>
          {apiKeys.length > 0 ? (
            <div className="table-wrap" style={{ marginTop: "1rem" }}>
              <table className="table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Prefix</th>
                    <th>Role</th>
                    <th>Active</th>
                  </tr>
                </thead>
                <tbody>
                  {apiKeys.map((item) => (
                    <tr key={item.id}>
                      <td>{item.name}</td>
                      <td>{item.key_prefix}</td>
                      <td>{item.role}</td>
                      <td>{item.active ? "Yes" : "No"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      ) : (
        <section className="panel">
          <h2>API keys</h2>
          <p className="muted" style={{ marginTop: 0 }}>
            FI Admin cannot create institution API keys. Request BTI Super Admin to onboard the machine
            key for your CBS, then register the callback URL below.
          </p>
        </section>
      )}

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
