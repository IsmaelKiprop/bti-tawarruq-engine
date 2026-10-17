import { useRef } from "react";
import type { Certificate } from "../api/client";
import "./BsasCertificateModal.css";

interface Props {
  certificate: Certificate;
  legLabel: string;
  onClose: () => void;
}

const LEG_TITLES: Record<string, string> = {
  "1": "Leg 1. Commodity purchase",
  "2": "Leg 2. Murabahah transfer",
  "3": "Leg 3. Independent sale",
};

function money(currency: string | null | undefined, value?: string | null) {
  if (value == null || value === "") return null;
  const amount = Number(value);
  const prefix = currency ? `${currency} ` : "";
  if (Number.isNaN(amount)) return `${prefix}${value}`;
  return `${prefix}${amount.toLocaleString("en-MY", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function Row({ label, value }: { label: string; value?: string | null }) {
  if (value == null || value === "" || value === "-") return null;
  return (
    <tr>
      <th>{label}</th>
      <td>{value}</td>
    </tr>
  );
}

export function BsasCertificateModal({ certificate, legLabel, onClose }: Props) {
  const printRef = useRef<HTMLDivElement>(null);
  const issuer = certificate.issuer || "Bursa Malaysia Islamic Services Sdn. Bhd.";
  const title = LEG_TITLES[legLabel] || `Suq Al-Sila' certificate. ${legLabel}`;
  const received = certificate.received_at
    ? new Date(certificate.received_at).toLocaleDateString("en-GB", {
        day: "numeric",
        month: "long",
        year: "numeric",
      })
    : null;

  return (
    <div className="cert-modal-overlay" onClick={onClose} role="presentation">
      <div
        className="cert-modal bsas-cert-modal"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="bsas-cert-dialog-title"
      >
        <div className="cert-modal-actions">
          <div>
            <p className="cert-modal-kicker">Exchange evidence</p>
            <p id="bsas-cert-dialog-title" className="cert-modal-leg-badge">
              {title}
            </p>
          </div>
          <div className="cert-modal-buttons">
            <button className="btn btn-primary btn-sm" type="button" onClick={() => window.print()}>
              Print
            </button>
            <button className="btn btn-secondary btn-sm" type="button" onClick={onClose}>
              Close
            </button>
          </div>
        </div>

        <article className="bsas-cert-paper" ref={printRef} aria-label="Islamic Services Receipt">
          <div className="bsas-cert-frame">
            <header className="bsas-cert-masthead">
              <div>
                <p className="bsas-cert-kicker">Bursa Suq Al-Sila'</p>
                <h1>Islamic Services Receipt</h1>
                <p className="bsas-cert-issuer">{issuer}</p>
              </div>
              <div className="bsas-cert-serial">
                <span>Receipt no.</span>
                <strong className="mono">{certificate.certificate_number}</strong>
                {received ? <em>Recorded {received}</em> : null}
              </div>
            </header>

            <p className="bsas-cert-lede">
              Evidence of a Shariah-compliant commodity trade recorded from the Suq Al-Sila'
              desk. Fields below are taken from the Islamic Services Receipt supplied by the
              exchange or appointed desk.
            </p>

            <section>
              <h2>Transaction</h2>
              <table className="bsas-cert-table">
                <tbody>
                  <Row label="Seller" value={certificate.seller} />
                  <Row label="Buyer" value={certificate.buyer} />
                  <Row label="Bid number" value={certificate.bid_no} />
                  <Row label="Selling time" value={certificate.selling_time} />
                  <Row label="Selling date" value={certificate.selling_date} />
                  <Row label="Value date" value={certificate.value_date} />
                  <Row label="Transaction type" value={certificate.transaction_type} />
                </tbody>
              </table>
            </section>

            <section>
              <h2>Commodity</h2>
              <table className="bsas-cert-table">
                <tbody>
                  <Row label="Product code" value={certificate.product_code} />
                  <Row label="Description" value={certificate.product_description} />
                  <Row label="Unit" value={certificate.unit} />
                  <Row label="Volume" value={certificate.volume} />
                </tbody>
              </table>
            </section>

            <section>
              <h2>Consideration</h2>
              <table className="bsas-cert-table">
                <tbody>
                  <Row label="Currency" value={certificate.currency} />
                  <Row label="Price" value={certificate.price} />
                  <Row
                    label="Price, MYR equivalent"
                    value={certificate.price_myr_equivalent}
                  />
                  {certificate.value_amount ? (
                    <tr>
                      <th>Total value</th>
                      <td className="bsas-cert-total">
                        {money(certificate.currency, certificate.value_amount)}
                      </td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </section>

            <section>
              <h2>Issuing authority</h2>
              <table className="bsas-cert-table">
                <tbody>
                  <tr>
                    <th>Issuer</th>
                    <td>{issuer}</td>
                  </tr>
                  {certificate.pdf_filename ? (
                    <tr>
                      <th>Source file</th>
                      <td>{certificate.pdf_filename}</td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </section>

            <footer className="bsas-cert-footer">
              <p>
                This page is Buruuj Fintech's official rendering of the Suq Al-Sila' receipt for
                audit. It is governed by the Rules of Bursa Suq Al-Sila' and does not itself
                constitute exchange membership. The certificate number must match the desk
                original.
              </p>
              <div className="bsas-cert-endorsement">
                <div className="bsas-cert-sign">
                  <div className="bsas-cert-sign-line" />
                  <strong>Recorded by Buruuj operations</strong>
                  <span>Against the desk receipt</span>
                </div>
                <div className="bsas-cert-stamp" aria-hidden="true">
                  <span>BSAS</span>
                  <small>Recorded</small>
                </div>
              </div>
            </footer>
          </div>
        </article>
      </div>
    </div>
  );
}
