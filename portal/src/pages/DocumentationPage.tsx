import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { PageShell } from "../components/PageShell";
import {
  APPROVAL_LIMIT_DASHBOARD,
  APPROVAL_LIMIT_FIELD,
  HOW_IT_WORKS,
  INSTITUTION_LIMIT_FIELD,
  MAKER_CHECKER_STEPS_FIELD,
  PAGE_EXPLAINS,
} from "../config/pageExplainers";
import { ROUTE_META } from "../config/navigation";

const TOPIC_ORDER = Object.keys(PAGE_EXPLAINS);

export function DocumentationPage() {
  const [query, setQuery] = useState("");
  const [openId, setOpenId] = useState<string>(TOPIC_ORDER[0] || "/");

  const topics = useMemo(() => {
    const q = query.trim().toLowerCase();
    return TOPIC_ORDER.filter((path) => {
      if (!q) return true;
      const explain = PAGE_EXPLAINS[path];
      const how = HOW_IT_WORKS[path];
      const hay = [
        path,
        ROUTE_META[path]?.title,
        explain?.title,
        explain?.lead,
        ...(explain?.dealSteps || []),
        how?.title,
        how?.intro,
        ...(how?.steps.flatMap((s) => [s.title, s.body]) || []),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return hay.includes(q);
    });
  }, [query]);

  return (
    <PageShell wide>
      <section className="panel">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="m-0">Documentation</h2>
            <p className="muted m-0 mt-1">
              Desk explainers and process notes moved off the live dashboard. Open a topic for how each page fits a deal.
            </p>
          </div>
          <label className="flex min-w-[14rem] flex-col gap-1 text-xs uppercase tracking-wide text-muted">
            Search
            <input
              className="rounded-sm border border-border bg-surface-elevated px-2.5 py-1.5 text-sm normal-case tracking-normal text-foreground"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Kenya, approvals, Sedania…"
            />
          </label>
        </div>
      </section>

      <section className="panel">
        <h3 className="mt-0">Controls & limits</h3>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <article className="rounded-sm border border-border/80 bg-surface-elevated p-3">
            <h4 className="m-0 text-sm font-semibold">Approval limit</h4>
            <p className="mb-0 mt-1.5 text-sm text-muted">{APPROVAL_LIMIT_DASHBOARD}</p>
          </article>
          <article className="rounded-sm border border-border/80 bg-surface-elevated p-3">
            <h4 className="m-0 text-sm font-semibold">User invite field</h4>
            <p className="mb-0 mt-1.5 text-sm text-muted">{APPROVAL_LIMIT_FIELD}</p>
          </article>
          <article className="rounded-sm border border-border/80 bg-surface-elevated p-3">
            <h4 className="m-0 text-sm font-semibold">Institution cap</h4>
            <p className="mb-0 mt-1.5 text-sm text-muted">{INSTITUTION_LIMIT_FIELD}</p>
          </article>
          <article className="rounded-sm border border-border/80 bg-surface-elevated p-3">
            <h4 className="m-0 text-sm font-semibold">Maker-checker steps</h4>
            <p className="mb-0 mt-1.5 text-sm text-muted">{MAKER_CHECKER_STEPS_FIELD}</p>
          </article>
        </div>
      </section>

      <section className="flex flex-col gap-2">
        {topics.length === 0 ? (
          <div className="panel">
            <p className="muted">No topics match “{query}”.</p>
          </div>
        ) : (
          topics.map((path) => {
            const explain = PAGE_EXPLAINS[path];
            const how = HOW_IT_WORKS[path];
            const title = ROUTE_META[path]?.title || explain?.title || path;
            const open = openId === path;
            return (
              <article
                key={path}
                className={`panel overflow-hidden p-0${open ? " border-primary/40" : ""}`}
              >
                <button
                  type="button"
                  className="flex w-full items-center justify-between gap-3 bg-transparent px-4 py-3 text-left"
                  onClick={() => setOpenId(open ? "" : path)}
                  aria-expanded={open}
                >
                  <span className="flex min-w-0 flex-col gap-0.5">
                    <strong className="text-sm font-semibold text-foreground">{title}</strong>
                    <small className="font-mono text-xs text-muted">{path}</small>
                  </span>
                  <span className="shrink-0 text-lg leading-none text-muted" aria-hidden>
                    {open ? "−" : "+"}
                  </span>
                </button>
                {open ? (
                  <div className="border-t border-border px-4 pb-4 pt-3">
                    {explain ? (
                      <div className="mb-4">
                        <h4 className="m-0 text-sm font-semibold">{explain.title}</h4>
                        <p className="mt-1.5 text-sm text-muted">{explain.lead}</p>
                        <h5 className="mb-1 mt-3 text-xs font-semibold uppercase tracking-wide text-foreground">
                          {explain.dealTitle}
                        </h5>
                        <ol className="m-0 list-decimal space-y-1 pl-4 text-sm text-muted">
                          {explain.dealSteps.map((step) => (
                            <li key={step}>{step}</li>
                          ))}
                        </ol>
                        {explain.note ? (
                          <p className="mt-2 rounded-sm border border-border/70 bg-surface-elevated px-2.5 py-2 text-sm text-muted">
                            {explain.note}
                          </p>
                        ) : null}
                      </div>
                    ) : null}
                    {how ? (
                      <div className="mb-4">
                        <h4 className="m-0 text-sm font-semibold">{how.title}</h4>
                        <p className="mt-1.5 text-sm text-muted">{how.intro}</p>
                        <ol className="m-0 mt-2 list-decimal space-y-1.5 pl-4 text-sm text-muted">
                          {how.steps.map((step) => (
                            <li key={step.n}>
                              <strong className="text-foreground">{step.title}.</strong> {step.body}
                            </li>
                          ))}
                        </ol>
                        {how.note ? (
                          <p className="mt-2 rounded-sm border border-border/70 bg-surface-elevated px-2.5 py-2 text-sm text-muted">
                            {how.note}
                          </p>
                        ) : null}
                      </div>
                    ) : null}
                    {path !== "/" ? (
                      <Link className="btn btn-secondary btn-sm" to={path}>
                        Open page
                      </Link>
                    ) : (
                      <Link className="btn btn-secondary btn-sm" to="/">
                        Open dashboard
                      </Link>
                    )}
                  </div>
                ) : null}
              </article>
            );
          })
        )}
      </section>
    </PageShell>
  );
}
