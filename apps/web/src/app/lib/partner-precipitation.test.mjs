import { test } from "node:test";
import { deepStrictEqual, equal, throws } from "node:assert/strict";
import { adaptPartnerPrecipitation } from "./partner-precipitation.ts";

function response() {
  return {
    status: "success",
    metadata: { variable_name: "Ejemplo", unit: "unidad ilustrativa", source: "no verificada", dataset: "ejemplo", limitations: ["Solo para pruebas"] },
    timeseries: [
      { date: "2023-01-01", value: 0, coverage_fraction: 1, quality_flag: "ok" },
      { date: "2023-02-01", value: null, coverage_fraction: 0.5, quality_flag: "partial_coverage" },
    ],
    trend_analysis: { status: "conclusive", summary: "No debe presentarse" },
  };
}

test("conserva ceros, faltantes y calidad sin aceptar la tendencia", () => {
  const adapted = adaptPartnerPrecipitation(response());
  equal(adapted.kind, "partner_unverified");
  deepStrictEqual(adapted.points.map(({ value }) => value), [0, null]);
  equal(adapted.points[1].coverageFraction, 0.5);
  equal("trend_analysis" in adapted, false);
});

test("rechaza fechas repetidas y cobertura fuera de rango", () => {
  const duplicate = response();
  duplicate.timeseries[1].date = duplicate.timeseries[0].date;
  throws(() => adaptPartnerPrecipitation(duplicate));
  const invalidCoverage = response();
  invalidCoverage.timeseries[1].coverage_fraction = 1.1;
  throws(() => adaptPartnerPrecipitation(invalidCoverage));
});

test("rechaza metadatos o valores inválidos", () => {
  const missingUnit = response();
  missingUnit.metadata.unit = "";
  throws(() => adaptPartnerPrecipitation(missingUnit));
  const badValue = response();
  badValue.timeseries[0].value = Number.NaN;
  throws(() => adaptPartnerPrecipitation(badValue));
});
