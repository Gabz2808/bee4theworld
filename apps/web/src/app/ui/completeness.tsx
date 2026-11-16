"use client";
import type { Exploration } from "../lib/api-v1";
import { useI18n } from "../i18n/provider";

// Resumen de completitud calculado solo con lo que devuelve la API (qualityFlag y coverageFraction por mes).
// No interpreta calidad ni precisión: solo cuenta meses con valor completo, parcial o ausente.
const groups = [
  { key: "ok", flags: ["ok"], className: "is-ok" },
  { key: "partial", flags: ["partial_coverage"], className: "is-partial" },
  { key: "missingValue", flags: ["missing_value"], className: "is-missing" },
  { key: "missingMonth", flags: ["missing_month"], className: "is-absent" },
] as const;

export function Completeness({ result }: { result: Exploration | null }) {
  const { t } = useI18n();
  const e = t.evidence;
  if (!result || result.points.length === 0) {
    return <section className="completeness" aria-labelledby="completeness-heading">
      <h4 id="completeness-heading">{e.completenessTitle}</h4>
      <p className="completeness-empty">{e.completenessEmpty}</p>
    </section>;
  }
  const points = result.points;
  const percent = new Intl.NumberFormat(t.numberLocale, { style: "percent", maximumFractionDigits: 1 });
  // Evita mostrar 100 % cuando la cobertura es casi completa pero no total.
  const formatCoverage = (f: number) => f < 1 && percent.format(f) === percent.format(1) ? `>${percent.format(0.999)}` : percent.format(f);
  const groupOf = (flag: string) => groups.find((g) => (g.flags as readonly string[]).includes(flag));
  const counts = groups.map((g) => ({ ...g, count: points.filter((p) => groupOf(p.qualityFlag)?.key === g.key).length }));
  const withValue = points.filter((p) => p.value !== null).length;
  const lowest = points.filter((p) => p.value !== null).reduce<(typeof points)[number] | null>((min, p) => (!min || p.coverageFraction < min.coverageFraction ? p : min), null);

  return <section className="completeness" aria-labelledby="completeness-heading">
    <h4 id="completeness-heading">{e.completenessTitle}</h4>
    <p className="completeness-summary">{e.completenessSummary(withValue, points.length)}</p>
    <ul className="completeness-legend">
      {counts.map((g) => <li key={g.key}><span className={`swatch ${g.className}`} aria-hidden="true" />{t.coverage[g.key]}<b>{g.count}</b></li>)}
    </ul>
    <div className="completeness-strip" aria-hidden="true" title={e.stripLabel}>
      {points.map((p) => <span key={p.date} className={groupOf(p.qualityFlag)?.className ?? "is-absent"} title={`${p.date.slice(0, 7)} · ${t.coverage[groupOf(p.qualityFlag)?.key ?? "unknown"]}`} />)}
    </div>
    <p className="completeness-axis" aria-hidden="true"><span>{points[0].date.slice(0, 7)}</span><span>{points.at(-1)?.date.slice(0, 7)}</span></p>
    {lowest && <p className="completeness-note">{e.lowestCoverage(formatCoverage(lowest.coverageFraction), lowest.date.slice(0, 7))}</p>}
    <p className="completeness-note">{e.completenessNote}</p>
  </section>;
}
