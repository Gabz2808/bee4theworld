/** Cliente v1 para el subconjunto de exploración del MVP; no acredita procedencia científica. */
export type ExplorationRequest = {
  region_id: string;
  variable_id: "precipitation";
  start_date: string;
  end_date: string;
  temporal_resolution: "monthly";
};

type JsonObject = Record<string, unknown>;
export type Catalog = { status: "success"; regions: JsonObject[]; variables: JsonObject[]; combinations: JsonObject[] };
export type Exploration = {
  kind: "api_unverified";
  metadata: JsonObject;
  points: { date: string; value: number | null; coverageFraction: number; qualityFlag: string }[];
  // La interpretación científica del resultado permanece pendiente de revisión.
  analysisStatus: "conclusive" | "inconclusive" | "not_computed";
};

export interface ExplorationSource {
  catalog(signal?: AbortSignal): Promise<Catalog>;
  explore(request: ExplorationRequest, signal?: AbortSignal): Promise<Exploration>;
}

export class ApiClientError extends Error {
  readonly kind: "network" | "http" | "invalid_response";
  readonly status?: number;
  readonly code?: string;
  constructor(kind: "network" | "http" | "invalid_response", message: string, status?: number, code?: string) {
    super(message);
    this.name = "ApiClientError";
    this.kind = kind;
    this.status = status;
    this.code = code;
  }
}

function invalid(): never { throw new ApiClientError("invalid_response", "Respuesta de la API incompatible con el contrato provisional."); }
function object(value: unknown): JsonObject {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return invalid();
  return value as JsonObject;
}
function string(value: unknown): string {
  if (typeof value !== "string" || !value.trim()) return invalid();
  return value;
}
function date(value: unknown): string {
  const s = string(value);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(s)) return invalid();
  const d = new Date(`${s}T00:00:00Z`);
  if (!Number.isFinite(d.valueOf()) || d.toISOString().slice(0, 10) !== s) return invalid();
  return s;
}
function interval(value: unknown): { start: string; end: string } {
  const v = object(value), start = date(v.start), end = date(v.end);
  if (start > end) return invalid();
  return { start, end };
}
function array(value: unknown): unknown[] { if (!Array.isArray(value)) return invalid(); return value; }
function strings(value: unknown): void { array(value).forEach(string); }
function finite(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) return invalid();
  return value;
}

export function parseCatalog(input: unknown): Catalog {
  const data = object(input);
  if (data.status !== "success") return invalid();
  const regions = array(data.regions).map((v) => {
    const r = object(v); string(r.id); string(r.name); string(r.boundary_source); string(r.boundary_version);
    const geom = object(r.geom); if (geom.type !== "Polygon") return invalid();
    const rings = array(geom.coordinates); if (!rings.length) return invalid();
    for (const rawRing of rings) {
      const ring = array(rawRing); if (ring.length < 4) return invalid();
      const positions = ring.map((rawPosition) => {
        const position = array(rawPosition); if (position.length !== 2) return invalid();
        const lon = finite(position[0]), lat = finite(position[1]);
        if (Math.abs(lon) > 180 || Math.abs(lat) > 90) return invalid();
        return [lon, lat];
      });
      if (positions[0][0] !== positions[positions.length - 1][0] || positions[0][1] !== positions[positions.length - 1][1]) return invalid();
    }
    return r;
  });
  const variables = array(data.variables).map((v) => {
    const x = object(v); [x.id, x.name, x.source, x.dataset, x.unit, x.spatial_resolution].forEach(string);
    if (x.temporal_resolution !== "monthly") return invalid(); interval(x.available_interval); strings(x.restrictions); return x;
  });
  const combinations = array(data.combinations).map((v) => {
    const c = object(v); string(c.region_id); string(c.variable_id); interval(c.available_interval);
    if (c.temporal_resolution !== "monthly" || typeof c.is_ready_for_exploration !== "boolean") return invalid();
    if (!regions.some((r) => r.id === c.region_id) || !variables.some((x) => x.id === c.variable_id)) return invalid();
    return c;
  });
  if (!regions.length || !variables.length || !combinations.length) return invalid();
  return { status: "success", regions, variables, combinations };
}

export function parseExploration(input: unknown, request: ExplorationRequest): Exploration {
  const data = object(input), metadata = object(data.metadata), selection = object(metadata.selection);
  if (data.status !== "success" || metadata.temporal_resolution !== "monthly") return invalid();
  [metadata.variable_name, metadata.source, metadata.dataset, metadata.unit, metadata.spatial_resolution,
    selection.region_id, selection.region_name, selection.boundary_source, selection.boundary_version].forEach(string);
  strings(metadata.limitations); strings(metadata.warnings);
  const requested = interval(selection.requested_period), effective = interval(selection.effective_period);
  if (selection.region_id !== request.region_id || requested.start !== request.start_date || requested.end !== request.end_date || effective.start !== requested.start || effective.end !== requested.end) return invalid();
  const analysis = object(data.trend_analysis);
  if (analysis.status !== "conclusive" && analysis.status !== "inconclusive" && analysis.status !== "not_computed") return invalid();
  string(analysis.method); string(analysis.summary);
  if (analysis.status === "conclusive") {
    finite(analysis.slope); string(analysis.slope_unit);
    const p = finite(analysis.p_value), confidence = finite(analysis.confidence_level);
    if (p < 0 || p > 1 || confidence <= 0 || confidence > 1 || typeof analysis.is_significant !== "boolean") return invalid();
  } else {
    string(analysis.methodological_note);
    for (const key of ["slope", "slope_unit", "p_value", "confidence_level", "is_significant"]) if (analysis[key] != null) return invalid();
  }
  let previous = "";
  const points = array(data.timeseries).map((raw) => {
    const p = object(raw), d = date(p.date), coverage = finite(p.coverage_fraction), flag = string(p.quality_flag);
    if (!d.endsWith("-01") || d <= previous || d < effective.start || d > effective.end || coverage < 0 || coverage > 1 ||
      !["ok", "partial_coverage", "missing_value", "missing_month"].includes(flag)) return invalid();
    previous = d;
    const value = p.value === null ? null : finite(p.value);
    if (value !== null && value < 0) return invalid();
    if (p.anomaly_mm != null) finite(p.anomaly_mm);
    return { date: d, value, coverageFraction: coverage, qualityFlag: flag };
  });
  if (!points.length) return invalid();
  let expected = request.start_date;
  for (const point of points) {
    if (point.date !== expected) return invalid();
    const [year, month] = expected.split("-").map(Number);
    expected = month === 12 ? `${year + 1}-01-01` : `${year}-${String(month + 1).padStart(2, "0")}-01`;
  }
  if (previous.slice(0, 7) !== request.end_date.slice(0, 7)) return invalid();
  array(data.annual_totals).forEach((raw) => { const a = object(raw); if (!Number.isInteger(a.year) || finite(a.annual_precipitation_mm) < 0 || a.months_reported !== 12) invalid(); });
  return { kind: "api_unverified", metadata, points, analysisStatus: analysis.status };
}

/** La URL y el transporte se inyectan; no se incluyen claves en el cliente. */
export function createApiV1Client(baseUrl: string, transport: typeof fetch = fetch): ExplorationSource {
  const root = baseUrl.replace(/\/+$/, "");
  async function get(path: string, init: RequestInit): Promise<unknown> {
    let response: Response;
    try { response = await transport(`${root}${path}`, init); }
    catch (error) { if (init.signal?.aborted) throw error; throw new ApiClientError("network", "No se pudo conectar con la API."); }
    let data: unknown;
    try { data = await response.json(); } catch { if (!response.ok) throw new ApiClientError("http", "La API no pudo completar la solicitud.", response.status); return invalid(); }
    if (!response.ok) {
      let code: string | undefined;
      try { const body = object(object(data).error); code = string(body.code); } catch { /* Respuesta de error no compatible. */ }
      throw new ApiClientError("http", "La API no pudo completar la solicitud.", response.status, code);
    }
    return data;
  }
  return {
    async catalog(signal) { return parseCatalog(await get("/catalog", { signal })); },
    async explore(request, signal) {
      return parseExploration(await get("/explorations", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(request), signal }), request);
    },
  };
}
