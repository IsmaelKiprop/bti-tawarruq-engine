import type { CustomerJourney } from "../api/client";

export type TradeDocKind = "purchase_order" | "supplier_invoice" | "delivery_order";

const LABELS: Record<TradeDocKind, string> = {
  purchase_order: "Purchase order (e-PO)",
  supplier_invoice: "Supplier invoice",
  delivery_order: "Delivery order",
};

export function TradeDocumentModal({
  journey,
  kind,
  onClose,
}: {
  journey: CustomerJourney;
  kind: TradeDocKind;
  onClose: () => void;
}) {
  const docs = journey.trade_documents;
  const ref =
    kind === "purchase_order"
      ? docs?.purchase_order
      : kind === "supplier_invoice"
        ? docs?.supplier_invoice
        : docs?.delivery_order;

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal-panel"
        role="dialog"
        aria-modal="true"
        aria-label={LABELS[kind]}
        onClick={(event) => event.stopPropagation()}
      >
        <div className="panel-header">
          <div>
            <h2>{LABELS[kind]}</h2>
            <p className="muted">
              {docs?.commodity_label ? `Commodity: ${docs.commodity_label}` : "Trade document"}
            </p>
          </div>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onClose}>
            Close
          </button>
        </div>
        <p className="mono">{ref || "No reference on file"}</p>
        <p className="meta">Customer ref {journey.customer_ref}</p>
      </div>
    </div>
  );
}
