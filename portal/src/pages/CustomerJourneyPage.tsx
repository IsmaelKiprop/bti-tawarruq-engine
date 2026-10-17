import { FormEvent, useCallback, useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, CustomerJourney, JourneyCertificate } from "../api/client";
import type { Certificate } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { BrandLogo } from "../components/BrandLogo";
import { BsasCertificateModal } from "../components/BsasCertificateModal";
import { BtiKenyaCertificate } from "../components/BtiKenyaCertificate";
import { TradeDocumentModal, type TradeDocKind } from "../components/TradeDocumentModal";
import { DealTape } from "../components/DealTape";
import { HowItWorks, PageExplain } from "../components/PageExplain";
import { Alert, EmptyState, LoadingPanel, PageShell, statusBadgeClass } from "../components/PageShell";
import { HOW_IT_WORKS, PAGE_EXPLAINS } from "../config/pageExplainers";
import "../components/ui.css";
import "./CustomerJourneyPage.css";

interface MatchedApp {
  application_id: string;
  customer_ref: string;
  amount: string;
  currency?: string;
  status: string;
  institution: string | null;
  created_at: string | null;
}

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
  return (
    <div className={embedded ? "customer-lookup customer-lookup-embedded" : "customer-lookup"}>
      <PageExplain content={PAGE_EXPLAINS["/customer"]} />
      <HowItWorks content={HOW_IT_WORKS["/customer"]} />
      <section className="panel">
        {embedded ? (
          <div className="panel-header">
            <div>
              <p className="customer-kicker">Customer visibility</p>
              <h2>Look up a journey</h2>
              <p className="muted">
                Enter an application reference or phone number to open live status and certificates.
              </p>
            </div>
          </div>
        ) : (
          <>
            <div className="login-brand login-brand--logo">
              <BrandLogo variant="lockup" />
              <p>Track your financing journey</p>
            </div>
            <p className="muted">
              Enter your application reference or phone number to see live status and certificates.
            </p>
          </>
        )}
        <form className="form" onSubmit={onLookup}>
          <label>
            Application reference
            <input
              value={lookupRef}
              onChange={(e) => setLookupRef(e.target.value)}
              placeholder="CUST-DEFAULT-2026-0003"
            />
          </label>
          <label>
            Phone number
            <input
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="254700999888"
              type="tel"
            />
          </label>
          {error && <Alert tone="error">{error}</Alert>}
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? "Searching" : "View my journey"}
          </button>
        </form>

        {matchedApps.length > 0 && (
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
        )}

        <div className="customer-sample">
          <p className="customer-kicker">Sample reference</p>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => onSelect("CUST-DEFAULT-2026-0003")}
          >
            CUST-DEFAULT-2026-0003
          </button>
        </div>
      </section>
    </div>
  );
}

function JourneyView({
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
    <div className="customer-journey">
      {error && journey && <Alert tone="error">{error}</Alert>}
      {loading && !journey && <LoadingPanel rows={6} />}

      {!loading && !journey && (
        <section className="panel">
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

          <div className="page-grid">
            <section className="panel">
              <h2>Financing steps</h2>
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

            <section className="panel">
              <h2>Certificates</h2>
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
