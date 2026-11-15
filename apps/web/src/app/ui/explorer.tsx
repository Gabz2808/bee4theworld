"use client";
import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import dynamic from "next/dynamic";
import { Chart } from "./chart";
import { Research } from "./research";
import { ApiClientError, completeMonths, createApiV1Client, type Catalog, type Exploration } from "../lib/api-v1";

const PrecipitationMap = dynamic(() => import("./precipitation-map"), { ssr: false, loading: () => <p>Cargando mapa...</p> });

const api = createApiV1Client("/api/backend");
const regionId = "costa-rica-snit-continental-v1";

function monthEnd(month: string) {
  const [year, number] = month.split("-").map(Number);
  return `${month}-${String(new Date(Date.UTC(year, number, 0)).getUTCDate()).padStart(2, "0")}`;
}
function formatCoverage(fraction: number) {
  if (fraction < 1 && Math.round(fraction * 100) === 100) return ">99 %";
  return `${Math.round(fraction * 100)} %`;
}
function coverageStatus(flag: string) {
  switch (flag) {
    case "ok": return "Completa";
    case "partial_coverage": return "Parcial";
    case "missing_value": return "Sin valor";
    case "missing_month": return "Mes ausente";
    default: return "No disponible";
  }
}
function errorMessage(error: unknown) {
  if (error instanceof ApiClientError && error.code === "NASA_AUTH_REQUIRED") return "El servicio necesita configurar el acceso a NASA Earthdata. Solicita al equipo que configure la autenticación y vuelve a intentarlo.";
  if (error instanceof ApiClientError && error.code === "BACKEND_TIMEOUT") return "La consulta tardó demasiado y podría seguir procesándose. Espera antes de reintentar para evitar consultas duplicadas, o elige un período más corto.";
  if (error instanceof ApiClientError && (error.code === "RATE_LIMIT_EXCEEDED" || error.status === 429)) return "Se alcanzó el límite de consultas. Espera un momento y vuelve a intentarlo.";
  if (error instanceof ApiClientError && error.code === "SNIT_SERIES_UNAVAILABLE") return "La serie no está disponible o no pasó la comprobación de integridad. Solicita al equipo que revise los archivos y vuelve a intentarlo.";
  if (error instanceof ApiClientError && (error.status === 401 || error.status === 403)) return "El servicio rechazó el acceso. Solicita al equipo que revise la configuración.";
  if (error instanceof ApiClientError && error.status === 502) return "El servicio de datos no pudo completar la consulta. Vuelve a intentarlo más tarde.";
  if (error instanceof ApiClientError && error.kind === "invalid_response") return "La respuesta no tiene el formato esperado. Vuelve a intentarlo más tarde.";
  if (error instanceof ApiClientError && error.status && error.status >= 400 && error.status < 500) return "La selección no está disponible. Revisa el período e inténtalo de nuevo.";
  return "No fue posible conectar con el servicio. Comprueba que la API esté disponible e inténtalo de nuevo.";
}

export function Explorer() {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [view, setView] = useState<"series" | "map">("series");
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogError, setCatalogError] = useState("");
  const [reload, setReload] = useState(0);
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [result, setResult] = useState<Exploration | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [message, setMessage] = useState("");
  const [periodError, setPeriodError] = useState("");
  const resultHeading = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const controller = new AbortController();
    api.catalog(controller.signal).then((data) => {
      if (controller.signal.aborted) return;
      const combination = data.combinations.find((c) => c.region_id === regionId && c.variable_id === "precipitation" && c.is_ready_for_exploration === true);
      if (!combination) { setCatalogError("La serie inicial no está disponible. Solicita al equipo que revise los archivos o reintenta la conexión."); return; }
      const interval = combination.available_interval as { start: string; end: string };
      const months = completeMonths(interval);
      if (!months) { setCatalogError("El servicio no indica meses completos disponibles. Vuelve a intentarlo más tarde."); return; }
      const endMonth = months.end;
      setStart(endMonth);
      setEnd(endMonth);
      setCatalog(data); setCatalogError("");
    }).catch((error) => { if (!controller.signal.aborted) setCatalogError(errorMessage(error)); });
    return () => controller.abort();
  }, [reload]);

  const combination = catalog?.combinations.find((c) => c.region_id === regionId && c.variable_id === "precipitation" && c.is_ready_for_exploration === true);
  const interval = combination?.available_interval as { start: string; end: string } | undefined;
  const coverage = interval ? completeMonths(interval) : null;

  async function explore(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!coverage || !start || !end || start > end || start < coverage.start.slice(0, 7) || end > coverage.end.slice(0, 7)) {
      setResult(null); setStatus("idle");
      setPeriodError(start > end ? "La fecha inicial debe ser anterior o igual a la fecha final. Cambia una de las dos fechas." : "Elige meses dentro del período indicado por el servicio.");
      return;
    }
    setPeriodError("");
    setStatus("loading"); setResult(null); setMessage("");
    try {
      const response = await api.explore({ region_id: regionId, variable_id: "precipitation", start_date: `${start}-01`, end_date: monthEnd(end), temporal_resolution: "monthly" });
      const selection = response.metadata.selection as Record<string, unknown>;
      const region = catalog?.regions.find((item) => item.id === regionId);
      if (!region || selection.geometry_sha256 !== region.geometry_sha256) throw new ApiClientError("invalid_response", "La geometría no coincide con el catálogo.");
      setSelectedIndex(0); setResult(response); setStatus("idle");
    } catch (error) { setMessage(errorMessage(error)); setStatus("error"); }
    finally { resultHeading.current?.focus(); }
  }

  // Codex: mantener la incertidumbre y la procedencia junto al resultado consultado.
  const metadata = result?.metadata;
  const warnings = metadata ? [...metadata.limitations as string[], ...metadata.warnings as string[]] : [];
  return <>
    <a className="skip-link" href="#explorar">Saltar al explorador</a>
    <header className="topbar"><a className="brand" href="#inicio" aria-label="Iyök, inicio"><span className="brand-symbol iyok-symbol" aria-hidden="true"><Image src="/iyok-logo.jpg" alt="" width={160} height={100} priority /></span><span>Iyök</span></a><nav aria-label="Navegación principal"><a href="#explorar">Explorar</a><a href="#investigacion">Investigación</a><a href="#acerca">Sobre Iyök</a></nav><a className="header-team" href="https://github.com/Gabz2808/bee4theworld" target="_blank" rel="noopener noreferrer" aria-label="Repositorio de Bee4TheWorld en GitHub (abre en una pestaña nueva)"><span className="brand-symbol team-symbol" aria-hidden="true"><Image src="/bee4theworld-logo.jpg" alt="" width={100} height={75} priority /></span><span><small>Un proyecto de</small><strong>Bee4TheWorld</strong></span></a></header>
    <main id="inicio"><section className="intro wrap"><div className="intro-copy"><div className="location"><span className="location-dot" /> COSTA RICA · PUNTO DE PARTIDA</div><h1>Entender la Tierra<br /><em>empieza por mirar.</em></h1><p>Explora cómo cambia nuestro territorio a través del tiempo, con datos y evidencia que cuentan la historia completa.</p><a className="primary-link" href="#explorar">Comenzar a explorar <span aria-hidden="true">↗</span></a></div><div className="intro-side"><div className="orbit orbit-one"/><div className="orbit orbit-two"/><div className="earth"><span>CR</span></div><div className="intro-caption"><span>UN PLANETA EN CAMBIO</span><strong>Una mirada más cercana<br />a nuestro territorio.</strong></div></div></section>
    <section id="explorar" className="workspace"><div className="wrap"><div className="section-heading"><div><p className="section-label">EL EXPLORADOR</p><h2>Haz una pregunta.<br /><em>Encuentra contexto.</em></h2></div><p>Un espacio para observar series, entender sus límites y seguir la evidencia detrás de cada resultado.</p></div>
      <div className="demo-notice"><strong>MVP · serie en revisión</strong><span>Este producto está en desarrollo. La serie cubre el componente terrestre principal de IGN/SNIT y excluye componentes separados. Su calidad, el método y la interpretación científica siguen en revisión.</span></div>
      <div className="explorer"><form className="controls" onSubmit={explore}><div className="panel-heading"><h3>Configura tu exploración</h3><p>Consulta la primera serie disponible del servicio.</p></div>
        <label>Territorio<select value="Costa Rica continental" disabled><option>Costa Rica continental</option></select></label>
        <label>Variable<select value="Precipitación mensual" disabled><option>Precipitación mensual</option></select></label>
        <label htmlFor="period-start">Desde<input id="period-start" type="month" value={start} min={coverage?.start.slice(0, 7)} max={coverage?.end.slice(0, 7)} aria-invalid={!!periodError} aria-describedby={periodError ? "period-error" : undefined} onChange={(e) => { setStart(e.target.value); setPeriodError(""); setResult(null); setStatus("idle"); }} disabled={!coverage || status === "loading"} required /></label>
        <label htmlFor="period-end">Hasta<input id="period-end" type="month" value={end} min={coverage?.start.slice(0, 7)} max={coverage?.end.slice(0, 7)} aria-invalid={!!periodError} aria-describedby={periodError ? "period-error" : undefined} onChange={(e) => { setEnd(e.target.value); setPeriodError(""); setResult(null); setStatus("idle"); }} disabled={!coverage || status === "loading"} required /></label>
        {periodError && <p id="period-error" className="period-error" role="alert">{periodError}</p>}
        <p className="control-note">{coverage ? `Período indicado por el servicio: ${coverage.start.slice(0, 7)} a ${coverage.end.slice(0, 7)}. Frontera continental IGN/SNIT; componentes separados excluidos.` : catalogError || "Consultando disponibilidad del servicio…"}</p>
        {catalogError ? <button type="button" className="button" onClick={() => { setCatalogError(""); setReload((n) => n + 1); }}>Reintentar conexión <span aria-hidden="true">→</span></button> : <button className="button" disabled={!coverage || status === "loading"}>{status === "loading" ? "Consultando…" : "Consultar serie"}<span aria-hidden="true">→</span></button>}
      </form>
      <div className="results" aria-busy={status === "loading"}><p className="sr-only" role="status">{status === "loading" ? "Consultando serie" : message}</p><div className="result-header"><div><span className="result-kicker">SERIE TEMPORAL</span><h3 ref={resultHeading} tabIndex={-1}>{status === "loading" ? "Consultando la serie" : status === "error" ? "No se pudo obtener la serie" : result ? "Precipitación mensual" : "Aquí comienza la exploración"}</h3></div><span className="status-pill">{status === "loading" ? "EN CURSO" : status === "error" ? "ERROR" : result ? "SIN VALIDAR" : "A LA ESPERA DE DATOS"}</span></div>
        {status === "loading" ? <div className="empty"><p>Estamos consultando el servicio. Esto puede tardar unos minutos.</p></div> : status === "error" ? <div className="empty"><p>{message}</p></div> : result && metadata ? <><div className="result-tabs" role="tablist" aria-label="Vista del resultado"><button type="button" role="tab" id="tab-series" aria-selected={view === "series"} aria-controls="result-view" tabIndex={view === "series" ? 0 : -1} onClick={() => setView("series")} onKeyDown={(event) => { if (event.key === "ArrowRight" || event.key === "ArrowLeft") { event.preventDefault(); setView("map"); document.getElementById("tab-map")?.focus(); } }}>Serie temporal</button><button type="button" role="tab" id="tab-map" aria-selected={view === "map"} aria-controls="result-view" tabIndex={view === "map" ? 0 : -1} onClick={() => setView("map")} onKeyDown={(event) => { if (event.key === "ArrowRight" || event.key === "ArrowLeft") { event.preventDefault(); setView("series"); document.getElementById("tab-series")?.focus(); } }}>Mapa</button></div><div id="result-view" role="tabpanel" aria-labelledby={view === "series" ? "tab-series" : "tab-map"}>{view === "series" ? <><p className="chart-caption">Período solicitado: {start} a {end} · {String(metadata.unit)} · los espacios indican valores ausentes</p>{result.points.every((point) => point.value === null) ? <div className="empty"><h4>No hay valores para este período.</h4><p>Prueba otro período y consulta la cobertura en la tabla.</p></div> : <><Chart points={result.points} selectedDate={result.points[selectedIndex]?.date}/><p className="chart-caption">Mes seleccionado en el mapa: {result.points[selectedIndex]?.date.slice(0, 7)}.</p></>}</> : <PrecipitationMap result={result} index={selectedIndex} setIndex={setSelectedIndex} />}</div><details className="data-table"><summary>Ver valores y cobertura en una tabla</summary><table><thead><tr><th scope="col">Mes</th><th scope="col">Valor ({String(metadata.unit)})</th><th scope="col">Cobertura</th><th scope="col">Estado de cobertura</th></tr></thead><tbody>{result.points.map((point) => <tr key={point.date}><td>{point.date.slice(0, 7)}</td><td>{point.value ?? "Sin dato"}</td><td>{formatCoverage(point.coverageFraction)}</td><td>{coverageStatus(point.qualityFlag)}</td></tr>)}</tbody></table></details><div className="result-note"><strong>Serie pendiente de validación</strong><p>La serie fue aceptada para este MVP. Su procedencia, calidad y procesamiento siguen en revisión científica.</p></div><section className="result-note trend-status" aria-labelledby="trend-heading"><h4 id="trend-heading">Estado del análisis de tendencia</h4><p><strong>{result.analysisStatus === "inconclusive" ? "Inconcluso" : result.analysisStatus === "not_computed" ? "No calculado" : "Resultado en revisión"}</strong></p><p>{result.analysisStatus === "conclusive" ? "El servicio reportó un resultado, pero la inferencia permanece en revisión científica y no se publican métricas." : result.analysisNote}</p><p>Método declarado: {result.analysisMethod}. La revisión del método y sus supuestos sigue pendiente.</p><p><strong>Incertidumbre:</strong> no se dispone de un intervalo de confianza revisado para la pendiente. La cobertura de la serie no cuantifica esa incertidumbre.</p><p>Los cambios observados en esta serie no demuestran por sí solos su causa.</p></section><div className="result-note"><strong>Información reportada por el servicio</strong><p>Producto: {String(metadata.dataset)}. Fuente declarada: {String(metadata.source)}. Resolución: {String(metadata.spatial_resolution)}. La cobertura indica el área con datos disponibles; no mide la precisión de la estimación. El índice de calidad de NASA aún no se muestra.</p>{warnings.length > 0 && <ul>{warnings.map((warning, i) => <li key={i}>{warning}</li>)}</ul>}</div></> : <div className="empty"><div className="empty-graphic" aria-hidden="true"><span/><span/><span/><span/><span/></div><h4>Elige un período para comenzar.</h4><p>Consulta la serie disponible y revisa su contexto y sus limitaciones.</p></div>}
      </div></div><div className="evidence"><div><h3>La evidencia<br />siempre a la vista.</h3></div><p>Las cifras necesitan contexto. La procedencia y el método de la serie se están revisando con el equipo.</p><div className="evidence-list">{result && metadata ? <><span>Producto <b>{String(metadata.dataset)}</b></span><span>Fuente declarada <b>{String(metadata.source)}</b></span>{typeof metadata.effective_origin === "string" && metadata.effective_origin.trim() && <span>Origen reportado <b>{metadata.effective_origin}</b></span>}{typeof metadata.product_version === "string" && metadata.product_version.trim() && <span>Versión del producto <b>{metadata.product_version}</b></span>}{typeof metadata.unit_conversion === "string" && metadata.unit_conversion.trim() && <span>Conversión de unidades <b>{metadata.unit_conversion}</b></span>}<span>Resolución <b>{String(metadata.spatial_resolution)}</b></span>{result.evidence.weighting && <span>Método de ponderación <b>{result.evidence.weighting}</b></span>}{result.evidence.doi && <span>Referencia <b><a href={result.evidence.doi}>Consultar fuente ↗</a></b></span>}{result.evidence.granules.length > 0 && <details><summary>Ver gránulos reportados ({result.evidence.granules.length})</summary><ul>{result.evidence.granules.map((id, index) => <li key={index}>{id}</li>)}</ul></details>}<span>Validación científica <b>En revisión</b></span></> : <p>Consulta una serie para ver la procedencia y las limitaciones reportadas por el servicio.</p>}</div></div>
    </div></section><Research /></main><footer id="acerca"><div className="wrap footer-inner"><div><a className="footer-brand" href="#inicio">iyök<span>.</span></a><p>Una forma más clara de explorar<br />el cambio en nuestro planeta.</p></div><div><strong>HECHO PARA EXPLORAR</strong><p>Un proyecto en desarrollo de Bee4TheWorld.<br />Integración y análisis en revisión.</p></div><a href="#inicio">Volver arriba ↑</a></div></footer>
  </>;
}
