// Prueba local: API en 8001 y frontend en 3001; las respuestas alteradas son sintéticas.
import { chromium } from "playwright";
import assert from "node:assert/strict";

const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe" });
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
    await period(page);
    await button(page).click();
    await page.getByRole("heading", { name: "Precipitación mensual" }).waitFor({ timeout: 30000 });
    assert.equal(await page.locator("tbody tr").count(), 12);
    await page.getByText("Ver valores y cobertura en una tabla").click();
    assert.match(await page.locator("tbody tr").first().innerText(), /70[.,]38/);
    assert.match(await page.locator("tbody tr").first().innerText(), />99 %/);
    assert.equal(await page.locator("#period-start").getAttribute("min"), "2001-01");
    assert.equal(await page.locator("#period-end").getAttribute("max"), "2024-12");
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

  const loading = await browser.newPage();
  await loading.route("**/api/backend/explorations", async (route) => { await new Promise((resolve) => setTimeout(resolve, 1000)); await route.continue(); });
  await ready(loading); await period(loading); await button(loading).click();
  await loading.getByRole("heading", { name: "Consultando la serie" }).waitFor();
  assert.equal(await loading.getByRole("button", { name: /Consultando/ }).isDisabled(), true);
  await loading.getByRole("heading", { name: "Precipitación mensual" }).waitFor({ timeout: 30000 });
  await loading.close();
  console.log("Límite, red, disponibilidad, vacío, geometría y carga OK");
} finally {
  await browser.close();
}
