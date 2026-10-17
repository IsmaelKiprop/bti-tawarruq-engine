import type { AgentDealerSummary, KenyaOpsCase } from "../api/client";
import { computeKenyaDeal, DEFAULT_PROFIT_RATE_PCT } from "../config/kenyaOps";

type OfferLike = {
  cost_price: string;
  profit_amount: string;
  total_payable: string;
  accepted?: boolean;
} | null;

type DealTapeProps = {
  amount: string | number;
  termMonths: number;
  profitRatePct?: number;
  onProfitRateChange?: (value: number) => void;
  currency?: string;
  includeSpot?: boolean;
  offer?: OfferLike;
  installmentsTotal?: number | null;
  installmentsPaid?: number | null;
};

function money(currency: string, value: number) {
  return `${currency} ${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

export function DealTape({
  amount,
  termMonths,
  profitRatePct = DEFAULT_PROFIT_RATE_PCT,
  onProfitRateChange,
  currency = "KES",
  includeSpot = true,
  offer = null,
  installmentsTotal,
  installmentsPaid,
}: DealTapeProps) {
  const deal = computeKenyaDeal({ amount, termMonths, profitRatePct, currency, offer });
  return (
    <div className="deal-tape">
      <div className="deal-tape-grid">
        <div>
          <span className="meta">Commodity cost</span>
          <strong>{money(deal.currency, deal.cost)}</strong>
        </div>
        <div>
          <span className="meta">Profit rate</span>
          {onProfitRateChange ? (
            <label className="deal-tape-rate">
              <input
                type="number"
                step="0.01"
                min="0"
                value={profitRatePct}
                onChange={(e) => onProfitRateChange(Number(e.target.value))}
              />
              <span>%</span>
            </label>
          ) : (
            <strong>{deal.profitRatePct}%</strong>
          )}
        </div>
        <div>
          <span className="meta">Profit</span>
          <strong>{money(deal.currency, deal.profit)}</strong>
        </div>
        <div>
          <span className="meta">Murabaha total</span>
          <strong>{money(deal.currency, deal.total)}</strong>
        </div>
        <div>
          <span className="meta">Term</span>
          <strong>{deal.termMonths} mo</strong>
        </div>
        <div>
          <span className="meta">Instalment</span>
          <strong>{money(deal.currency, deal.installment)}</strong>
        </div>
        {includeSpot ? (
          <div>
            <span className="meta">Spot desk</span>
            <strong>Kenya float</strong>
          </div>
        ) : null}
        {installmentsTotal != null ? (
          <div>
            <span className="meta">Instalments</span>
            <strong>
              {installmentsPaid ?? 0}/{installmentsTotal}
            </strong>
          </div>
        ) : null}
      </div>
      {offer?.accepted ? <p className="meta">Offer accepted — totals are locked.</p> : null}
    </div>
  );
}

export function PoolTape({
  balance,
  topup = 0,
  previewTopup,
}: {
  balance: number;
  topup?: number;
  previewTopup?: boolean;
}) {
  const next = balance + (previewTopup ? topup : 0);
  return (
    <div className="deal-tape">
      <div className="deal-tape-grid">
        <div>
          <span className="meta">Float balance</span>
          <strong>{money("KES", balance)}</strong>
        </div>
        {previewTopup ? (
          <>
            <div>
              <span className="meta">Top-up preview</span>
              <strong>{money("KES", topup)}</strong>
            </div>
            <div>
              <span className="meta">After top-up</span>
              <strong>{money("KES", next)}</strong>
            </div>
          </>
        ) : null}
      </div>
    </div>
  );
}

export function BookTape({
  items,
  title = "Book tape",
}: {
  items: { amount: string | number; termMonths: number; currency?: string }[];
  title?: string;
}) {
  const total = items.reduce((sum, row) => sum + Number(row.amount || 0), 0);
  return (
    <div className="deal-tape">
      <div className="panel-header">
        <h3>{title}</h3>
        <span className="meta">{items.length} journeys</span>
      </div>
      <div className="deal-tape-grid">
        <div>
          <span className="meta">Open cost</span>
          <strong>{money("KES", total)}</strong>
        </div>
        <div>
          <span className="meta">Preview Murabaha @ {DEFAULT_PROFIT_RATE_PCT}%</span>
          <strong>{money("KES", total * (1 + DEFAULT_PROFIT_RATE_PCT / 100))}</strong>
        </div>
      </div>
    </div>
  );
}

export function RepaymentTape({
  items,
}: {
  items: { amount_due?: string | number; status?: string }[];
}) {
  const due = items.reduce((sum, row) => sum + Number(row.amount_due || 0), 0);
  return (
    <div className="deal-tape">
      <div className="deal-tape-grid">
        <div>
          <span className="meta">Rows</span>
          <strong>{items.length}</strong>
        </div>
        <div>
          <span className="meta">Amount due</span>
          <strong>{money("KES", due)}</strong>
        </div>
      </div>
    </div>
  );
}

export function MurabahaTape({
  caseData,
  profitRatePct,
  onProfitRateChange,
}: {
  caseData: KenyaOpsCase;
  profitRatePct: number;
  onProfitRateChange?: (value: number) => void;
}) {
  return (
    <DealTape
      amount={caseData.amount_requested}
      termMonths={caseData.term_months}
      profitRatePct={profitRatePct}
      onProfitRateChange={caseData.offer ? undefined : onProfitRateChange}
      offer={caseData.offer}
      installmentsTotal={caseData.installments_total}
      installmentsPaid={caseData.installments_paid}
    />
  );
}

export function PossessionTape({
  caseData,
  dealer,
}: {
  caseData: KenyaOpsCase;
  dealer: AgentDealerSummary | null;
}) {
  return (
    <div className="deal-tape">
      <div className="deal-tape-grid">
        <div>
          <span className="meta">Possession</span>
          <strong>{caseData.possession_sealed ? "Sealed" : "Open"}</strong>
        </div>
        <div>
          <span className="meta">Supplier / pool</span>
          <strong>
            {dealer?.primary_dealer?.business_name || caseData.broker_name || "—"}
          </strong>
        </div>
        <div>
          <span className="meta">Float cost</span>
          <strong>{money("KES", Number(caseData.amount_requested || 0))}</strong>
        </div>
      </div>
    </div>
  );
}

export function WakalaTape({ caseData }: { caseData: KenyaOpsCase }) {
  return (
    <div className="deal-tape">
      <div className="deal-tape-grid">
        <div>
          <span className="meta">Wakala</span>
          <strong>{caseData.wakala_appointed ? "Appointed" : "Pending"}</strong>
        </div>
        <div>
          <span className="meta">Notes</span>
          <strong>{caseData.wakala_notes || "—"}</strong>
        </div>
      </div>
    </div>
  );
}

export function SettlementTape({ caseData }: { caseData: KenyaOpsCase }) {
  return (
    <div className="deal-tape">
      <div className="deal-tape-grid">
        <div>
          <span className="meta">Status</span>
          <strong>{caseData.status}</strong>
        </div>
        <div>
          <span className="meta">Next action</span>
          <strong>{caseData.next_action_label || caseData.next_action || "—"}</strong>
        </div>
        <div>
          <span className="meta">Paid / total</span>
          <strong>
            {caseData.installments_paid ?? 0}/{caseData.installments_total ?? "—"}
          </strong>
        </div>
      </div>
    </div>
  );
}

export function AuditTape({ caseData }: { caseData: KenyaOpsCase }) {
  return (
    <div className="deal-tape">
      <div className="deal-tape-grid">
        <div>
          <span className="meta">Application</span>
          <strong className="mono">{caseData.application_id}</strong>
        </div>
        <div>
          <span className="meta">Transaction</span>
          <strong className="mono">{caseData.transaction_id || "—"}</strong>
        </div>
        <div>
          <span className="meta">Phase</span>
          <strong>{caseData.current_phase || "—"}</strong>
        </div>
      </div>
    </div>
  );
}

export function MalaysiaLegTape({
  currency,
  bid,
  profit,
  total,
  legNumber,
}: {
  currency: string;
  bid: string;
  profit: string;
  total: string;
  legNumber: string;
}) {
  return (
    <div className="deal-tape">
      <div className="deal-tape-grid">
        <div>
          <span className="meta">Leg {legNumber} bid</span>
          <strong>
            {currency} {bid}
          </strong>
        </div>
        <div>
          <span className="meta">Profit</span>
          <strong>
            {currency} {profit}
          </strong>
        </div>
        <div>
          <span className="meta">Murabaha</span>
          <strong>
            {currency} {total}
          </strong>
        </div>
      </div>
    </div>
  );
}

export function MalaysiaSettlementTape({
  currency,
  amount,
  status,
}: {
  currency?: string;
  amount?: string | number;
  status?: string;
  [key: string]: unknown;
}) {
  return (
    <div className="deal-tape">
      <div className="deal-tape-grid">
        <div>
          <span className="meta">Settlement</span>
          <strong>{status || "Pending"}</strong>
        </div>
        <div>
          <span className="meta">Amount</span>
          <strong>
            {currency || "MYR"} {String(amount ?? "—")}
          </strong>
        </div>
      </div>
    </div>
  );
}
