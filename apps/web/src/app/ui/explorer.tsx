"use client";
import { useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { Chart } from "./chart";
import { WorldMap } from "./world-map";
import { useI18n } from "../i18n/provider";
import { MonthField } from "./month-field";
import { Completeness } from "./completeness";
import type { Dictionary } from "../i18n/dictionaries";
import { ApiClientError, completeMonths, createApiV1Client, type Catalog, type Exploration } from "../lib/api-v1";

const PrecipitationMap = dynamic(() => import("./precipitation-map"), { ssr: false, loading: () => <MapLoading /> });
function MapLoading() { return <p>{useI18n().t.explorer.loadingMap}</p>; }

const api = createApiV1Client("/api/backend");
const defaultRegionId = "costa-rica-snit-continental-v1";
// La serie SNIT reprocesada (y sus capas de mapa) cubre solo 2001-2024, aunque el catálogo anuncie más.
const snitRange = { start: "2001-01-01", end: "2024-12-31" };
function snitInterval(interval: { start: string; end: string }) {
  return { start: interval.start > snitRange.start ? interval.start : snitRange.start, end: interval.end < snitRange.end ? interval.end : snitRange.end };
}

function monthEnd(month: string) {
  const [year, number] = month.split("-").map(Number);
  return `${month}-${String(new Date(Date.UTC(year, number, 0)).getUTCDate()).padStart(2, "0")}`;
}
function formatCoverage(fraction: number) {
  if (fraction < 1 && Math.round(fraction * 100) === 100) return ">99 %";
  return `${Math.round(fraction * 100)} %`;
}
function coverageStatus(flag: string, t: Dictionary) {
  switch (flag) {
    case "ok": return t.coverage.ok;
    case "partial_coverage": return t.coverage.partial;
    case "missing_value": return t.coverage.missingValue;
    case "missing_month": return t.coverage.missingMonth;
    default: return t.coverage.unknown;
  }
}
type ErrorKey = keyof Dictionary["errors"];
function errorKey(error: unknown): ErrorKey {
  if (error instanceof ApiClientError && error.code === "NASA_AUTH_REQUIRED") return "auth";
  if (error instanceof ApiClientError && error.code === "BACKEND_TIMEOUT") return "timeout";
  if (error instanceof ApiClientError && (error.code === "RATE_LIMIT_EXCEEDED" || error.status === 429)) return "rateLimit";
  if (error instanceof ApiClientError && error.code === "SNIT_SERIES_UNAVAILABLE") return "seriesUnavailable";
  if (error instanceof ApiClientError && (error.status === 401 || error.status === 403)) return "denied";
  if (error instanceof ApiClientError && error.status === 502) return "upstream";
  if (error instanceof ApiClientError && error.kind === "invalid_response") return "invalidResponse";
  if (error instanceof ApiClientError && error.status && error.status >= 400 && error.status < 500) return "badSelection";
  return "network";
}

export function Explorer() {
  const { t, locale } = useI18n();
  const [selectedRegion, setSelectedRegion] = useState({
    id: defaultRegionId,
    name: t.regions[defaultRegionId],
  });
  const regionName = t.regions[selectedRegion.id] ?? selectedRegion.name;
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [view, setView] = useState<"series" | "map" | "world">("series");
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogError, setCatalogError] = useState<ErrorKey | "">("");
  const [reload, setReload] = useState(0);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [result, setResult] = useState<Exploration | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [message, setMessage] = useState<ErrorKey | "">("");
  const [periodError, setPeriodError] = useState<"periodOrder" | "periodRange" | "">("");
  const resultHeading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    api.catalog(controller.signal).then((data) => {
      if (controller.signal.aborted) return;
      const combination = data.combinations.find((c) => c.region_id === selectedRegion.id && c.variable_id === "precipitation" && c.is_ready_for_exploration === true);
      if (!combination) {
        if (selectedRegion.id === defaultRegionId) {
          setCatalogError("initialUnavailable");
        }
        return;
      }
      const interval = snitInterval(combination.available_interval as { start: string; end: string });
      const months = completeMonths(interval);
      if (!months) { setCatalogError("noMonths"); return; }
      const endMonth = months.end;
      setStart(endMonth);
      setEnd(endMonth);
      setCatalog(data); setCatalogError("");
    }).catch((error) => { if (!controller.signal.aborted) setCatalogError(errorKey(error)); });
    return () => controller.abort();
  }, [reload, selectedRegion.id]);

  const combination = catalog?.combinations.find((c) => c.region_id === selectedRegion.id && c.variable_id === "precipitation" && c.is_ready_for_exploration === true);
  const interval = combination ? snitInterval(combination.available_interval as { start: string; end: string }) : undefined;
  const coverage = interval ? completeMonths(interval) : null;

  function handleSelectRegionFromMap(regionId: string, regionName: string) {
    setSelectedRegion({ id: regionId, name: regionName });
    setResult(null);
    setStatus("idle");
    setPeriodError("");
  }

  async function explore(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!coverage || !start || !end || start > end || start < coverage.start.slice(0, 7) || end > coverage.end.slice(0, 7)) {
      setResult(null); setStatus("idle");
      setPeriodError(start > end ? "periodOrder" : "periodRange");
      return;
    }
    setPeriodError("");
    setStatus("loading"); setResult(null); setMessage("");
    try {
      const response = await api.explore({ region_id: selectedRegion.id, variable_id: "precipitation", start_date: `${start}-01`, end_date: monthEnd(end), temporal_resolution: "monthly" });
      const selection = response.metadata.selection as Record<string, unknown>;
      const region = catalog?.regions.find((item) => item.id === selectedRegion.id);
      if (!region || selection.geometry_sha256 !== region.geometry_sha256) throw new ApiClientError("invalid_response", "La geometría no coincide con el catálogo.");
      setSelectedIndex(0); setResult(response); setStatus("idle");
    } catch (error) { setMessage(errorKey(error)); setStatus("error"); }
    finally { resultHeading.current?.focus(); }
  }

  // Codex: mantener la incertidumbre y la procedencia junto al resultado consultado.
  const metadata = result?.metadata;
  const unitLabel = metadata?.unit === "mm/month" ? t.map.unit : String(metadata?.unit ?? "");
  const warnings = metadata ? [...metadata.limitations as string[], ...metadata.warnings as string[]] : [];
  return <main id="graficos">
    <section id="explorar" className="workspace"><div className="wrap"><div className="section-heading"><div><p className="section-label">{t.explorer.label}</p><h2>{t.explorer.title1}<br /><em>{t.explorer.title2}</em></h2></div><p>{t.explorer.body}</p></div>
      <div className="demo-notice"><strong>{t.explorer.noticeTitle}</strong><span>{t.explorer.notice}</span></div>
      <div className="explorer">
        <form className="controls" onSubmit={explore}>
          <div className="panel-heading">
            <h3>{t.explorer.configure}</h3>
            <p>{t.explorer.configureHint}</p>
          </div>

          {/* Mención en pantalla de la variable en estudio (reemplaza dropdown) */}
          <div className="variable-indicator-card">
            <div className="indicator-header">
              <span className="live-dot" />
              <span className="indicator-tag">{t.explorer.variableTag}</span>
            </div>
            <strong className="indicator-title">{t.explorer.variableTitle}</strong>
            <p className="indicator-meta">{t.explorer.variableMeta}</p>
          </div>

          {/* Territorio seleccionado mediante el mapa (reemplaza dropdown) */}
          <div className="territory-indicator-card">
            <div className="indicator-header">
              <span className="territory-icon">📍</span>
              <span className="indicator-tag">{t.explorer.territoryTag}</span>
            </div>
            <strong className="indicator-title">{regionName}</strong>
            <p className="indicator-meta">
              {selectedRegion.id === defaultRegionId
                ? t.explorer.defaultMeta
                : t.explorer.otherMeta}
            </p>
          </div>

          <MonthField id="period-start" legend={t.explorer.from} value={start} min={coverage?.start.slice(0, 7)} max={coverage?.end.slice(0, 7)} invalid={!!periodError} disabled={!coverage || status === "loading"} onChange={(value) => { setStart(value); setPeriodError(""); setResult(null); setStatus("idle"); }} />
          <MonthField id="period-end" legend={t.explorer.to} value={end} min={coverage?.start.slice(0, 7)} max={coverage?.end.slice(0, 7)} invalid={!!periodError} disabled={!coverage || status === "loading"} onChange={(value) => { setEnd(value); setPeriodError(""); setResult(null); setStatus("idle"); }} />
          {periodError && <p id="period-error" className="period-error" role="alert">{t.explorer[periodError]}</p>}
          <p className="control-note">{coverage ? t.explorer.available(coverage.start.slice(0, 7), coverage.end.slice(0, 7)) : catalogError ? t.errors[catalogError] : (selectedRegion.id !== defaultRegionId ? t.explorer.needsToken : t.explorer.checking)}</p>
          {catalogError ? <button type="button" className="button" onClick={() => { setCatalogError(""); setReload((n) => n + 1); }}>{t.explorer.retry} <span aria-hidden="true">→</span></button> : <button className="button" disabled={!coverage || status === "loading"}>{status === "loading" ? t.explorer.querying : t.explorer.query}<span aria-hidden="true">→</span></button>}
        </form>

        <div className="results" aria-busy={status === "loading"}>
          <p className="sr-only" role="status">{status === "loading" ? t.results.srLoading : message ? t.errors[message] : ""}</p>
          <div className="result-header">
            <div>
              <span className="result-kicker">{t.results.kicker}</span>
              <h3 ref={resultHeading} tabIndex={-1}>{status === "loading" ? t.results.loadingTitle : status === "error" ? t.results.errorTitle : result ? t.results.resultTitle : t.results.idleTitle}</h3>
            </div>
            {(status !== "idle" || result) && <span className="status-pill">{status === "loading" ? t.results.pillLoading : status === "error" ? t.results.pillError : t.results.pillResult}</span>}
          </div>

          {status === "loading" ? (
            <div className="empty">
              <p>{t.results.loadingBody}</p>
            </div>
          ) : status === "error" ? (
            <div className="empty">
              <p>{message ? t.errors[message] : ""}</p>
            </div>
          ) : result && metadata ? (
            <>
              <div className="result-tabs" role="tablist" aria-label={t.results.tabs}>
                <button
                  type="button"
                  role="tab"
                  id="tab-series"
                  aria-selected={view === "series"}
                  aria-controls="result-view"
                  tabIndex={view === "series" ? 0 : -1}
                  onClick={() => setView("series")}
                  onKeyDown={(event) => { if (event.key === "ArrowRight") { event.preventDefault(); setView("map"); document.getElementById("tab-map")?.focus(); } }}
                >
                  {t.results.tabSeries}
                </button>
                <button
                  type="button"
                  role="tab"
                  id="tab-map"
                  aria-selected={view === "map"}
                  aria-controls="result-view"
                  tabIndex={view === "map" ? 0 : -1}
                  onClick={() => setView("map")}
                  onKeyDown={(event) => {
                    if (event.key === "ArrowRight") { event.preventDefault(); setView("world"); document.getElementById("tab-world")?.focus(); }
                    if (event.key === "ArrowLeft") { event.preventDefault(); setView("series"); document.getElementById("tab-series")?.focus(); }
                  }}
                >
                  {t.results.tabMap}
                </button>
                <button
                  type="button"
                  role="tab"
                  id="tab-world"
                  aria-selected={view === "world"}
                  aria-controls="result-view"
                  tabIndex={view === "world" ? 0 : -1}
                  onClick={() => setView("world")}
                  onKeyDown={(event) => { if (event.key === "ArrowLeft") { event.preventDefault(); setView("map"); document.getElementById("tab-map")?.focus(); } }}
                >
                  {t.results.tabWorld}
                </button>
              </div>

              <div id="result-view" role="tabpanel" aria-labelledby={view === "series" ? "tab-series" : view === "map" ? "tab-map" : "tab-world"}>
                {view === "series" ? (
                  <>
                    <p className="chart-caption">{t.results.caption(start, end, unitLabel)}</p>
                    {result.points.every((point) => point.value === null) ? (
                      <div className="empty">
                        <h4>{t.results.noValuesTitle}</h4>
                        <p>{t.results.noValuesBody}</p>
                      </div>
                    ) : (
                      <>
                        <Chart points={result.points} selectedDate={result.points[selectedIndex]?.date}/>
                        <p className="chart-caption">{t.results.selectedMonth(result.points[selectedIndex]?.date.slice(0, 7) ?? "")}</p>
                      </>
                    )}
                  </>
                ) : view === "map" ? (
                  <PrecipitationMap key={locale} result={result} index={selectedIndex} setIndex={setSelectedIndex} />
                ) : (
                  <WorldMap selectedRegionId={selectedRegion.id} onSelectRegion={handleSelectRegionFromMap} />
                )}
              </div>

              <details className="data-table">
                <summary>{t.results.tableSummary}</summary>
                <table>
                  <thead>
                    <tr>
                      <th scope="col">{t.results.colMonth}</th>
                      <th scope="col">{t.results.colValue(unitLabel)}</th>
                      <th scope="col">{t.results.colCoverage}</th>
                      <th scope="col">{t.results.colStatus}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.points.map((point) => (
                      <tr key={point.date}>
                        <td>{point.date.slice(0, 7)}</td>
                        <td>{point.value ?? t.results.noData}</td>
                        <td>{formatCoverage(point.coverageFraction)}</td>
                        <td>{coverageStatus(point.qualityFlag, t)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </details>

              <div className="result-note">
                <strong>{t.results.pendingTitle}</strong>
                <p>{t.results.pendingBody}</p>
              </div>

              <section className="result-note trend-status" aria-labelledby="trend-heading">
                <h4 id="trend-heading">{t.results.trendHeading}</h4>
                <p><strong>{result.analysisStatus === "inconclusive" ? t.results.inconclusive : result.analysisStatus === "not_computed" ? t.results.notComputed : t.results.underReview}</strong></p>
                <p>{result.analysisStatus === "conclusive" ? t.results.conclusiveNote : <span lang="es">{result.analysisNote}</span>}</p>
                <p>{t.results.method(result.analysisMethod)}</p>
                <p><strong>{t.results.uncertaintyLabel}</strong> {t.results.uncertainty}</p>
                <p>{t.results.causality}</p>
              </section>

              <div className="result-note">
                <strong>{t.results.serviceTitle}</strong>
                <p>{t.results.service(String(metadata.dataset), String(metadata.source), String(metadata.spatial_resolution))}</p>
                {warnings.length > 0 && <>{t.results.serviceLanguage && <p>{t.results.serviceLanguage}</p>}<ul lang="es">{warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul></>}
              </div>
            </>
          ) : (
            <div className="world-initial-view">
              <WorldMap selectedRegionId={selectedRegion.id} onSelectRegion={handleSelectRegionFromMap} />
            </div>
          )}
        </div>
      </div>

      <div className="evidence">
        <div className="evidence-intro">
          <h3>{t.evidence.title1}<br />{t.evidence.title2}</h3>
          <p>{t.evidence.body}</p>
        </div>
        <Completeness result={result} />
        <div className="evidence-list">
          {result && metadata ? (
            <>
              <span>{t.evidence.product} <b>{String(metadata.dataset)}</b></span>
              <span>{t.evidence.source} <b>{String(metadata.source)}</b></span>
              {typeof metadata.effective_origin === "string" && metadata.effective_origin.trim() && <span>{t.evidence.origin} <b>{metadata.effective_origin}</b></span>}
              {typeof metadata.product_version === "string" && metadata.product_version.trim() && <span>{t.evidence.version} <b>{metadata.product_version}</b></span>}
              {typeof metadata.unit_conversion === "string" && metadata.unit_conversion.trim() && <span>{t.evidence.conversion} <b>{metadata.unit_conversion}</b></span>}
              <span>{t.evidence.resolution} <b>{String(metadata.spatial_resolution)}</b></span>
              {result.evidence.weighting && <span>{t.evidence.weighting} <b>{result.evidence.weighting}</b></span>}
              {result.evidence.doi && <span>{t.evidence.reference} <b><a href={result.evidence.doi}>{t.evidence.referenceLink} ↗</a></b></span>}
              {result.evidence.granules.length > 0 && (
                <details>
                  <summary>{t.evidence.granules(result.evidence.granules.length)}</summary>
                  <ul>{result.evidence.granules.map((id, index) => <li key={index}>{id}</li>)}</ul>
                </details>
              )}
              <span>{t.evidence.validation} <b>{t.evidence.validationStatus}</b></span>
            </>
          ) : (
            <p>{t.evidence.empty}</p>
          )}
        </div>
      </div>
    </div>
  </section>
  </main>;
}
