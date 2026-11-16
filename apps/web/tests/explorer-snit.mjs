// Prueba local: API en 8001 y frontend en 3001; las respuestas alteradas son sintéticas.
import { chromium } from "playwright";
import assert from "node:assert/strict";

const launched = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe" });
// Estas pruebas verifican textos en español; el sitio usa inglés por defecto.
const context = await launched.newContext();
await context.addInitScript(() => { try { localStorage.setItem("iyok-locale", "es"); } catch {} });
const browser = { newPage: (options) => options ? launched.newContext(options).then(async (c) => { await c.addInitScript(() => { try { localStorage.setItem("iyok-locale", "es"); } catch {} }); return c.newPage(); }) : context.newPage(), close: () => launched.close() };
const base = process.env.IYOK_TEST_URL || "http://localhost:3001";
const button = (page) => page.getByRole("button", { name: "Consultar serie" });
async function ready(page) {
  await page.goto(base);
  await page.locator("#period-start:enabled").waitFor({ timeout: 30000 });
}
async function period(page, start = "2024-01", end = "2024-12") {
  await page.locator("#period-start").fill(start);
  await page.locator("#period-end").fill(end);
}

try {
  for (const width of [1280, 390]) {
    const page = await browser.newPage({ viewport: { width, height: 800 } });
    await ready(page);
    assert.equal(await page.getByRole("link", { name: "Investigación", exact: true }).getAttribute("href"), "#investigacion");
    assert.equal(await page.getByRole("heading", { name: "Pruebas y alcance técnico" }).count(), 1);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await period(page);
    await button(page).click();
    await page.getByRole("heading", { name: "Precipitación mensual" }).waitFor({ timeout: 30000 });
    assert.equal(await page.getByText("MVP · serie en revisión").isVisible(), true);
    assert.equal(await page.getByText(/El índice de calidad de NASA aún no se muestra/).isVisible(), true);
    assert.equal(await page.getByText(/Su procedencia, calidad y procesamiento siguen en revisión científica/).isVisible(), true);
    assert.equal(await page.getByRole("heading", { name: "Estado del análisis de tendencia" }).isVisible(), true);
    assert.equal(await page.getByText("Inconcluso", { exact: true }).isVisible(), true);
    assert.match(await page.locator(".trend-status").innerText(), /intervalo de confianza revisado/);
    assert.match(await page.locator(".trend-status").innerText(), /no demuestran.*su causa/);
    assert.match(await page.locator(".evidence-list").innerText(), /GPM_3IMERGM\.07/);
    assert.equal(await page.locator("tbody tr").count(), 12);
    await page.getByText("Ver valores y cobertura en una tabla").click();
    assert.equal(await page.getByRole("columnheader", { name: "Estado de cobertura" }).isVisible(), true);
    assert.match(await page.locator("tbody tr").first().innerText(), /Parcial/);
    assert.match(await page.locator("tbody tr").first().innerText(), /70[.,]38/);
    assert.match(await page.locator("tbody tr").first().innerText(), />99 %/);
    assert.equal(await page.locator("#period-start").getAttribute("min"), "2001-01");
    assert.equal(await page.locator("#period-end").getAttribute("max"), "2024-12");
    await period(page, "2023-01", "2023-12");
    await page.getByRole("heading", { name: "Aquí comienza la exploración" }).waitFor();
    assert.equal(await page.locator("tbody tr").count(), 0);
    if (width === 1280) {
      await period(page, "2001-01", "2024-12");
      await button(page).click();
      await page.getByRole("heading", { name: "Precipitación mensual" }).waitFor({ timeout: 30000 });
      assert.equal(await page.locator("tbody tr").count(), 288);
    }
    await period(page, "2024-12", "2024-01");
    await button(page).click();
    assert.match(await page.locator("#period-error").innerText(), /fecha inicial/);
    await page.close();
    console.log(`${width}px: serie real y fechas invertidas OK`);
  }

  const rate = await browser.newPage();
  await rate.route("**/api/backend/explorations", (route) => route.fulfill({ status: 429, contentType: "application/json", body: JSON.stringify({ error: { code: "RATE_LIMIT_EXCEEDED" } }) }));
  await ready(rate); await period(rate); await button(rate).click();
  await rate.getByText(/límite de consultas/).first().waitFor();
  await rate.close();

  const offline = await browser.newPage();
  await offline.route("**/api/backend/explorations", (route) => route.abort());
  await ready(offline); await period(offline); await button(offline).click();
  await offline.getByText(/No fue posible conectar con el servicio/).first().waitFor();
  await offline.close();

  const unavailable = await browser.newPage();
  await unavailable.route("**/api/backend/catalog", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.combinations.find((x) => x.region_id === "costa-rica-snit-continental-v1").is_ready_for_exploration = false;
    await route.fulfill({ response, json: data });
  });
  await unavailable.goto(base);
  await unavailable.getByRole("button", { name: /Reintentar conexión/ }).waitFor();
  assert.equal(await unavailable.locator("#period-start").isDisabled(), true);
  await unavailable.close();

  const missing = await browser.newPage();
  await missing.route("**/api/backend/explorations", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.timeseries[0].value = 0;
    data.timeseries[0].coverage_fraction = 1;
    data.timeseries[0].quality_flag = "ok";
    data.timeseries[1].value = null;
    data.timeseries[1].quality_flag = "missing_value";
    await route.fulfill({ response, json: data });
  });
  await ready(missing); await period(missing); await button(missing).click();
  await missing.getByRole("heading", { name: "Precipitación mensual" }).waitFor();
  await missing.getByText("Ver valores y cobertura en una tabla").click();
  assert.match(await missing.locator("tbody tr").nth(0).innerText(), /2024-01\s+0/);
  assert.match(await missing.locator("tbody tr").nth(0).innerText(), /Completa/);
  assert.match(await missing.locator("tbody tr").nth(1).innerText(), /2024-02\s+Sin dato/);
  assert.match(await missing.locator("tbody tr").nth(1).innerText(), /Sin valor/);
  assert.match(await missing.locator("thead").innerText(), /Valor \(.+\)/);
  await missing.close();

  const empty = await browser.newPage();
  await empty.route("**/api/backend/explorations", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    for (const p of data.timeseries) { p.value = null; p.quality_flag = "missing_value"; }
    await route.fulfill({ response, json: data });
  });
  await ready(empty); await period(empty); await button(empty).click();
  await empty.getByRole("heading", { name: "No hay valores para este período." }).waitFor();
  await empty.close();

  const mismatch = await browser.newPage();
  await mismatch.route("**/api/backend/explorations", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.metadata.selection.geometry_sha256 = "0".repeat(64);
    await route.fulfill({ response, json: data });
  });
  await ready(mismatch); await period(mismatch); await button(mismatch).click();
  await mismatch.getByText(/respuesta no tiene el formato esperado/).first().waitFor();
  await mismatch.close();

  // Respuesta sintética: no habilita inferencias antes de la revisión científica.
  const unreviewed = await browser.newPage();
  await unreviewed.route("**/api/backend/explorations", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.trend_analysis = { status: "conclusive", method: "Método sintético", summary: "Ejemplo", slope: 123.456, slope_unit: "mm/año", p_value: 0.001, confidence_level: 0.95, is_significant: true };
    await route.fulfill({ response, json: data });
  });
  await ready(unreviewed); await period(unreviewed); await button(unreviewed).click();
  await unreviewed.getByRole("heading", { name: "Precipitación mensual" }).waitFor();
  assert.equal(await unreviewed.getByText("Resultado en revisión", { exact: true }).isVisible(), true);
  assert.doesNotMatch(await unreviewed.locator(".trend-status").innerText(), /123[.,]456|0[.,]001/);
  await unreviewed.close();

  // Aunque el catálogo anuncie meses fuera de la serie SNIT, el selector se limita a 2001-2024.
  const wide = await browser.newPage();
  await wide.route("**/api/backend/catalog", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.combinations.find((x) => x.region_id === "costa-rica-snit-continental-v1").available_interval = { start: "1998-01-01", end: "2025-06-30" };
    await route.fulfill({ response, json: data });
  });
  await ready(wide);
  assert.equal(await wide.locator("#period-start").getAttribute("min"), "2001-01");
  assert.equal(await wide.locator("#period-end").getAttribute("max"), "2024-12");
  assert.match(await wide.locator(".control-note").innerText(), /Período disponible: 2001-01 a 2024-12/);
  let wideRequests = 0;
  wide.on("request", (request) => { if (request.url().includes("/api/backend/explorations")) wideRequests += 1; });
  await period(wide, "1998-01", "1998-12");
  await button(wide).click();
  assert.equal(await wide.locator("#period-start").evaluate((input) => input.validity.rangeUnderflow), true);
  await wide.waitForTimeout(1000);
  assert.equal(wideRequests, 0);
  await wide.close();

  const loading = await browser.newPage();
  await loading.route("**/api/backend/explorations", async (route) => { await new Promise((resolve) => setTimeout(resolve, 1000)); await route.continue(); });
  await ready(loading); await period(loading); await button(loading).click();
  await loading.getByRole("heading", { name: "Consultando la serie" }).waitFor();
  assert.equal(await loading.getByRole("button", { name: /Consultando/ }).isDisabled(), true);
  assert.equal(await loading.locator("#period-start").isDisabled(), true);
  assert.equal(await loading.locator("#period-end").isDisabled(), true);
  await loading.getByRole("heading", { name: "Precipitación mensual" }).waitFor({ timeout: 30000 });
  assert.match(await loading.locator(".chart-caption").first().innerText(), /2024-01 a 2024-12/);
  await loading.close();
  console.log("Límite, red, disponibilidad, vacío, geometría y carga OK");
} finally {
  await browser.close();
}
