import { FormEvent, useCallback, useEffect, useState } from "react";
import { api, AgentDealer } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { PoolTape } from "../components/DealTape";
import { HowItWorks, PageExplain } from "../components/PageExplain";
import { Alert, EmptyState, LoadingPanel, PageShell } from "../components/PageShell";
import { HOW_IT_WORKS, PAGE_EXPLAINS } from "../config/pageExplainers";
import { isDealerRole } from "../config/roles";
import "../components/ui.css";

type View = "list" | "detail" | "create";

function floatIndicator(balance: number) {
  if (balance >= 100000) {
    return { color: "var(--color-success)", label: "Healthy", bg: "color-mix(in srgb, var(--color-success) 14%, var(--color-surface))" };
  }
  if (balance >= 20000) {
    return { color: "var(--color-warning)", label: "Low", bg: "color-mix(in srgb, var(--color-warning) 14%, var(--color-surface))" };
  }
  return { color: "var(--color-destructive)", label: "Critical", bg: "color-mix(in srgb, var(--color-destructive) 14%, var(--color-surface))" };
}

export function AgentDealerPage() {
  const { user } = useAuth();
  const dealerDesk = isDealerRole(user?.role);
  const [dealers, setDealers] = useState<AgentDealer[]>([]);
  const [selected, setSelected] = useState<AgentDealer | null>(null);
  const [view, setView] = useState<View>("list");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const [businessName, setBusinessName] = useState("");
  const [mpesaNumber, setMpesaNumber] = useState("");
  const [mpesaTill, setMpesaTill] = useState("");
  const [code, setCode] = useState("");
  const [contactName, setContactName] = useState("");
  const [contactPhone, setContactPhone] = useState("");

  const [topupAmount, setTopupAmount] = useState("");
  const [topupRef, setTopupRef] = useState("");
  const [topupNote, setTopupNote] = useState("");

  const loadDealers = useCallback(async () => {
    setLoading(true);
    try {
      const data = dealerDesk ? [await api.getMyAgentDealer()] : await api.listAgentDealers();
      setDealers(data);
      if (data.length === 0) {
        setSelected(null);
        return;
      }
      if (dealerDesk) {
        setSelected(data[0]);
        setView("detail");
        return;
      }
      setView((current) => (current === "create" ? current : "detail"));
      setSelected((current) => {
        if (current && data.some((row) => row.id === current.id)) return current;
        return data[0];
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dealers");
    } finally {
      setLoading(false);
    }
  }, [dealerDesk]);

  const loadDealer = useCallback(async (id: string) => {
    try {
      const data = dealerDesk ? await api.getMyAgentDealer() : await api.getAgentDealer(id);
      setSelected(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dealer detail");
    }
  }, [dealerDesk]);

  useEffect(() => {
    void loadDealers();
  }, [loadDealers]);

  useEffect(() => {
    if (dealerDesk || !selected?.id || view === "create") return;
    if (selected.float_history) return;
    void loadDealer(selected.id);
  }, [dealerDesk, selected?.id, selected?.float_history, view, loadDealer]);

  useEffect(() => {
    if (!selected || !dealerDesk) return;
    setBusinessName(selected.business_name || "");
    setMpesaNumber(selected.mpesa_number || "");
    setMpesaTill(selected.mpesa_till_number || "");
    setContactName(selected.contact_name || "");
    setContactPhone(selected.contact_phone || "");
  }, [selected?.id, dealerDesk]);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api.createAgentDealer({
        business_name: businessName,
        mpesa_number: mpesaNumber,
        mpesa_till_number: mpesaTill || undefined,
        code: code || undefined,
        contact_name: contactName || undefined,
        contact_phone: contactPhone || undefined,
      });
      setMessage("Dealer registered at zero float. Issue an Agent dealer login so they can add float.");
      setView("list");
      await loadDealers();
      setBusinessName("");
      setMpesaNumber("");
      setMpesaTill("");
      setCode("");
      setContactName("");
      setContactPhone("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleTopup(e: FormEvent) {
    e.preventDefault();
    if (!selected || !dealerDesk) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const res = await api.topupAgentDealer(selected.id, parseFloat(topupAmount), topupRef, topupNote);
      setMessage(res.message);
      await loadDealer(selected.id);
      await loadDealers();
      setTopupAmount("");
      setTopupRef("");
      setTopupNote("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Top-up failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleProfile(e: FormEvent) {
    e.preventDefault();
    if (!selected || !dealerDesk) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api.updateAgentDealer(selected.id, {
        business_name: businessName,
        mpesa_number: mpesaNumber,
        mpesa_till_number: mpesaTill || null,
        contact_name: contactName || null,
        contact_phone: contactPhone || null,
      });
      setMessage("Your dealer details were saved.");
      await loadDealer(selected.id);
      await loadDealers();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save dealer details.");
    } finally {
      setBusy(false);
    }
  }

  async function handleToggle(dealer: AgentDealer) {
    setBusy(true);
    try {
      await api.updateAgentDealer(dealer.id, { active: !dealer.active });
      await loadDealers();
      if (selected?.id === dealer.id) await loadDealer(dealer.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  const liveBalance = dealerDesk
    ? selected?.float_balance || 0
    : dealers.reduce((sum, dealer) => sum + (dealer.float_balance || 0), 0);

  return (
    <PageShell wide>
      <div className="page-grid">
        <div className="span-2">
          <PageExplain content={PAGE_EXPLAINS["/agent-dealers"]} />
        </div>
        <HowItWorks content={HOW_IT_WORKS["/agent-dealers"]} />
        <section className="panel">
          <h2>{dealerDesk ? "Your pool" : "Live pool"}</h2>
          <PoolTape
            balance={liveBalance}
            topup={dealerDesk ? Number(topupAmount) || 0 : 0}
            previewTopup={dealerDesk}
          />
        </section>
        <section className="panel">
          <div className="panel-header">
            <div>
              <h2>{dealerDesk ? "Your dealer desk" : "M-Pesa Agent Dealers"}</h2>
              <p className="muted">
                  {dealerDesk
                  ? "Keep your business details current and add float here. Kenya step 2 draws from this pool. You do not see the customer journey."
                  : "Float pool providers for Kenya step 2. Only the dealer login can add float."}
              </p>
            </div>
            {!dealerDesk ? (
              <button className="btn btn-primary btn-sm" onClick={() => { setView("create"); setSelected(null); }}>
                + Register Dealer
              </button>
            ) : null}
          </div>

          {error && <Alert tone="error">{error}</Alert>}
          {message && <Alert tone="success">{message}</Alert>}

          {loading ? (
            <LoadingPanel rows={4} />
          ) : dealers.length === 0 ? (
            <EmptyState
              title={dealerDesk ? "No dealer bound to this login" : "No dealers registered"}
              description={
                dealerDesk
                  ? "Ask your institution admin to bind this login to a registered dealer."
                  : "Register an M-Pesa Agent Dealer, then create their Agent dealer login on Users so they can add float."
              }
            />
          ) : (
            <ul className="case-list">
              {dealers.map((d) => {
                const fi = floatIndicator(d.float_balance);
                return (
                  <li key={d.id}>
                    <button
                      type="button"
                      className={`case-row${selected?.id === d.id ? " active" : ""}`}
                      onClick={async () => { setView("detail"); await loadDealer(d.id); }}
                    >
                      <div className="case-row-top">
                        <strong>{d.business_name}</strong>
                        <span className={`badge ${d.active ? "success" : "warning"}`}>
                          {d.active ? "Active" : "Inactive"}
                        </span>
                      </div>
                      <span className="meta">{d.mpesa_number} · Code: {d.code}</span>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginTop: "0.35rem" }}>
                        <span className="meta">Float:</span>
                        <span
                          style={{
                            fontSize: "0.75rem",
                            fontWeight: 700,
                            color: fi.color,
                            background: fi.bg,
                            padding: "0.1rem 0.5rem",
                            borderRadius: "var(--radius)",
                          }}
                        >
                          KES {d.float_balance.toLocaleString("en-KE", { minimumFractionDigits: 2 })} · {fi.label}
                        </span>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <div>
          {view === "create" && !dealerDesk && (
            <section className="panel">
              <div className="panel-header">
                <div>
                  <h2>Register Agent Dealer</h2>
                  <p className="muted">Pool starts at zero. The dealer adds float after they sign in.</p>
                </div>
                <button className="btn btn-secondary btn-sm" onClick={() => setView("list")}>Cancel</button>
              </div>
              <form className="form-grid" onSubmit={handleCreate}>
                <label className="span-2">
                  Business Name
                  <input value={businessName} onChange={(e) => setBusinessName(e.target.value)} placeholder="Mwangi Dealers Ltd" required />
                </label>
                <label>
                  M-Pesa Number
                  <input value={mpesaNumber} onChange={(e) => setMpesaNumber(e.target.value)} placeholder="254712345678" required />
                </label>
                <label>
                  Till / Paybill Number (optional)
                  <input value={mpesaTill} onChange={(e) => setMpesaTill(e.target.value)} placeholder="12345" />
                </label>
                <label>
                  Dealer Code (auto-generated if blank)
                  <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="DEALER-001" />
                </label>
                <label>
                  Contact Name
                  <input value={contactName} onChange={(e) => setContactName(e.target.value)} placeholder="John Mwangi" />
                </label>
                <label>
                  Contact Phone
                  <input value={contactPhone} onChange={(e) => setContactPhone(e.target.value)} placeholder="254712345678" />
                </label>
                <p className="span-2 muted">
                  Institution and platform ops cannot seed or top up this pool. After register, open Users and issue an Agent dealer login bound to this dealer.
                </p>
                <div className="span-2">
                  <button type="submit" className="btn btn-primary" disabled={busy}>
                    {busy ? "Registering…" : "Register Dealer"}
                  </button>
                </div>
              </form>
            </section>
          )}

          {view === "detail" && selected && (
            <>
              <section className="panel">
                <div className="panel-header">
                  <div>
                    <h2>{selected.business_name}</h2>
                    <p className="muted">{selected.mpesa_number} · {selected.code}</p>
                  </div>
                  <div className="actions-row">
                    <span className={`badge ${selected.active ? "success" : "warning"}`}>
                      {selected.active ? "Active" : "Inactive"}
                    </span>
                    {!dealerDesk ? (
                      <button
                        className="btn btn-secondary btn-sm"
                        onClick={() => handleToggle(selected)}
                        disabled={busy}
                      >
                        {selected.active ? "Deactivate" : "Activate"}
                      </button>
                    ) : null}
                  </div>
                </div>

                {(() => {
                  const fi = floatIndicator(selected.float_balance);
                  return (
                    <div style={{ padding: "1rem", background: fi.bg, borderRadius: "var(--radius)", marginBottom: "1rem", border: `1px solid color-mix(in srgb, ${fi.color} 20%, transparent)` }}>
                      <div className="meta" style={{ marginBottom: "0.25rem" }}>Current Float Balance</div>
                      <div style={{ fontSize: "1.75rem", fontWeight: 800, color: fi.color }}>
                        KES {selected.float_balance.toLocaleString("en-KE", { minimumFractionDigits: 2 })}
                      </div>
                      <div style={{ fontSize: "0.72rem", color: fi.color, fontWeight: 600 }}>{fi.label}</div>
                    </div>
                  );
                })()}
                <PoolTape balance={selected.float_balance} topup={dealerDesk ? Number(topupAmount) || 0 : 0} />

                <ul className="status-list compact">
                  {selected.contact_name && (
                    <li className="status-row"><span>Contact</span><span>{selected.contact_name}</span></li>
                  )}
                  {selected.contact_phone && (
                    <li className="status-row"><span>Phone</span><span>{selected.contact_phone}</span></li>
                  )}
                  {selected.mpesa_till_number && (
                    <li className="status-row"><span>Till / Paybill</span><span>{selected.mpesa_till_number}</span></li>
                  )}
                  <li className="status-row">
                    <span>Registered</span>
                    <span className="meta">{selected.created_at ? new Date(selected.created_at).toLocaleDateString("en-KE") : "-"}</span>
                  </li>
                </ul>
              </section>

              {dealerDesk ? (
                <section className="panel">
                  <h2>Your details</h2>
                  <p className="muted" style={{ marginBottom: "1rem" }}>
                    Update the same fields used at register. Dealer code stays as issued.
                  </p>
                  <form className="form-grid" onSubmit={handleProfile}>
                    <label className="span-2">
                      Business Name
                      <input
                        value={businessName}
                        onChange={(e) => setBusinessName(e.target.value)}
                        placeholder="Mwangi Dealers Ltd"
                        required
                      />
                    </label>
                    <label>
                      M-Pesa Number
                      <input
                        value={mpesaNumber}
                        onChange={(e) => setMpesaNumber(e.target.value)}
                        placeholder="254712345678"
                        required
                      />
                    </label>
                    <label>
                      Till / Paybill Number (optional)
                      <input
                        value={mpesaTill}
                        onChange={(e) => setMpesaTill(e.target.value)}
                        placeholder="12345"
                      />
                    </label>
                    <label>
                      Dealer Code
                      <input value={selected.code} disabled />
                    </label>
                    <label>
                      Contact Name
                      <input
                        value={contactName}
                        onChange={(e) => setContactName(e.target.value)}
                        placeholder="John Mwangi"
                      />
                    </label>
                    <label>
                      Contact Phone
                      <input
                        value={contactPhone}
                        onChange={(e) => setContactPhone(e.target.value)}
                        placeholder="254712345678"
                      />
                    </label>
                    <div className="span-2">
                      <button type="submit" className="btn btn-primary" disabled={busy}>
                        {busy ? "Saving…" : "Save details"}
                      </button>
                    </div>
                  </form>
                </section>
              ) : null}

              {dealerDesk ? (
                <section className="panel">
                  <h2>Add float</h2>
                  <p className="muted" style={{ marginBottom: "1rem" }}>
                    Only you can add float. Institution and platform ops cannot do this.
                  </p>
                  <form className="form-grid" onSubmit={handleTopup}>
                    <label>
                      Amount (KES)
                      <input
                        type="number"
                        min={1}
                        value={topupAmount}
                        onChange={(e) => setTopupAmount(e.target.value)}
                        placeholder="50000"
                        required
                      />
                    </label>
                    <label>
                      M-Pesa Reference
                      <input value={topupRef} onChange={(e) => setTopupRef(e.target.value)} placeholder="QHA73EXAMPLE" />
                    </label>
                    <label className="span-2">
                      Note
                      <input value={topupNote} onChange={(e) => setTopupNote(e.target.value)} placeholder="Top-up from business account" />
                    </label>
                    <div className="span-2">
                      <button type="submit" className="btn btn-primary" disabled={busy || !topupAmount}>
                        {busy ? "Processing…" : "Add float"}
                      </button>
                    </div>
                  </form>
                </section>
              ) : (
                <section className="panel">
                  <h2>Float is the dealer&apos;s job</h2>
                  <p className="muted">
                    Bank and platform ops can register and activate this dealer. They cannot add float.
                    Issue an Agent dealer login on Users, bound to this dealer. Kenya step 2 draws from the pool after they top up.
                  </p>
                </section>
              )}

              {selected.float_history && selected.float_history.length > 0 && (
                <section className="panel">
                  <h2>{dealerDesk ? "Top-ups and draws" : "Float History"}</h2>
                  <div className="table-wrap">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Date</th>
                          <th>Kind</th>
                          <th>Amount</th>
                          <th>Reference</th>
                          {!dealerDesk ? <th>By</th> : null}
                        </tr>
                      </thead>
                      <tbody>
                        {selected.float_history.map((t) => {
                          const kind = t.kind || (t.amount < 0 ? "draw" : "topup");
                          return (
                            <tr key={t.id}>
                              <td className="meta">{t.created_at ? new Date(t.created_at).toLocaleString("en-KE", { dateStyle: "short", timeStyle: "short" }) : "-"}</td>
                              <td>{kind === "draw" ? "Draw" : "Top-up"}</td>
                              <td>
                                <span style={{ color: t.amount < 0 ? "var(--color-destructive)" : "var(--color-success)", fontWeight: 600 }}>
                                  {t.amount < 0 ? "-" : "+"}KES {Math.abs(t.amount).toLocaleString("en-KE", { minimumFractionDigits: 2 })}
                                </span>
                              </td>
                              <td className="meta mono">{t.reference || "-"}</td>
                              {!dealerDesk ? <td className="meta">{t.added_by || "-"}</td> : null}
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </section>
              )}
            </>
          )}

          {view === "list" && !selected && !dealerDesk && (
            <section className="panel">
              <EmptyState
                title="Select a dealer"
                description="Choose a dealer to see pool balance and draws. Register one, then issue their login so they can add float."
              />
            </section>
          )}
        </div>
      </div>
    </PageShell>
  );
}
