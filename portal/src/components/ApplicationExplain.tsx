import { APPLICATION_EXPLAIN } from "../config/applicationOps";

export function ApplicationExplain() {
  const content = APPLICATION_EXPLAIN;
  return (
    <section className="panel page-explain">
      <h2>{content.title}</h2>
      <p>{content.lead}</p>
      <h3>{content.dealTitle}</h3>
      <ol className="flow-list numbered">
        {content.dealSteps.map((step, index) => (
          <li key={index}>{step}</li>
        ))}
      </ol>
      <p className="meta">{content.book}</p>
    </section>
  );
}
