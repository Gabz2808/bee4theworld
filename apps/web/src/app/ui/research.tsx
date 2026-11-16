"use client";
import Link from "next/link";
import { useI18n } from "../i18n/provider";
const stepIcons = ["origin", "area", "calculation", "review"];

function StepIcon({ type }: { type: string }) {
  return <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {type === "origin" && <><circle cx="12" cy="12" r="8"/><path d="M4 12h16M12 4c2.5 2.2 3.5 5 3.5 8s-1 5.8-3.5 8c-2.5-2.2-3.5-5-3.5-8S9.5 6.2 12 4Z"/></>}
    {type === "area" && <><path d="m4 7 5-3 6 3 5-3v13l-5 3-6-3-5 3V7ZM9 4v13M15 7v13"/></>}
    {type === "calculation" && <><path d="M4 19h16M6 16v-4M12 16V5M18 16V9"/><circle cx="6" cy="10" r="1"/><circle cx="12" cy="3" r="1"/><circle cx="18" cy="7" r="1"/></>}
    {type === "review" && <><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.5 15.5 4 4M8 10.5l1.7 1.7 3.3-3.4"/></>}
  </svg>;
}

export function Research() {
  const { t } = useI18n();
  const r = t.research;
  return <section id="investigacion" className="research" aria-labelledby="research-heading">
    <div className="wrap">
      <header className="research-intro">
        <span className="research-badge"><span aria-hidden="true" />{r.badge}</span>
        <h2 id="research-heading">{r.heading}</h2>
        <p>{r.intro}</p>
      </header>

      <div className="method-flow" aria-label={r.flow}>
        <ol>{r.steps.map((step, index) => <li key={stepIcons[index]}>
          <div className="method-step-top"><span className="method-icon"><StepIcon type={stepIcons[index]} /></span><span className="method-number">0{index + 1}</span></div>
          <span className="method-label">{step.label}</span><h3>{step.title}</h3><p>{step.detail}</p>
        </li>)}</ol>
      </div>

      <section className="research-panel trend-research" aria-labelledby="research-trend-heading">
        <h3 id="research-trend-heading"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M12 3 2.5 20h19L12 3Z"/><path d="M12 9v4.5M12 17h.01"/></svg>{r.trendHeading}</h3>
        <p><strong>{r.trendLead}</strong> {r.trend1}</p>
        <p>{r.trend2}</p>
        <p>{r.trend3}</p>
        <Link href="/explorar">{r.trendLink}</Link>
      </section>

      <div className="research-grid">
        <section className="research-panel technical-panel" aria-labelledby="technical-heading">
          <h3 id="technical-heading">{r.technicalHeading}</h3>
          <div className="research-metrics">
            <div><strong>288 <small>{r.months}</small></strong><p>{r.monthsDetail}</p></div>
            <div><strong>{r.coverageValue} <small>%</small></strong><p>{r.coverageDetail}</p></div>
          </div>
          <p className="research-warning"><strong>{r.scopeLead}</strong> {r.scope}</p>
        </section>
        <section className="research-panel publication-panel" aria-labelledby="publication-heading">
          <h3 id="publication-heading">{r.publicationHeading}</h3>
          <ul className="publication-list">
            <li><span className="publication-status available">{r.available}</span><p>{r.pubAvailable}</p></li>
            <li><span className="publication-status review">{r.review}</span><p>{r.pubReview}</p></li>
            <li><span className="publication-status pending">{r.pending}</span><p>{r.pubPending}</p></li>
          </ul>
        </section>
      </div>

      <section className="interval-panel" aria-labelledby="interval-heading">
        <div><h3 id="interval-heading">{r.intervalHeading}</h3><p>{r.intervalSub}</p></div>
        <div className="interval-content"><div className="interval-bar" aria-label={r.intervalAria}><span>&lt; 3</span><span>{r.intervalMid}</span><span>≥ 10</span></div>
          <p><strong>{r.noteLead}</strong> {r.note1} <strong>{r.noteStrong}</strong> {r.note2}</p></div>
      </section>

      <nav className="research-links" aria-label={r.links}>
        <a href="https://gpm.nasa.gov/resources/documents/imerg-v07-technical-documentation">{r.linkDocs} <span aria-hidden="true">↗</span></a>
        <a href="https://doi.org/10.5067/GPM/IMERG/3B-MONTH/07">{r.linkProduct} <span aria-hidden="true">↗</span></a>
        <a href="https://gpm.nasa.gov/sites/default/files/2023-07/IMERG_V07_ATBD_final_230712.pdf">{r.linkMethod} <span aria-hidden="true">↗</span></a>
      </nav>
    </div>
  </section>;
}
