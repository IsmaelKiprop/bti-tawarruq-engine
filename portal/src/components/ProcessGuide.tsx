import { useState, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";
import {
  ACTORS,
  ACTOR_ORDER,
  ActorId,
  FlowStep,
  PageGuideContent,
  ProcessTrack,
  RESPONSIBILITY_SPLIT,
  getPageGuide,
} from "../config/processModel";

const GUIDE_STORAGE_KEY = "bti.portal.guides.collapsed";

function readCollapsed(): Record<string, boolean> {
  try {
    const raw = localStorage.getItem(GUIDE_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as Record<string, boolean>) : {};
  } catch {
    return {};
  }
}

function writeCollapsed(next: Record<string, boolean>) {
  try {
    localStorage.setItem(GUIDE_STORAGE_KEY, JSON.stringify(next));
  } catch {
    /* storage unavailable, collapse state is cosmetic */
  }
}

export function ActorChip({ actor, owner }: { actor: ActorId; owner?: boolean }) {
  const meta = ACTORS[actor];
  return (
    <span
      className={`actor-chip actor-${actor}${owner ? " is-owner" : ""}`}
      title={`${meta.name} — ${meta.role}`}
    >
      <span className="actor-dot" />
      {meta.short}
    </span>
  );
}

export function ActorChips({ actors }: { actors: ActorId[] }) {
  return (
    <span className="actor-chips">
      {actors.map((actor, index) => (
        <ActorChip key={actor} actor={actor} owner={index === 0} />
      ))}
    </span>
  );
}

export function ActorLegend() {
  return (
    <ul className="actor-legend">
      {ACTOR_ORDER.map((id) => {
        const actor = ACTORS[id];
        return (
          <li key={id}>
            <div className="actor-legend-head">
              <ActorChip actor={id} owner />
              <span className="actor-legend-name">{actor.name}</span>
              <span className={`actor-kind kind-${actor.kind}`}>{actor.kind}</span>
            </div>
            <p>{actor.role}</p>
          </li>
        );
      })}
    </ul>
  );
}

const MODE_LABEL: Record<FlowStep["mode"], string> = {
  manual: "Ops action",
  automated: "Engine / Amanah",
  external: "Waiting on partner",
};

export function TrackFlow({ track, compact }: { track: ProcessTrack; compact?: boolean }) {
  return (
    <div className={`track-flow${compact ? " compact" : ""}`}>
      {track.phases.map((phase) => (
        <section className="track-phase" key={phase.id}>
          <header className="track-phase-head">
            <h4>{phase.title}</h4>
            <p>{phase.summary}</p>
          </header>
          <ol className="track-steps">
            {phase.steps.map((step) => (
              <li className="track-step" key={step.step}>
                <span className="track-step-num">{step.step}</span>
                <div className="track-step-body">
                  <div className="track-step-title">
                    <strong>{step.title}</strong>
                    <ActorChips actors={step.actors} />
                    <span className={`mode-tag mode-${step.mode}`}>{MODE_LABEL[step.mode]}</span>
                  </div>
                  <p>{step.detail}</p>
                  {step.route && !compact ? (
                    <Link className="track-step-link" to={step.route}>
                      Done in {step.routeLabel ?? step.route}
                    </Link>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}

/**
 * Inline explainer placed directly above a form or action list so the operator
 * knows which party is acting before they click.
 */
export function StepCallout({
  stepLabel,
  title,
  actors,
  mode,
}: {
  stepLabel?: string;
  title: string;
  actors: ActorId[];
  mode?: FlowStep["mode"];
  children?: ReactNode;
}) {
  // Children (long process copy) are ignored — desk docs live under Documentation.
  return (
    <div className="step-callout">
      <div className="step-callout-head">
        {stepLabel ? <span className="track-step-num">{stepLabel}</span> : null}
        <strong>{title}</strong>
        <ActorChips actors={actors} />
        {mode ? <span className={`mode-tag mode-${mode}`}>{MODE_LABEL[mode]}</span> : null}
      </div>
    </div>
  );
}

export function ResponsibilityMatrix() {
  return (
    <div className="responsibility-grid">
      {RESPONSIBILITY_SPLIT.map((entry) => (
        <article className="responsibility-card" key={entry.actor}>
          <header>
            <ActorChip actor={entry.actor} owner />
            <strong>{ACTORS[entry.actor].name}</strong>
          </header>
          <ul>
            {entry.owns.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
          <p className="responsibility-never">{entry.neverDoes}</p>
        </article>
      ))}
    </div>
  );
}

/**
 * Explains the current page: which phase it belongs to, who acts, and where the
 * work goes next. Collapse state is remembered per route.
 */
export function PageGuide() {
  const location = useLocation();
  const guide = getPageGuide(location.pathname);
  if (!guide) return null;
  // Keyed so each route re-reads its own collapse preference on navigation.
  return <GuidePanel key={location.pathname} routeKey={location.pathname} guide={guide} />;
}

function GuidePanel({ routeKey: key, guide }: { routeKey: string; guide: PageGuideContent }) {
  const [collapsed, setCollapsed] = useState(() => Boolean(readCollapsed()[key]));

  function toggle() {
    const next = { ...readCollapsed(), [key]: !collapsed };
    writeCollapsed(next);
    setCollapsed(!collapsed);
  }

  return (
    <section className={`page-guide${collapsed ? " is-collapsed" : ""}`}>
      <div className="page-guide-top">
        <div className="page-guide-heading">
          <span className="page-guide-stage">{guide.stage}</span>
          <p className="page-guide-summary">{guide.summary}</p>
          <ActorChips actors={guide.actors} />
        </div>
        <button type="button" className="btn btn-secondary btn-sm" onClick={toggle}>
          {collapsed ? "Show guide" : "Hide guide"}
        </button>
      </div>

      {!collapsed ? (
        <>
          <div className="page-guide-columns">
            <div className="page-guide-col">
              <h4>You do here</h4>
              <ul>
                {guide.youDo.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
            <div className="page-guide-col">
              <h4>The engine does</h4>
              <ul>
                {guide.engineDoes.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          </div>

          {guide.watchOut?.length ? (
            <ul className="page-guide-watch">
              {guide.watchOut.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}

          {guide.comesFrom || guide.goesTo ? (
            <div className="page-guide-nav">
              {guide.comesFrom ? (
                <span>
                  Comes from{" "}
                  <Link to={guide.comesFrom.to}>{guide.comesFrom.label}</Link>
                </span>
              ) : null}
              {guide.goesTo ? (
                <span>
                  Next step <Link to={guide.goesTo.to}>{guide.goesTo.label}</Link>
                </span>
              ) : null}
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}
