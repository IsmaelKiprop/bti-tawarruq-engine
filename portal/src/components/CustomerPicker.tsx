import { forwardRef, useEffect, useImperativeHandle, useState } from "react";
import { Link } from "react-router-dom";
import { api, Institution, KenyaCustomer } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Alert } from "./PageShell";

export type CustomerPickerHandle = {
  ensureCustomer: () => Promise<KenyaCustomer>;
};

type Props = {
  className?: string;
};

export const CustomerPicker = forwardRef<CustomerPickerHandle, Props>(function CustomerPicker(
  { className },
  ref,
) {
  const { user } = useAuth();
  const isPlatformAdmin = !user || user.role === "platform_admin";
  const [customers, setCustomers] = useState<KenyaCustomer[]>([]);
  const [institutions, setInstitutions] = useState<Institution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [mode, setMode] = useState<"existing" | "register">("existing");
  const [customerId, setCustomerId] = useState("");
  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [email, setEmail] = useState("");
  const [nationalId, setNationalId] = useState("");
  const [institutionId, setInstitutionId] = useState(user?.institution_id || "");

  useEffect(() => {
    let active = true;
    Promise.all([api.listKenyaCustomers(), api.listInstitutions().catch(() => [] as Institution[])])
      .then(([rows, books]) => {
        if (!active) return;
        setCustomers(rows);
        setInstitutions(books);
        setMode(rows.length > 0 ? "existing" : "register");
        if (!institutionId && (user?.institution_id || books[0]?.id)) {
          setInstitutionId(user?.institution_id || books[0]?.id || "");
        }
      })
      .catch((err) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "We could not load customers.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const selected = customers.find((item) => item.id === customerId) || null;

  useImperativeHandle(ref, () => ({
    async ensureCustomer() {
      if (mode === "register") {
        const name = fullName.trim();
        const mobile = phone.trim();
        const mail = email.trim();
        if (!name || !mobile || !mail) {
          throw new Error("Enter the customer name, email, and phone.");
        }
        const bookId = isPlatformAdmin ? institutionId : user?.institution_id;
        if (isPlatformAdmin && !bookId) {
          throw new Error("Select the institution this customer belongs to.");
        }
        const created = await api.registerKenyaCustomer({
          full_name: name,
          phone: mobile,
          email: mail,
          wallet_number: mobile,
          national_id: nationalId.trim() || undefined,
          institution_id: bookId || undefined,
        });
        setCustomers((prev) => [created, ...prev.filter((item) => item.id !== created.id)]);
        setCustomerId(created.id);
        setMode("existing");
        return created;
      }
      if (!selected) {
        throw new Error("Select the onboarded customer for this deal.");
      }
      return selected;
    },
  }));

  return (
    <div className={className ? `customer-picker ${className}` : "customer-picker"}>
      <div className="customer-picker-toolbar">
        <button
          type="button"
          className={mode === "existing" ? "chip active" : "chip"}
          onClick={() => setMode("existing")}
        >
          Onboarded customer
        </button>
        <button
          type="button"
          className={mode === "register" ? "chip active" : "chip"}
          onClick={() => setMode("register")}
        >
          Register new
        </button>
      </div>

      {error && <Alert tone="error">{error}</Alert>}

      {mode === "existing" ? (
        <>
          <label>
            Customer
            <select
              className="select-input"
              value={customerId}
              onChange={(event) => setCustomerId(event.target.value)}
              disabled={loading}
              required={mode === "existing"}
            >
              <option value="">{loading ? "Loading customers…" : "Select a customer"}</option>
              {customers.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.full_name} · {item.phone}
                  {item.institution_name ? ` · ${item.institution_name}` : ""}
                </option>
              ))}
            </select>
          </label>
          {selected ? (
            <p className="meta">
              {selected.institution_name ? `${selected.institution_name}. ` : ""}
              {selected.email
                ? `Accept mail goes to ${selected.email}. `
                : "No email on this record. Add one on Customers so the accept link can be mailed. "}
              Same record as on Customers.{" "}
              <Link to={`/customers/${selected.id}`}>Open {selected.full_name}</Link>
            </p>
          ) : (
            <p className="meta">
              Use the customer already on the books. If they are new, register them here first.
            </p>
          )}
        </>
      ) : (
        <>
          <div className="form-grid">
            {isPlatformAdmin ? (
              <label className="span-2">
                Institution
                <select
                  className="select-input"
                  value={institutionId}
                  onChange={(event) => setInstitutionId(event.target.value)}
                  required={mode === "register"}
                >
                  <option value="">Select institution</option>
                  {institutions.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name} ({item.code})
                    </option>
                  ))}
                </select>
              </label>
            ) : null}
            <label>
              Full name
              <input
                value={fullName}
                onChange={(event) => setFullName(event.target.value)}
                required={mode === "register"}
                placeholder="Marian Abubakar"
              />
            </label>
            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required={mode === "register"}
                placeholder="jane@example.com"
              />
            </label>
            <label>
              Phone
              <input
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                required={mode === "register"}
                placeholder="60123456789"
              />
            </label>
            <label className="span-2">
              National ID (optional)
              <input
                value={nationalId}
                onChange={(event) => setNationalId(event.target.value)}
                placeholder="12345678"
              />
            </label>
          </div>
          <p className="meta">
            This writes to the same customer book as <Link to="/customers">Customers</Link>. Email is
            for the accept link. Wallet details can be completed later if this deal pays out in Kenya.
          </p>
        </>
      )}
    </div>
  );
});
