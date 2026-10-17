import { FormEvent, useEffect, useState } from "react";
import { api, type OpsUserRecord } from "../api/client";
import { HowItWorks, PageExplain } from "../components/PageExplain";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";
import { HOW_IT_WORKS, PAGE_EXPLAINS } from "../config/pageExplainers";
import "../components/ui.css";

export function UsersPage() {
  const [items, setItems] = useState<OpsUserRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [role, setRole] = useState("institution_ops");
  const [tempPassword, setTempPassword] = useState("");

  async function load() {
    setLoading(true);
    try {
      setItems(await api.listOpsUsers());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load users");
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
      const created = await api.createOpsUser({
        email,
        full_name: fullName,
        role,
      } as Parameters<typeof api.createOpsUser>[0]);
      setTempPassword((created as { temporary_password?: string }).temporary_password || "");
      setEmail("");
      setFullName("");
      setMessage("User created. Share the temporary password once.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create user");
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageShell wide>
      <PageExplain content={PAGE_EXPLAINS["/users"]} />
      <HowItWorks content={HOW_IT_WORKS["/users"]} />
      {error ? <Alert tone="error">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}
      {tempPassword ? <Alert tone="info">Temporary password: {tempPassword}</Alert> : null}

      <section className="panel">
        <h2>Create ops user</h2>
        <form className="grid-2" onSubmit={onCreate}>
          <label>
            Full name
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
          </label>
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          </label>
          <label>
            Role
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="platform_admin">platform_admin</option>
              <option value="institution_admin">institution_admin</option>
              <option value="institution_ops">institution_ops</option>
              <option value="read_only">read_only</option>
              <option value="agent_dealer">agent_dealer</option>
            </select>
          </label>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? "Creating…" : "Create user"}
          </button>
        </form>
      </section>

      <section className="panel">
        <h2>Portal users</h2>
        {loading ? (
          <LoadingPanel rows={4} />
        ) : items.length === 0 ? (
          <EmptyState title="No users" description="Create an ops login to share with bank or SACCO staff." />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Active</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.full_name}</td>
                    <td>{item.email}</td>
                    <td>{item.role}</td>
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
