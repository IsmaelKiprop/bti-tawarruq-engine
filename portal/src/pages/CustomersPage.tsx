import { FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type KenyaCustomer } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";

export function CustomersPage() {
  const { customerId } = useParams();
  const { user } = useAuth();
  const [items, setItems] = useState<KenyaCustomer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [walletNumber, setWalletNumber] = useState("");

  async function load() {
    setLoading(true);
    try {
      setItems(await api.listKenyaCustomers(user?.institution_id || undefined));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load customers");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, [user?.institution_id]);

  async function onCreate(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api.registerKenyaCustomer({
        full_name: fullName,
        phone,
        wallet_number: walletNumber || phone,
        email: email || undefined,
        institution_id: user?.institution_id || undefined,
      });
      setFullName("");
      setPhone("");
      setEmail("");
      setWalletNumber("");
      setMessage("Customer registered.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to register customer");
    } finally {
      setBusy(false);
    }
  }

  const selected = customerId ? items.find((row) => row.id === customerId) : null;

  return (
    <PageShell wide>
      {error ? <Alert tone="error">{error}</Alert> : null}
      {message ? <Alert tone="success">{message}</Alert> : null}

      <section className="panel">
        <h2>Register customer</h2>
        <form className="grid-2" onSubmit={onCreate}>
          <label>
            Full name
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} required />
          </label>
          <label>
            Phone
            <input value={phone} onChange={(e) => setPhone(e.target.value)} required />
          </label>
          <label>
            Wallet number
            <input value={walletNumber} onChange={(e) => setWalletNumber(e.target.value)} placeholder="Defaults to phone" />
          </label>
          <label>
            Email
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? "Saving…" : "Save customer"}
          </button>
        </form>
      </section>

      <section className="panel">
        <h2>Customers</h2>
        {loading ? (
          <LoadingPanel rows={5} />
        ) : items.length === 0 ? (
          <EmptyState title="No customers" description="Register the financing beneficiary before opening a case." />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Phone</th>
                  <th>Wallet</th>
                  <th>Score</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td>{item.full_name}</td>
                    <td>{item.phone}</td>
                    <td>{item.wallet_number}</td>
                    <td>{item.credit_score}</td>
                    <td>
                      <Link className="btn btn-secondary btn-sm" to={`/customers/${item.id}`}>
                        Open
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {selected ? (
          <p className="meta" style={{ marginTop: "0.75rem" }}>
            Selected {selected.full_name} · wallet {selected.wallet_number}
          </p>
        ) : null}
      </section>
    </PageShell>
  );
}
