import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api, type ApiClientRequest, type InstitutionOnboarding } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Alert, LoadingPanel, PageShell } from "../components/PageShell";
import { SecretCopyPanel } from "../components/SecretCopyPanel";
import { formFromOnboarding, lifecycleLabel, WIZARD_STEPS } from "../config/fiKyc";

function text(value: unknown): string {
  if (value == null || value === "") return "—";
  if (Array.isArray(value)) {
    const names = value
      .map((row) => (typeof row === "string" ? row : String((row as { name?: string }).name || "")))
      .map((part) => part.trim())
      .filter(Boolean);
    return names.join(", ") || "—";
  }
  return String(value);
}

export function InstitutionProfilePage() {
  const { user } = useAuth();
  const institutionId = user?.institution_id || "";
  const [record, setRecord] = useState<InstitutionOnboarding | null>(null);
  const [requestState, setRequestState] = useState<ApiClientRequest | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const form = useMemo(() => (record ? formFromOnboarding(record as unknown as Record<string, unknown>) : null), [record]);

  async function load() {
    if (!institutionId) {
      setLoading(false);
      setError("This login is not bound to an institution.");
      return;
    }
    setLoading(true);
    try {
      const [profile, request] = await Promise.all([
        api.getInstitutionOnboarding(institutionId),
        api.getApiClientRequest(institutionId),
      ]);
      setRecord(profile);
      setRequestState(request);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load institution profile");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [institutionId]);

  useEffect(() => {
    if (!institutionId || requestState?.status !== "requested") return;
    const timer = window.setInterval(async () => {
      try {
        const next = await api.getApiClientRequest(institutionId);
        setRequestState(next);
        if (next.status === "issued") {
          setMessage(next.message);
        }
      } catch {
        /* keep the last known request state */
      }
    }, 8000);
    return () => window.clearInterval(timer);
  }, [institutionId, requestState?.status]);

  async function onRequestKey() {
    if (!institutionId) return;
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const next = await api.requestApiClient(institutionId);
      setRequestState(next);
      setMessage(next.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send API client request");
    } finally {
      setBusy(false);
    }
  }

  const sections = useMemo(() => {
    if (!form) return [];
    return [
      {
        id: "identity",
        rows: [
          ["Legal name", form.legal_registered_name],
          ["Code", form.code],
          ["Type", form.institution_type === "OTHER" ? form.other_institution_type : form.institution_type],
          ["Support email", form.support_email],
          ["Telephone", form.main_telephone],
          ["Address", form.registered_address_line1],
          ["KRA PIN", form.kra_pin],
          ["Website", form.website_url],
        ],
      },
      {
        id: "regulatory",
        rows: [
          ["Regulator", form.primary_regulator === "OTHER" ? form.regulator_other_name : form.primary_regulator],
          ["Licence", form.licence_number],
          ["Issue date", form.licence_issue_date],
          ["Status", form.licence_status],
        ],
      },
      {
        id: "ownership",
        rows: [
          ["CEO", form.ceo_managing_director_name],
          ["Shareholders", text(form.owners_and_shareholders)],
          ["UBOs", text(form.ubo_details)],
          ["Board", text(form.directors_board_members)],
        ],
      },
      {
        id: "representatives",
        rows: [
          ["Primary contact", form.primary_contact_full_name],
          ["Work email", form.primary_contact_work_email],
          ["Signatories", text(form.authorized_signatories)],
        ],
      },
      {
        id: "settlement",
        rows: [
          ["Bank", form.settlement_bank_name],
          ["Account name", form.settlement_account_name],
          ["Account number", form.settlement_account_number],
          ["Currency", form.settlement_currency],
        ],
      },
      {
        id: "commercial",
        rows: [
          ["Go-live", form.target_go_live_date],
          ["Monthly count", form.expected_monthly_transaction_count],
          ["Agreement", form.commercial_agreement_status],
        ],
      },
    ];
  }, [form]);

  if (user?.role !== "institution_admin") {
    return (
      <PageShell>
        <Alert tone="error">FI profile is for FI Admin. Super Admin and BTI Ops use Institutions.</Alert>
        <Link className="btn btn-secondary" to="/institutions">
          Institutions
        </Link>
      </PageShell>
    );
  }

  return (
    <PageShell wide>
      <header className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="m-0 text-lg font-semibold">{record?.name || "Institution profile"}</h2>
          <p className="muted m-0 mt-1 text-sm">
            {lifecycleLabel(record?.lifecycle_status, record?.active)} KYC for your tenant. Read only.
          </p>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          disabled={busy || !record || requestState?.status === "issued" || requestState?.status === "requested"}
          onClick={() => void onRequestKey()}
        >
          {busy ? "Sending…" : requestState?.status === "issued" ? "API client issued" : requestState?.status === "requested" ? "Request sent" : "Request API Client"}
        </button>
      </header>

      {error ? <Alert tone="error">{error}</Alert> : null}
      {message && requestState?.status !== "issued" && requestState?.status !== "requested" ? (
        <Alert tone="success">{message}</Alert>
      ) : null}

      {requestState?.status === "requested" ? (
        <section className="rounded-sm border border-border bg-surface p-3">
          <p className="m-0 text-[0.7rem] uppercase tracking-wide text-muted">API client</p>
          <strong className="mt-1 block text-sm">Pending Super Admin</strong>
          <p className="muted m-0 mt-1 text-sm">{requestState.message}</p>
          {requestState.requested_at ? (
            <p className="muted m-0 mt-1 text-xs">Requested {new Date(requestState.requested_at).toLocaleString()}</p>
          ) : null}
        </section>
      ) : null}

      {requestState?.status === "issued" ? (
        <SecretCopyPanel
          title="API client issued"
          note={requestState.message}
          institutionId={institutionId}
          secrets={[
            { id: "key", label: "API key", value: requestState.api_key || "", prefix: requestState.key_prefix || undefined },
            { id: "hmac", label: "HMAC secret", value: requestState.hmac_secret || "" },
          ]}
          onReveal={async (password) => {
            const revealed = await api.revealApiClient(institutionId, password);
            return [
              { id: "key", label: "API key", value: revealed.api_key || "", prefix: revealed.key_prefix || undefined },
              { id: "hmac", label: "HMAC secret", value: revealed.hmac_secret || "" },
            ];
          }}
        />
      ) : null}

      {loading ? <LoadingPanel rows={6} /> : null}

      {!loading && form ? (
        <div className="grid gap-3">
          {sections.map((section) => {
            const title = WIZARD_STEPS.find((step) => step.id === section.id)?.title || section.id;
            return (
              <section key={section.id} className="rounded-sm border border-border bg-surface p-3">
                <h3 className="m-0 mb-3 text-sm font-semibold">{title}</h3>
                <dl className="m-0 grid gap-2 sm:grid-cols-2">
                  {section.rows.map(([label, value]) => (
                    <div key={label} className="rounded-sm border border-border bg-surface-elevated px-3 py-2">
                      <dt className="text-[0.7rem] uppercase tracking-wide text-muted">{label}</dt>
                      <dd className="m-0 text-sm">{text(value)}</dd>
                    </div>
                  ))}
                </dl>
              </section>
            );
          })}
        </div>
      ) : null}
    </PageShell>
  );
}
