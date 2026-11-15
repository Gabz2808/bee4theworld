/** Adaptación provisional de una respuesta compartida para revisión, no del contrato acordado. */
export type UnverifiedPrecipitation = {
  kind: "partner_unverified";
  title: string;
  unit: string;
  source: string;
  dataset: string;
  limitations: string[];
  points: { date: string; value: number | null; coverageFraction: number; qualityFlag: string }[];
};

function record(value: unknown): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error("Se esperaba un objeto en la respuesta de precipitación.");
  }
  return value as Record<string, unknown>;
}

function nonempty(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

/** No valida procedencia científica ni interpreta tendencia, anomalías o geometría. */
export function adaptPartnerPrecipitation(input: unknown): UnverifiedPrecipitation {
  const response = record(input);
  if (response.status !== "success") throw new Error("La respuesta no indica éxito.");
  const metadata = record(response.metadata);
  if (!nonempty(metadata.variable_name) || !nonempty(metadata.unit) ||
      !nonempty(metadata.source) || !nonempty(metadata.dataset) ||
      !Array.isArray(metadata.limitations) || !metadata.limitations.every(nonempty)) {
    throw new Error("Los metadatos de la serie están incompletos.");
  }
  if (!Array.isArray(response.timeseries) || response.timeseries.length === 0) {
    throw new Error("La serie mensual está vacía o no es válida.");
  }
  let previous = "";
  const points = response.timeseries.map((raw: unknown) => {
    const point = record(raw);
    if (typeof point.date !== "string" || !/^\d{4}-(0[1-9]|1[0-2])-01$/.test(point.date) || point.date <= previous) {
      throw new Error("Las fechas mensuales deben ser válidas, únicas y ordenadas.");
    }
    previous = point.date;
    if (point.value !== null && (typeof point.value !== "number" || !Number.isFinite(point.value) || point.value < 0)) {
      throw new Error("La precipitación debe ser un número finito no negativo o null.");
    }
    if (typeof point.coverage_fraction !== "number" || !Number.isFinite(point.coverage_fraction) ||
        point.coverage_fraction < 0 || point.coverage_fraction > 1 || !nonempty(point.quality_flag)) {
      throw new Error("La cobertura o la calidad de un punto no son válidas.");
    }
    return { date: point.date, value: point.value, coverageFraction: point.coverage_fraction, qualityFlag: point.quality_flag };
  });
  return {
    kind: "partner_unverified", title: metadata.variable_name, unit: metadata.unit,
    source: metadata.source, dataset: metadata.dataset, limitations: metadata.limitations, points,
  };
}
