import { test } from "node:test";
import { deepStrictEqual, equal, rejects, throws } from "node:assert/strict";
import { readFileSync } from "node:fs";
import { ApiClientError, completeMonths, createApiV1Client, parseCatalog, parseExploration } from "./api-v1.ts";

// Datos sintéticos: no representan observaciones ni resultados científicos.
const request = { region_id: "costa-rica-continental", variable_id: "precipitation", start_date: "2023-01-01", end_date: "2023-02-28", temporal_resolution: "monthly" };
const range = { start: request.start_date, end: request.end_date };
test("limita la selección a meses completos dentro de la cobertura declarada", () => {
  deepStrictEqual(completeMonths({ start: "2023-12-02", end: "2024-03-30" }), { start: "2024-01", end: "2024-02" });
  deepStrictEqual(completeMonths({ start: "2024-02-01", end: "2024-02-29" }), { start: "2024-02", end: "2024-02" });
  equal(completeMonths({ start: "2024-02-02", end: "2024-02-29" }), null);
});
test("acepta la respuesta NASA de 288 meses para la geometría provisional", () => {
  // La estructura se comprueba aquí; la geometría y el método siguen sin validar.
  const path = new URL("../../../../../docs/evidencia/harmony-costa-rica-provisional-2001-2024.json", import.meta.url);
  const response = JSON.parse(readFileSync(path, "utf8"));
  const selection = { ...request, start_date: "2001-01-01", end_date: "2024-12-31" };
  const result = parseExploration(response, selection);
  equal(result.points.length, 288);
  equal(result.points[0].date, "2001-01-01");
  equal(result.points.at(-1).date, "2024-12-01");
});
function catalog() {
  return { status: "success", regions: [{ id: request.region_id, name: "Ejemplo", boundary_source: "Ejemplo", boundary_version: "1", geom: { type: "Polygon", coordinates: [[[0, 0], [1, 0], [1, 1], [0, 0]]] } }],
    variables: [{ id: "precipitation", name: "Ejemplo", source: "Ejemplo", dataset: "Ejemplo", unit: "mm/month", spatial_resolution: "Ejemplo", temporal_resolution: "monthly", available_interval: range, restrictions: [] }],
    combinations: [{ region_id: request.region_id, variable_id: "precipitation", available_interval: range, temporal_resolution: "monthly", is_ready_for_exploration: true }] };
}
function exploration() {
  return { status: "success", metadata: { variable_name: "Ejemplo", source: "Ejemplo", dataset: "Ejemplo", unit: "mm/month", spatial_resolution: "Ejemplo", temporal_resolution: "monthly", limitations: [], warnings: [],
    selection: { region_id: request.region_id, region_name: "Ejemplo", boundary_source: "Ejemplo", boundary_version: "1", requested_period: range, effective_period: range } },
    trend_analysis: { status: "inconclusive", method: "Ejemplo", summary: "Insuficiente", methodological_note: "Ejemplo", slope: null, slope_unit: null, p_value: null, confidence_level: null, is_significant: null },
    timeseries: [{ date: "2023-01-01", value: 0, coverage_fraction: 1, quality_flag: "ok", anomaly_mm: null }, { date: "2023-02-01", value: null, coverage_fraction: 0.5, quality_flag: "partial_coverage", anomaly_mm: null }], annual_totals: [] };
}
test("valida catálogo, cobertura y referencias entre opciones", () => {
  equal(parseCatalog(catalog()).combinations.length, 1);
  const bad = catalog(); bad.combinations[0].region_id = "otra";
  throws(() => parseCatalog(bad), ApiClientError);
});
test("acepta región identificada por huella y rechaza una referencia inválida", () => {
  const x = catalog();
  x.regions[0].geom = null;
  x.regions[0].geometry_sha256 = "a".repeat(64);
  equal(parseCatalog(x).regions[0].geometry_sha256, "a".repeat(64));
  x.regions[0].geometry_sha256 = "no-es-huella";
  throws(() => parseCatalog(x), ApiClientError);
});
test("conserva cero, faltante, cobertura parcial y análisis inconcluso", () => {
  const result = parseExploration(exploration(), request);
  equal(result.kind, "api_unverified"); equal(result.analysisStatus, "inconclusive");
  deepStrictEqual(result.points.map((p) => p.value), [0, null]);
  equal(result.points[1].coverageFraction, 0.5);
});
test("rechaza fechas, selección, unidad, cobertura y estados incompatibles", () => {
  for (const mutate of [
    (x) => { x.metadata.unit = ""; },
    (x) => { x.metadata.selection.effective_period = { start: "2023-02-01", end: "2023-02-28" }; },
    (x) => { x.metadata.selection.region_id = "otra-region"; },
    (x) => { x.timeseries[1].date = "2023-02-30"; },
    (x) => { x.timeseries[1].date = "2023-01-01"; },
    (x) => { x.timeseries[0].coverage_fraction = 1.1; },
    (x) => { x.trend_analysis.p_value = 0.2; },
    (x) => { x.timeseries.pop(); },
  ]) { const response = exploration(); mutate(response); throws(() => parseExploration(response, request), ApiClientError); }
});
test("transporta solicitudes y maneja error de cobertura sin filtrar detalles internos", async () => {
  const calls = [];
  const client = createApiV1Client("https://example.invalid/", async (url, init) => {
    calls.push({ url, init });
    if (init.method === "POST") return new Response(JSON.stringify(exploration()), { status: 200 });
    return new Response(JSON.stringify(catalog()), { status: 200 });
  });
  await client.catalog(); await client.explore(request);
  equal(calls[0].url, "https://example.invalid/catalog");
  deepStrictEqual(JSON.parse(calls[1].init.body), request);
  const failure = createApiV1Client("", async () => new Response(JSON.stringify({ error: { code: "NO_COVERAGE", message: "detalle interno" } }), { status: 400 }));
  await rejects(() => failure.explore(request), (e) => e.kind === "http" && e.status === 400 && e.code === "NO_COVERAGE" && !e.message.includes("interno"));
  const timeout = createApiV1Client("", async () => new Response(JSON.stringify({ error: { code: "BACKEND_TIMEOUT" } }), { status: 504 }));
  await rejects(() => timeout.explore(request), (e) => e.kind === "http" && e.status === 504 && e.code === "BACKEND_TIMEOUT");
});
test("rechaza JSON incompatible y distingue fallo de red", async () => {
  await rejects(() => createApiV1Client("", async () => new Response("no-json")).catalog(), (e) => e.kind === "invalid_response");
  await rejects(() => createApiV1Client("", async () => { throw new Error("secret"); }).catalog(), (e) => e.kind === "network" && !e.message.includes("secret"));
});
