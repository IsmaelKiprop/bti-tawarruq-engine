import { COMMODITY_EXPLAIN } from "../config/malaysiaOps";

export function CommodityExplain() {
  return (
    <section className="panel">
      <h2>{COMMODITY_EXPLAIN.title}</h2>
      <p className="muted">{COMMODITY_EXPLAIN.lead}</p>
      <h3>{COMMODITY_EXPLAIN.dealTitle}</h3>
      <ol className="flow-list numbered">
        {COMMODITY_EXPLAIN.dealSteps.map((step) => (
          <li key={step}>{step}</li>
        ))}
      </ol>
      <p className="meta">{COMMODITY_EXPLAIN.desk}</p>
    </section>
  );
}
