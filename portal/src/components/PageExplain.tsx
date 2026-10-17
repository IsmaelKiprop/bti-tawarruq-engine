import type { HowItWorksContent, PageExplainContent } from "../config/pageExplainers";

export function PageExplain({ content }: { content?: PageExplainContent }) {
  if (!content) return null;
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
      {content.note ? <p className="meta">{content.note}</p> : null}
    </section>
  );
}

export function HowItWorks({ content }: { content?: HowItWorksContent }) {
  if (!content) return null;
  return (
    <section className="panel how-it-works">
      <h2>{content.title}</h2>
      <p className="muted">{content.intro}</p>
      <ol className="flow-list numbered">
        {content.steps.map((step) => (
          <li key={step.n}>
            <strong>
              {step.n}. {step.title}.
            </strong>{" "}
            {step.body}
          </li>
        ))}
      </ol>
      {content.note ? <p className="meta">{content.note}</p> : null}
    </section>
  );
}
