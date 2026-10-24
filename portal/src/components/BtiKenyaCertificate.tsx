import { useRef } from "react";
import type { CustomerJourney } from "../api/client";
import { BrandLogo } from "./BrandLogo";

interface Props {
  journey: CustomerJourney;
  onClose?: () => void;
  embedded?: boolean;
}

function money(currency: string, value?: string | null) {
  if (value == null || value === "") return null;
  const amount = Number(value);
  if (Number.isNaN(amount)) return `${currency} ${value}`;
  return `${currency} ${amount.toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formalDate(value?: string | null) {
  if (!value) return "Not recorded";
  return new Date(value).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

function formalDateTime(value?: string | null) {
  if (!value) return "Not recorded";
  return new Date(value).toLocaleString("en-GB", {
    day: "numeric",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function commodityLabel(journey: CustomerJourney) {
  if (journey.track === "malaysia") {
    return journey.commodity === "PALM_OIL" || !journey.commodity
      ? "Crude palm oil (ACPO) on Bursa Suq Al-Sila'"
      : journey.commodity;
  }
  if (journey.commodity === "FLOAT_MPESA_DEALER" || journey.commodity?.includes("AIRTIME")) {
    return "Safaricom digital float / airtime";
  }
  return journey.commodity || "Not recorded";
}

export function BtiKenyaCertificate({ journey, onClose, embedded = false }: Props) {
  const printRef = useRef<HTMLDivElement>(null);

  const certNumber =
    journey.certificates.find((c) => c.type === "bti_tawarruq_cert")?.certificate_number ??
    `BURUUJ-${journey.track === "malaysia" ? "MY" : "KE"}-${new Date().toISOString().slice(0, 10).replace(/-/g, "")}-${journey.customer_ref.slice(-6).toUpperCase()}`;

  const purchaseStep = journey.steps.find((s) => s.number === 2);
  const murabahaStep = journey.steps.find((s) => s.number === 4);
  const liquidationStep = journey.steps.find((s) => s.number === 6);
  const disbursementStep = journey.steps.find((s) => s.number === 8) ?? journey.steps.find((s) => s.number === 7);
  const issuedAt =
    disbursementStep?.timestamp ||
    [...journey.steps].reverse().find((s) => s.timestamp)?.timestamp ||
    journey.created_at;

  const supplier =
    purchaseStep?.certificate?.issuer ||
    (journey.track === "malaysia" ? "Bursa Malaysia Islamic Services" : "Licensed float supplier");

  const auditUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/shariah?cert=${encodeURIComponent(certNumber)}`
      : certNumber;
  const qrSrc = `https://api.qrserver.com/v1/create-qr-code/?size=120x120&margin=8&data=${encodeURIComponent(auditUrl)}`;

  function handlePrint() {
    window.print();
  }

  const cost = money(journey.currency, journey.amount);
  const profit = money(journey.currency, journey.profit);
  const total = money(journey.currency, journey.murabaha_total);

  const trail = [
    {
      num: "01",
      title: "Spot purchase",
      detail: "The financing institution acquires the commodity from the supplier.",
      step: purchaseStep,
    },
    {
      num: "02",
      title: "Murabahah sale",
      detail: "The institution sells the same commodity to the customer on deferred payment.",
      step: murabahaStep,
    },
    {
      num: "03",
      title: "Independent liquidation",
      detail: "The customer, through the wakeel, sells to an independent third-party buyer.",
      step: liquidationStep,
    },
    {
      num: "04",
      title: "Disbursement",
      detail: "Net proceeds are credited to the customer after settlement.",
      step: disbursementStep,
    },
  ];

  const content = (
    <article className="bti-cert-paper" ref={printRef} aria-label="Buruuj Tawarruq execution certificate">
      <div className="bti-cert-frame">
        <header className="bti-cert-masthead">
          <div className="bti-cert-brand">
            <BrandLogo variant="lockup" className="bti-cert-logo" />
            <p className="bti-cert-entity-sub">Digital Islamic finance. Authorised Tawarruq execution agent.</p>
          </div>
          <div className="bti-cert-serial">
            <span>Certificate no.</span>
            <strong className="mono">{certNumber}</strong>
          </div>
        </header>

        <div className="bti-cert-titleblock">
          <p className="bti-cert-kicker">Shariah execution instrument</p>
          <h1>Certificate of Tawarruq</h1>
          <p className="bti-cert-subtitle">
            Issued upon completion of a Bay al-Murabahah commodity financing arranged for the
            named institution and customer.
          </p>
        </div>

        <dl className="bti-cert-meta">
          <div>
            <dt>Date of issue</dt>
            <dd>{formalDate(issuedAt)}</dd>
          </div>
          <div>
            <dt>Application</dt>
            <dd className="mono">{journey.customer_ref}</dd>
          </div>
          <div>
            <dt>Market</dt>
            <dd>{journey.track === "malaysia" ? "Malaysia. Suq Al-Sila'" : "Kenya. Float / airtime"}</dd>
          </div>
          <div>
            <dt>Status</dt>
            <dd>{journey.overall_progress >= 7 ? "Executed and recorded" : "In progress"}</dd>
          </div>
        </dl>

        <section>
          <h2>Parties</h2>
          <table className="bti-cert-table">
            <tbody>
              <tr>
                <th>Customer</th>
                <td>
                  <strong>{journey.customer_name || journey.customer_ref}</strong>
                  {journey.customer_phone ? <span className="bti-cert-quiet"> {journey.customer_phone}</span> : null}
                </td>
              </tr>
              <tr>
                <th>Financing institution</th>
                <td>{journey.institution_name || "Not recorded"}</td>
              </tr>
              <tr>
                <th>Execution agent</th>
                <td>Buruuj Fintech Ltd, acting as wakeel</td>
              </tr>
              <tr>
                <th>Commodity supplier</th>
                <td>{supplier}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section>
          <h2>Facility and commodity</h2>
          <table className="bti-cert-table">
            <tbody>
              <tr>
                <th>Underlying commodity</th>
                <td>{commodityLabel(journey)}</td>
              </tr>
              <tr>
                <th>Spot cost (principal)</th>
                <td>{cost || "Not recorded"}</td>
              </tr>
              {profit && (
                <tr>
                  <th>Murabahah profit</th>
                  <td>{profit}</td>
                </tr>
              )}
              <tr>
                <th>Deferred selling price</th>
                <td className="bti-cert-total">{total || cost || "Not recorded"}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section>
          <h2>Execution record</h2>
          <ol className="bti-cert-trail">
            {trail.map((item) => {
              const done = item.step?.status === "done";
              return (
                <li key={item.num} className={done ? "is-done" : undefined}>
                  <span className="bti-cert-trail-num">{item.num}</span>
                  <div>
                    <strong>{item.title}</strong>
                    <p>{item.detail}</p>
                    <p className="bti-cert-trail-time">
                      {done ? `Completed ${formalDateTime(item.step?.timestamp)}` : "Awaiting completion"}
                    </p>
                  </div>
                </li>
              );
            })}
          </ol>
        </section>

        <section className="bti-cert-attestation">
          <h2>Attestation</h2>
          <p>
            Buruuj Fintech Ltd certifies that this Tawarruq was executed in the order required for
            Bay al-Murabahah. Constructive possession was recorded before the deferred sale. The
            customer appointed the wakeel before liquidation. The spot sale was to an independent
            buyer, so the transaction is not Bai al-Inah. Each step is stored on the Buruuj Shariah
            audit ledger.
          </p>
        </section>

        <footer className="bti-cert-footer">
          <div className="bti-cert-sign">
            <div className="bti-cert-sign-line" />
            <strong>Authorised officer</strong>
            <span>Buruuj Fintech Ltd</span>
            <span>Tawarruq execution agent</span>
          </div>
          <div className="bti-cert-verify">
            <img className="bti-cert-qr" src={qrSrc} alt={`Verification code for ${certNumber}`} />
            <p>Scan to open the ledger entry</p>
          </div>
          <div className="bti-cert-seal" aria-hidden="true">
            <BrandLogo variant="mark" className="bti-cert-seal-logo" alt="" />
            <small>Verified</small>
          </div>
        </footer>

        <p className="bti-cert-legal">
          This certificate is evidence of execution on the Buruuj engine. It is not a negotiable
          instrument and does not replace the institution Murabahah contract. Quote {certNumber}{" "}
          in any audit enquiry.
        </p>
      </div>
    </article>
  );

  if (embedded) return content;

  return (
    <div className="cert-modal-overlay" onClick={onClose} role="presentation">
      <div
        className="cert-modal bti-cert-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="bti-cert-dialog-title"
      >
        <div className="cert-modal-actions">
          <div>
            <p className="cert-modal-kicker">Official record</p>
            <p id="bti-cert-dialog-title" className="cert-modal-leg-badge">
              Certificate of Tawarruq
            </p>
          </div>
          <div className="cert-modal-buttons">
            <button className="btn btn-primary btn-sm" type="button" onClick={handlePrint}>
              Print
            </button>
            {onClose && (
              <button className="btn btn-secondary btn-sm" type="button" onClick={onClose}>
                Close
              </button>
            )}
          </div>
        </div>
        {content}
      </div>
    </div>
  );
}
