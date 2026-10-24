import { FormEvent, useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, Application, CustomerJourney, JourneyCertificate } from "../api/client";
import type { Certificate } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { BrandLogo } from "../components/BrandLogo";
import { BsasCertificateModal } from "../components/BsasCertificateModal";
import { BtiKenyaCertificate } from "../components/BtiKenyaCertificate";
import { TradeDocumentModal, type TradeDocKind } from "../components/TradeDocumentModal";
import { DealTape } from "../components/DealTape";
import { Alert, EmptyState, LoadingPanel, PageShell, statusBadgeClass } from "../components/PageShell";
import { formatMoney, formatWorkflowLabel } from "../lib/display";

interface MatchedApp {
  application_id: string;
  customer_ref: string;
  amount: string;
  currency?: string;
  status: string;
  institution: string | null;
  created_at: string | null;
}

const SAMPLE_REF = "CUST-DEFAULT-2026-0003";
const pillClass =
  "inline-flex items-center gap-1.5 rounded-sm border border-border bg-surface-elevated px-2 py-0.5 text-[0.7rem] uppercase tracking-wide text-muted";
const panelClass = "rounded-sm border border-border bg-surface p-3 flex flex-col gap-2.5 min-w-0";

export function CustomerJourneyPage() {
  const { authEnabled, user } = useAuth();
  const embedded = !authEnabled || Boolean(user);
  const navigate = useNavigate();
  const { ref } = useParams<{ ref: string }>();
  const [searchParams] = useSearchParams();
  const [journey, setJourney] = useState<CustomerJourney | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lookupRef, setLookupRef] = useState(ref || "");
  const [phone, setPhone] = useState(searchParams.get("phone") || "");
  const [matchedApps, setMatchedApps] = useState<MatchedApp[]>([]);
  const [bsasCert, setBsasCert] = useState<{ cert: Certificate; legLabel: string } | null>(null);
  const [showBtiCert, setShowBtiCert] = useState(false);
  const [tradeDoc, setTradeDoc] = useState<TradeDocKind | null>(null);
  const [pollingActive, setPollingActive] = useState(false);
  const [openStep, setOpenStep] = useState<number | null>(null);
  const [actionBusy, setActionBusy] = useState(false);

  const load = useCallback(async (appRef: string, ph?: string) => {
    if (!appRef) return;
    setLoading(true);
    setError("");
    setMatchedApps([]);
    try {
      const data = await api.getCustomerJourney(appRef, ph || undefined);
      setJourney(data);
      const inProgress =
        data.steps.some((s) => s.status === "active") ||
        Boolean(data.customer_action) ||
        ["in_progress", "eligibility_pending", "offer_pending"].includes(data.status);
      setPollingActive(inProgress);
      const current = data.steps.find((s) => s.status === "active");
      setOpenStep(current?.number ?? data.steps.find((s) => s.status === "done")?.number ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "We could not load this journey.");
      setJourney(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (ref) void load(ref, phone || undefined);
  }, [ref, load, phone]);

  useEffect(() => {
    if (!pollingActive || !ref) return;
    const timer = setInterval(() => void load(ref, phone || undefined), 12000);
    return () => clearInterval(timer);
  }, [pollingActive, ref, phone, load]);

  async function handleLookup(event: FormEvent) {
    event.preventDefault();
    setError("");
    setMatchedApps([]);

    const cleanRef = lookupRef.trim();
    const cleanPhone = phone.trim();

    if (cleanRef) {
      navigate(`/customer/${encodeURIComponent(cleanRef)}${cleanPhone ? `?phone=${encodeURIComponent(cleanPhone)}` : ""}`);
      await load(cleanRef, cleanPhone || undefined);
      return;
    }

    if (cleanPhone) {
      setLoading(true);
      try {
        const apps = await api.lookupCustomerByPhone(cleanPhone);
        if (apps.length === 1) {
          navigate(`/customer/${encodeURIComponent(apps[0].customer_ref)}?phone=${encodeURIComponent(cleanPhone)}`);
          await load(apps[0].customer_ref, cleanPhone);
        } else if (apps.length > 1) {
          setMatchedApps(apps);
        } else {
          setError("No applications found for this phone number.");
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : "No applications found for this phone number.");
      } finally {
        setLoading(false);
      }
      return;
    }

    setError("Enter an application reference or phone number.");
  }

  function handleSelectSample(sampleRef: string) {
    setLookupRef(sampleRef);
    navigate(`/customer/${encodeURIComponent(sampleRef)}`);
    void load(sampleRef);
  }

  async function handleCustomerAction() {
    if (!journey) return;
    setActionBusy(true);
    setError("");
    try {
      const next =
        journey.customer_action === "sign"
          ? await api.customerSignContract(journey.customer_ref, phone || undefined)
          : await api.customerAcceptOffer(journey.customer_ref, phone || undefined);
      setJourney(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "We could not record that action.");
    } finally {
      setActionBusy(false);
    }
  }

  function openBsasCert(cert: JourneyCertificate, legLabel: string) {
    setBsasCert({
      cert: {
        certificate_number: cert.certificate_number,
        issuer: cert.issuer,
        seller: cert.seller ?? undefined,
        buyer: cert.buyer ?? undefined,
        selling_time: cert.selling_time ?? undefined,
        selling_date: cert.selling_date ?? undefined,
        value_date: cert.value_date ?? undefined,
        product_code: cert.product_code ?? undefined,
        volume: cert.volume ?? undefined,
        currency: cert.currency ?? undefined,
        price: cert.price ?? undefined,
        value_amount: cert.value_amount ?? undefined,
        pdf_filename: cert.pdf_filename ?? undefined,
      } as Certificate,
      legLabel,
    });
  }

  const progress = journey ? Math.round((journey.overall_progress / journey.total_steps) * 100) : 0;
  const allDone = Boolean(journey?.steps.length && journey.steps.every((step) => step.status === "done"));

  const content = !ref && !journey ? (
    <LookupView
      embedded={embedded}
      lookupRef={lookupRef}
      phone={phone}
      loading={loading}
      error={error}
      matchedApps={matchedApps}
      setLookupRef={setLookupRef}
      setPhone={setPhone}
      onLookup={handleLookup}
      onSelect={handleSelectSample}
    />
  ) : (
    <JourneyView
      embedded={embedded}
      journey={journey}
      loading={loading}
      error={error}
      progress={progress}
      allDone={allDone}
      pollingActive={pollingActive}
      openStep={openStep}
      setOpenStep={setOpenStep}
      onBack={() => {
        setJourney(null);
        navigate("/customer");
      }}
      onOpenBti={() => setShowBtiCert(true)}
      onOpenBsas={openBsasCert}
      onOpenTradeDoc={setTradeDoc}
      actionBusy={actionBusy}
      onCustomerAction={() => void handleCustomerAction()}
    />
  );

  return (
    <>
      {bsasCert && (
        <BsasCertificateModal
          certificate={bsasCert.cert}
          legLabel={bsasCert.legLabel}
          onClose={() => setBsasCert(null)}
        />
      )}
      {showBtiCert && journey && (
        <BtiKenyaCertificate journey={journey} onClose={() => setShowBtiCert(false)} />
      )}
      {tradeDoc && journey?.trade_documents && (
        <TradeDocumentModal journey={journey} kind={tradeDoc} onClose={() => setTradeDoc(null)} />
      )}
      {embedded ? (
        <PageShell wide>{content}</PageShell>
      ) : (
        <div className="customer-public">{content}</div>
      )}
    </>
  );
}

function LookupView({
  embedded,
  lookupRef,
  phone,
  loading,
  error,
  matchedApps,
  setLookupRef,
  setPhone,
  onLookup,
  onSelect,
}: {
  embedded: boolean;
  lookupRef: string;
  phone: string;
  loading: boolean;
  error: string;
  matchedApps: MatchedApp[];
  setLookupRef: (value: string) => void;
  setPhone: (value: string) => void;
  onLookup: (event: FormEvent) => void;
  onSelect: (ref: string) => void;
}) {
  if (!embedded) {
    return (
      <div className="customer-lookup">
        <section className="panel">
          <div className="login-brand login-brand--logo">
            <BrandLogo variant="lockup" />
            <p>Track your financing journey</p>
          </div>
          <p className="muted">
            Enter your application reference or phone number to see live status and certificates.
          </p>
          <LookupForm
            lookupRef={lookupRef}
            phone={phone}
            loading={loading}
            error={error}
            setLookupRef={setLookupRef}
            setPhone={setPhone}
            onLookup={onLookup}
            submitLabel="View my journey"
          />
          <MatchList matchedApps={matchedApps} onSelect={onSelect} />
          <div className="customer-sample">
            <p className="customer-kicker">Sample reference</p>
            <button type="button" className="btn btn-secondary btn-sm" onClick={() => onSelect(SAMPLE_REF)}>
              {SAMPLE_REF}
            </button>
          </div>
        </section>
      </div>
    );
  }

  return (
    <WorkspaceLookup
      lookupRef={lookupRef}
      phone={phone}
      loading={loading}
      error={error}
      matchedApps={matchedApps}
      setLookupRef={setLookupRef}
      setPhone={setPhone}
      onLookup={onLookup}
      onSelect={onSelect}
    />
  );
}

function WorkspaceLookup({
  lookupRef,
  phone,
  loading,
  error,
  matchedApps,
  setLookupRef,
  setPhone,
  onLookup,
  onSelect,
}: {
  lookupRef: string;
  phone: string;
  loading: boolean;
  error: string;
  matchedApps: MatchedApp[];
  setLookupRef: (value: string) => void;
  setPhone: (value: string) => void;
  onLookup: (event: FormEvent) => void;
  onSelect: (ref: string) => void;
}) {
  const [recent, setRecent] = useState<Application[]>([]);
  const [recentLoading, setRecentLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    api
      .listApplications()
      .then((items) => {
        if (!alive) return;
        const open = items
          .filter((a) =>
            ["in_progress", "offer_accepted", "eligibility_pending", "offer_pending"].includes(a.status),
          )
          .slice(0, 8);
        setRecent(open.length ? open : items.slice(0, 8));
      })
      .catch(() => {
        if (alive) setRecent([]);
      })
      .finally(() => {
        if (alive) setRecentLoading(false);
      });
    return () => {
      alive = false;
    };
  }, []);

  return (
    <section className="flex flex-col gap-3">
      <header className="grid gap-3 rounded-sm border border-border bg-surface p-3 sm:grid-cols-[1fr_auto] sm:items-center">
        <div className="min-w-0">
          <h2 className="m-0 text-lg font-semibold tracking-tight text-foreground">Customer Journey</h2>
          <p className="m-0 mt-0.5 text-sm text-muted">Live tracker, accept/sign actions, and certificates</p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 sm:justify-end">
          <span className={pillClass}>Workspace</span>
          <Link className="btn btn-secondary btn-sm" to="/customers">
            Customers
          </Link>
          <Link className="btn btn-secondary btn-sm" to="/applications">
            Applications
          </Link>
          <Link className="btn btn-secondary btn-sm" to="/kenya">
            Kenya Ops
          </Link>
        </div>
      </header>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,1fr)]">
        <section className={panelClass}>
          <div className="flex items-baseline justify-between gap-2">
            <h3 className="m-0 text-sm font-semibold">Look up</h3>
            <span className="text-xs text-muted">Reference or phone</span>
          </div>
          <LookupForm
            lookupRef={lookupRef}
            phone={phone}
            loading={loading}
            error={error}
            setLookupRef={setLookupRef}
            setPhone={setPhone}
            onLookup={onLookup}
            submitLabel="Open journey"
            workspace
          />
          <MatchList matchedApps={matchedApps} onSelect={onSelect} workspace />
          <div className="flex flex-wrap items-center gap-2 border-t border-border pt-2.5">
            <span className="text-[0.7rem] uppercase tracking-wide text-muted">Sample</span>
            <button
              type="button"
              className="btn btn-secondary btn-sm font-mono text-xs"
              onClick={() => onSelect(SAMPLE_REF)}
            >
              {SAMPLE_REF}
            </button>
          </div>
        </section>

        <section className={panelClass}>
          <div className="flex items-baseline justify-between gap-2">
            <h3 className="m-0 text-sm font-semibold">Open book</h3>
            <span className="text-xs tabular-nums text-muted">{recent.length} shown</span>
          </div>
          {recentLoading ? (
            <LoadingPanel rows={4} />
          ) : recent.length === 0 ? (
            <EmptyState
              title="No applications yet"
              description="Register a customer, then start a Kenya or Malaysia case."
              action={
                <Link className="btn btn-primary btn-sm" to="/customers">
                  Customers
                </Link>
              }
            />
          ) : (
            <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
              {recent.map((app) => (
                <li key={app.id}>
                  <button
                    type="button"
                    className="flex w-full items-center justify-between gap-2 rounded-sm border border-border bg-surface-elevated px-2.5 py-2 text-left transition-colors hover:border-foreground/40"
                    onClick={() => onSelect(app.customer_ref)}
                  >
                    <span className="min-w-0">
                      <strong className="block truncate text-sm">{app.customer_name || app.customer_ref}</strong>
                      <span className="mono block truncate text-xs text-muted">{app.customer_ref}</span>
                    </span>
                    <span className="flex shrink-0 flex-col items-end gap-1">
                      <span className={statusBadgeClass(app.status)}>
                        {formatWorkflowLabel(app.status, app.current_phase)}
                      </span>
                      <span className="text-xs tabular-nums text-muted">
                        {formatMoney(app.currency, app.amount_requested)}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </section>
  );
}

function LookupForm({
  lookupRef,
  phone,
  loading,
  error,
  setLookupRef,
  setPhone,
  onLookup,
  submitLabel,
  workspace,
}: {
  lookupRef: string;
  phone: string;
  loading: boolean;
  error: string;
  setLookupRef: (value: string) => void;
  setPhone: (value: string) => void;
  onLookup: (event: FormEvent) => void;
  submitLabel: string;
  workspace?: boolean;
}) {
  if (workspace) {
    return (
      <form className="flex flex-col gap-2.5" onSubmit={onLookup}>
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm">
            Application reference
            <input
              className="rounded-sm border border-border bg-background px-2.5 py-2 font-mono text-sm"
              value={lookupRef}
              onChange={(e) => setLookupRef(e.target.value)}
              placeholder={SAMPLE_REF}
              autoComplete="off"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Phone number
            <input
              className="rounded-sm border border-border bg-background px-2.5 py-2 text-sm"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="254700999888"
              type="tel"
              autoComplete="tel"
            />
          </label>
        </div>
        {error ? <Alert tone="error">{error}</Alert> : null}
        <div className="flex flex-wrap gap-2">
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? "Searching…" : submitLabel}
          </button>
        </div>
      </form>
    );
  }

  return (
    <form className="form" onSubmit={onLookup}>
      <label>
        Application reference
        <input
          value={lookupRef}
          onChange={(e) => setLookupRef(e.target.value)}
          placeholder={SAMPLE_REF}
        />
      </label>
      <label>
        Phone number
        <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="254700999888" type="tel" />
      </label>
      {error ? <Alert tone="error">{error}</Alert> : null}
      <button type="submit" className="btn btn-primary" disabled={loading}>
        {loading ? "Searching" : submitLabel}
      </button>
    </form>
  );
}

function MatchList({
  matchedApps,
  onSelect,
  workspace,
}: {
  matchedApps: MatchedApp[];
  onSelect: (ref: string) => void;
  workspace?: boolean;
}) {
  if (matchedApps.length === 0) return null;

  if (workspace) {
    return (
      <div className="flex flex-col gap-1.5 border-t border-border pt-2.5">
        <span className="text-[0.7rem] uppercase tracking-wide text-muted">
          {matchedApps.length} matches
        </span>
        {matchedApps.map((app) => (
          <button
            key={app.application_id}
            type="button"
            className="flex w-full items-center justify-between gap-2 rounded-sm border border-border bg-surface-elevated px-2.5 py-2 text-left hover:border-foreground/40"
            onClick={() => onSelect(app.customer_ref)}
          >
            <span className="min-w-0">
              <strong className="mono block truncate text-sm">{app.customer_ref}</strong>
              <span className="block truncate text-xs text-muted">
                {formatMoney(app.currency || "KES", app.amount)}
                {app.institution ? ` · ${app.institution}` : ""}
              </span>
            </span>
            <span className={statusBadgeClass(app.status)}>{app.status.replace(/_/g, " ")}</span>
          </button>
        ))}
      </div>
    );
  }

  return (
    <div className="customer-match-list">
      <p className="customer-kicker">Select an application</p>
      {matchedApps.map((app) => (
        <button
          key={app.application_id}
          type="button"
          className="customer-match-item"
          onClick={() => onSelect(app.customer_ref)}
        >
          <span>
            <strong className="mono">{app.customer_ref}</strong>
            <span className="muted">
              {app.currency} {parseFloat(app.amount).toLocaleString("en-KE")}
              {app.institution ? ` · ${app.institution}` : ""}
            </span>
          </span>
          <span className={statusBadgeClass(app.status)}>{app.status.replace(/_/g, " ")}</span>
        </button>
      ))}
    </div>
  );
}

function JourneyView({
  embedded,
  journey,
  loading,
  error,
  progress,
  allDone,
  pollingActive,
  openStep,
  setOpenStep,
  onBack,
  onOpenBti,
  onOpenBsas,
  onOpenTradeDoc,
  actionBusy,
  onCustomerAction,
}: {
  embedded: boolean;
  journey: CustomerJourney | null;
  loading: boolean;
  error: string;
  progress: number;
  allDone: boolean;
  pollingActive: boolean;
  openStep: number | null;
  setOpenStep: (value: number | null) => void;
  onBack: () => void;
  onOpenBti: () => void;
  onOpenBsas: (cert: JourneyCertificate, label: string) => void;
  onOpenTradeDoc: (kind: TradeDocKind) => void;
  actionBusy: boolean;
  onCustomerAction: () => void;
}) {
  return (
    <div className={embedded ? "flex flex-col gap-3" : "customer-journey"}>
      {error && journey && <Alert tone="error">{error}</Alert>}
      {loading && !journey && <LoadingPanel rows={6} />}

      {!loading && !journey && (
        <section className={embedded ? panelClass : "panel"}>
          <EmptyState
            title="Journey not found"
            description="Check the application reference or phone number, then try another lookup."
            action={
              <button type="button" className="btn btn-primary btn-sm" onClick={onBack}>
                New lookup
              </button>
            }
          />
        </section>
      )}

      {journey && (
        <>
          {embedded ? (
            <header className="grid gap-3 rounded-sm border border-border bg-surface p-3 lg:grid-cols-[1fr_auto] lg:items-center">
              <div className="min-w-0">
                <div className="mb-1 flex flex-wrap items-center gap-1.5">
                  <span className={pillClass}>
                    {journey.track === "malaysia" ? "Malaysia BSAS" : "Kenya float"}
                  </span>
                  <span className={statusBadgeClass(journey.status)}>
                    {journey.status.replace(/_/g, " ")}
                  </span>
                  {pollingActive ? (
                    <span className={`${pillClass} border-success/40 text-success`}>
                      <span className="size-1.5 rounded-full bg-success" aria-hidden />
                      Live
                    </span>
                  ) : null}
                </div>
                <h2 className="m-0 text-lg font-semibold tracking-tight">
                  {journey.customer_name || journey.customer_ref}
                </h2>
                <p className="m-0 mt-0.5 text-sm text-muted">
                  {formatMoney(journey.currency || "KES", journey.amount)}
                  {journey.murabaha_total
                    ? ` · Murabaha ${formatMoney(journey.currency || "KES", journey.murabaha_total)}`
                    : ""}
                  {journey.institution_name ? ` · ${journey.institution_name}` : ""}
                </p>
                <p className="mono m-0 mt-0.5 text-xs text-muted">{journey.customer_ref}</p>
              </div>
              <div className="flex flex-wrap items-center gap-2 lg:justify-end">
                <div className="min-w-[9rem] flex-1 sm:flex-none">
                  <div className="mb-1 flex justify-between gap-2 text-xs text-muted">
                    <span>Progress</span>
                    <span className="tabular-nums">{progress}%</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-sm bg-border/60" aria-label={`Progress ${progress} percent`}>
                    <span className="block h-full rounded-sm bg-primary" style={{ width: `${progress}%` }} />
                  </div>
                  <p className="m-0 mt-1 text-xs text-muted">
                    {allDone
                      ? "Complete"
                      : `Step ${journey.overall_progress} of ${journey.total_steps}`}
                  </p>
                </div>
                <button type="button" className="btn btn-secondary btn-sm" onClick={onBack}>
                  New lookup
                </button>
              </div>
            </header>
          ) : (
            <section className="panel">
              <div className="panel-header">
                <div>
                  <p className="customer-kicker">
                    {journey.track === "malaysia" ? "Malaysia BSAS" : "Kenya float"} track
                  </p>
                  <h2>{journey.customer_name || journey.customer_ref}</h2>
                  <p className="muted">
                    {journey.currency} {parseFloat(journey.amount).toLocaleString("en-KE")}
                    {journey.murabaha_total && (
                      <>
                        {" "}
                        payable {journey.currency} {parseFloat(journey.murabaha_total).toLocaleString("en-KE")}
                      </>
                    )}
                    {journey.institution_name ? ` · ${journey.institution_name}` : ""}
                  </p>
                  <p className="mono muted">Ref {journey.customer_ref}</p>
                </div>
                <div className="actions">
                  <span className={statusBadgeClass(journey.status)}>{journey.status.replace(/_/g, " ")}</span>
                  <button type="button" className="btn btn-secondary btn-sm" onClick={onBack}>
                    New lookup
                  </button>
                </div>
              </div>
            </section>
          )}

          <section className={embedded ? panelClass : "panel"}>
            <DealTape
              amount={journey.amount}
              termMonths={journey.term_months || journey.steps.find((step) => step.installments_total)?.installments_total || 12}
              currency={journey.currency || "KES"}
              includeSpot={journey.track === "kenya"}
              offer={
                journey.murabaha_total && journey.profit
                  ? {
                      cost_price: journey.amount,
                      profit_amount: journey.profit,
                      total_payable: journey.murabaha_total,
                    }
                  : null
              }
              installmentsTotal={journey.steps.find((step) => step.installments_total)?.installments_total}
              installmentsPaid={journey.steps.find((step) => step.installments_paid !== undefined)?.installments_paid}
            />

            {!embedded ? (
            <div className="customer-progress" aria-label={`Progress ${progress} percent`}>
              <div className="customer-progress-track">
                <div className="customer-progress-fill" style={{ width: `${progress}%` }} />
              </div>
              <p className="muted">
                {allDone
                  ? "Journey complete"
                  : `Step ${journey.overall_progress} of ${journey.total_steps} complete`}
                {pollingActive ? " · Updating" : ""}
              </p>
            </div>
            ) : null}
            {journey.customer_action ? (
              <div className="customer-action">
                <p>
                  {journey.customer_action === "accept"
                    ? "The bank locked the Murabaha price. Accept it here. Institution ops cannot accept for you."
                    : "Accept is recorded. Sign the Murabaha contract to move title."}
                </p>
                {journey.murabaha_total ? (
                  <p className="muted">
                    You will repay {journey.currency} {parseFloat(journey.murabaha_total).toLocaleString("en-KE")}
                    {journey.profit
                      ? `, including ${journey.currency} ${parseFloat(journey.profit).toLocaleString("en-KE")} profit`
                      : ""}
                    .
                  </p>
                ) : null}
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={actionBusy}
                  onClick={onCustomerAction}
                >
                  {actionBusy
                    ? "Saving…"
                    : journey.customer_action === "accept"
                      ? "Accept Murabaha offer"
                      : "Sign Murabaha contract"}
                </button>
              </div>
            ) : null}

            {(journey.wad_accepted || journey.trade_documents?.purchase_order) && (
              <ul className="meta-list trade-doc-list">
                {journey.wad_accepted ? <li>Wa'd recorded</li> : null}
                {journey.trade_documents?.commodity_label ? (
                  <li>Commodity {journey.trade_documents.commodity_label}</li>
                ) : null}
                {journey.trade_documents?.purchase_order ? (
                  <li className="trade-doc-row">
                    <span>e-PO <span className="mono">{journey.trade_documents.purchase_order}</span></span>
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => onOpenTradeDoc("purchase_order")}>
                      Download
                    </button>
                  </li>
                ) : null}
                {journey.trade_documents?.supplier_invoice ? (
                  <li className="trade-doc-row">
                    <span>Invoice <span className="mono">{journey.trade_documents.supplier_invoice}</span></span>
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => onOpenTradeDoc("supplier_invoice")}>
                      Download
                    </button>
                  </li>
                ) : null}
                {journey.trade_documents?.delivery_order ? (
                  <li className="trade-doc-row">
                    <span>
                      DO {journey.trade_documents.commodity_label ? `${journey.trade_documents.commodity_label} · ` : ""}
                      <span className="mono">{journey.trade_documents.delivery_order}</span>
                    </span>
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => onOpenTradeDoc("delivery_order")}>
                      Download
                    </button>
                  </li>
                ) : null}
              </ul>
            )}
          </section>

          <div className={embedded ? "grid gap-3 lg:grid-cols-2" : "page-grid"}>
            <section className={embedded ? panelClass : "panel"}>
              {embedded ? (
                <h3 className="m-0 text-sm font-semibold">Financing steps</h3>
              ) : (
                <h2>Financing steps</h2>
              )}
              <ol className="customer-steps">
                {journey.steps.map((step) => {
                  const expanded = openStep === step.number;
                  return (
                    <li key={step.number} className="customer-step" data-status={step.status}>
                      <button
                        type="button"
                        className="customer-step-toggle"
                        aria-expanded={expanded}
                        onClick={() => setOpenStep(expanded ? null : step.number)}
                      >
                        <span className="customer-step-num">{step.number}</span>
                        <span className="customer-step-copy">
                          <strong>{step.label}</strong>
                          <span className="muted">{step.actor}</span>
                        </span>
                        <span className={statusBadgeClass(step.status)}>{step.status}</span>
                      </button>
                      {expanded && (
                        <div className="customer-step-detail">
                          <p>{step.description}</p>
                          {step.timestamp && (
                            <p className="muted">
                              {new Date(step.timestamp).toLocaleString("en-KE")}
                            </p>
                          )}
                          {step.wad_accepted && step.wad_text ? (
                            <p className="muted">Wa'd recorded: {step.wad_text}</p>
                          ) : null}
                          {step.documents?.purchase_order ? (
                            <ul className="meta-list trade-doc-list">
                              <li className="trade-doc-row">
                                <span>e-PO <span className="mono">{step.documents.purchase_order}</span></span>
                                <button type="button" className="btn btn-secondary btn-sm" onClick={() => onOpenTradeDoc("purchase_order")}>
                                  Download
                                </button>
                              </li>
                              {step.documents.supplier_invoice ? (
                                <li className="trade-doc-row">
                                  <span>Invoice <span className="mono">{step.documents.supplier_invoice}</span></span>
                                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => onOpenTradeDoc("supplier_invoice")}>
                                    Download
                                  </button>
                                </li>
                              ) : null}
                              {step.documents.delivery_order ? (
                                <li className="trade-doc-row">
                                  <span>
                                    DO {step.documents.commodity_label ? `${step.documents.commodity_label} · ` : ""}
                                    <span className="mono">{step.documents.delivery_order}</span>
                                  </span>
                                  <button type="button" className="btn btn-secondary btn-sm" onClick={() => onOpenTradeDoc("delivery_order")}>
                                    Download
                                  </button>
                                </li>
                              ) : null}
                              {step.documents.receipt_id ? <li>Receipt <span className="mono">{step.documents.receipt_id}</span></li> : null}
                              {step.documents.batch_id ? <li>Batch {step.documents.batch_id}</li> : null}
                            </ul>
                          ) : null}
                          {step.certificate ? (
                            <p className="muted">
                              {step.certificate.type === "bti_tawarruq_cert" ? "Tawarruq certificate" : "Certificate"}{" "}
                              <span className="mono">{step.certificate.certificate_number}</span>
                            </p>
                          ) : null}
                          {step.wakala_ref ? (
                            <p className="muted">
                              Wakala consent <span className="mono">{step.wakala_ref}</span>
                            </p>
                          ) : null}
                          {step.wallet_txn_id ? (
                            <p className="muted">
                              Wallet {step.wallet_provider || "credit"} <span className="mono">{step.wallet_txn_id}</span>
                              {step.wallet_credited ? " credited" : ""}
                            </p>
                          ) : null}
                          {step.payments && step.payments.length > 0 ? (
                            <ul className="meta-list">
                              {step.payments.map((payment) => (
                                <li key={payment.installment_number}>
                                  Instalment {payment.installment_number} {payment.status}
                                  {payment.payment_ref ? (
                                    <>
                                      {" "}
                                      <span className="mono">{payment.payment_ref}</span>
                                    </>
                                  ) : null}
                                </li>
                              ))}
                            </ul>
                          ) : step.installments_total !== undefined ? (
                            <p className="muted">
                              Installments {step.installments_paid} of {step.installments_total} paid
                              {step.next_due ? `. Next due ${step.next_due}` : ""}
                            </p>
                          ) : null}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ol>
            </section>

            <section className={embedded ? panelClass : "panel"}>
              {embedded ? (
                <h3 className="m-0 text-sm font-semibold">Certificates</h3>
              ) : (
                <h2>Certificates</h2>
              )}
              {journey.certificates.length === 0 ? (
                <EmptyState
                  title="No certificates yet"
                  description="Download buttons appear here after each confirmed leg."
                />
              ) : (
                <ul className="customer-certs">
                  {journey.certificates.map((cert, index) => (
                    <li key={`${cert.certificate_number}-${index}`} className="customer-cert">
                      <div>
                        <strong>{cert.label}</strong>
                        <p className="mono muted">{cert.certificate_number}</p>
                        <p className="muted">{cert.issuer}</p>
                      </div>
                        <button
                          type="button"
                          className="btn btn-secondary btn-sm"
                          onClick={() => {
                            if (cert.type === "bti_tawarruq_cert") {
                              onOpenBti();
                              return;
                            }
                            if (cert.type?.startsWith("trade_")) {
                              onOpenTradeDoc(cert.type.replace("trade_", "") as TradeDocKind);
                              return;
                            }
                            onOpenBsas(cert, String(cert.step));
                          }}
                        >
                          {cert.type?.startsWith("trade_") ? "Download" : "View"}
                        </button>
                    </li>
                  ))}
                </ul>
              )}

              {journey.overall_progress >= 7 && (
                <div className="customer-cert-cta">
                  <div>
                    <strong>Certificate of Tawarruq</strong>
                    <p className="muted">Official Buruuj execution certificate is ready to print.</p>
                  </div>
                  <button type="button" className="btn btn-primary btn-sm" onClick={onOpenBti}>
                    Open
                  </button>
                </div>
              )}

              {allDone && (
                <div className="customer-compliance">
                  <strong>Shariah compliant transaction</strong>
                  <p className="muted">
                    This Tawarruq financing followed Bay al-Murabahah principles. Constructive
                    possession was confirmed and the Bai al-Inah guardrail was validated.
                  </p>
                </div>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}
