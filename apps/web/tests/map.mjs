// Prueba local del mapa (issue #11): API en 8001 y frontend en IYOK_TEST_URL.
// Las respuestas alteradas son sintéticas y solo prueban estados de error.
import { chromium } from "playwright";
import assert from "node:assert/strict";

const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe" });
const base = process.env.IYOK_TEST_URL || "http://localhost:3001";
const shots = process.env.IYOK_SCREENSHOTS;

async function openMap(page, { start = "2024-01", end = "2024-12" } = {}) {
  await page.goto(base);
  await page.locator("#period-start:enabled").waitFor({ timeout: 30000 });
  await page.locator("#period-start").fill(start);
  await page.locator("#period-end").fill(end);
  await page.getByRole("button", { name: "Consultar serie" }).click();
  await page.getByRole("heading", { name: "Precipitación mensual" }).waitFor({ timeout: 30000 });
  // Navegación de pestañas con teclado.
  await page.getByRole("tab", { name: "Serie temporal" }).focus();
  await page.keyboard.press("ArrowRight");
  const tab = page.getByRole("tab", { name: "Mapa" });
  assert.equal(await tab.getAttribute("aria-selected"), "true");
  assert.equal(await page.evaluate(() => document.activeElement?.id), "tab-map");
  await page.locator(".map-canvas canvas").waitFor({ timeout: 30000 });
}

try {
  for (const width of [1280, 390]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    const layers = [];
    page.on("response", (response) => { const m = response.url().match(/map-data\/(\d{4}-\d{2})\.json$/); if (m && response.ok()) layers.push(m[1]); });
    await openMap(page);
    await page.waitForFunction(() => document.querySelector(".map-view [role=status]")?.textContent === "", null, { timeout: 30000 });
    assert.deepEqual(layers, ["2024-01"]);
    assert.match(await page.locator(".map-description").innerText(), /2024-01 en la serie: 70,4 mm\/mes/);
    assert.match(await page.locator(".maplibregl-ctrl-attrib").innerText(), /NASA GES DISC/);
    assert.match(await page.locator(".maplibregl-ctrl-attrib").innerText(), /SNIT/);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    // El encuadre inicial debe contener el territorio completo.
    const bounds = await page.locator(".map-canvas").boundingBox();
    assert.ok(bounds && bounds.width <= width);
    if (shots) await page.screenshot({ path: `${shots}/map-${width}.png`, fullPage: false, clip: { x: 0, y: Math.max(0, bounds.y - 120), width, height: Math.min(900, bounds.height + 360) } });

    // Control temporal con teclado.
    const slider = page.locator("#map-month");
    await slider.focus();
    await page.keyboard.press("ArrowRight");
    assert.equal(await slider.getAttribute("aria-valuetext"), "2024-02");
    await page.waitForFunction(() => document.querySelector(".map-view [role=status]")?.textContent === "", null, { timeout: 15000 });
    assert.equal(layers.at(-1), "2024-02");
    await page.keyboard.press("End");
    assert.equal(await slider.getAttribute("aria-valuetext"), "2024-12");

    // Reproducción: desde el último mes vuelve a empezar y avanza.
    await page.getByRole("button", { name: "Reproducir" }).click();
    await page.waitForFunction(() => ["2024-02", "2024-03"].includes(document.querySelector("#map-month")?.getAttribute("aria-valuetext") ?? ""), null, { timeout: 15000 });
    await page.getByRole("button", { name: "Pausar" }).click();
    const paused = await slider.getAttribute("aria-valuetext");
    await page.waitForTimeout(2000);
    assert.equal(await slider.getAttribute("aria-valuetext"), paused);

    // La gráfica refleja el mes elegido en el mapa.
    await page.getByRole("tab", { name: "Serie temporal" }).click();
    assert.match(await page.locator(".results").innerText(), new RegExp(`Mes seleccionado en el mapa: ${paused}`));
    await page.close();
    console.log(`${width}px: mapa, teclado, reproducción y sincronización OK`);
  }

  // Sin fondo cartográfico: las capas siguen disponibles.
  const offline = await browser.newPage();
  await offline.route("https://tile.openstreetmap.org/**", (route) => route.abort());
  await openMap(offline);
  await offline.getByText(/No se pudo cargar el fondo cartográfico/).waitFor({ timeout: 30000 });
  await offline.waitForFunction(() => document.querySelector(".map-view [role=status]")?.textContent === "", null, { timeout: 30000 });
  await offline.close();

  // Capa ausente.
  const missing = await browser.newPage();
  await missing.route("**/map-data/2024-01.json", (route) => route.fulfill({ status: 404, body: "" }));
  await openMap(missing);
  await missing.getByText("No se pudo cargar la capa de 2024-01.").waitFor({ timeout: 30000 });
  await missing.close();

  // Manifiesto de otra geometría: no se dibujan capas.
  const foreign = await browser.newPage();
  const requested = [];
  foreign.on("request", (request) => { if (/map-data\/\d{4}-\d{2}\.json$/.test(request.url())) requested.push(request.url()); });
  await foreign.route("**/map-data/manifest.json", async (route) => {
    const response = await route.fetch();
    const data = await response.json();
    data.geometry_sha256 = "0".repeat(64);
    await route.fulfill({ response, json: data });
  });
  await openMap(foreign);
  await foreign.getByText(/No se pudo comprobar el origen de las capas/).waitFor({ timeout: 30000 });
  assert.equal(await foreign.getByRole("button", { name: "Reproducir" }).isDisabled(), true);
  assert.deepEqual(requested, []);
  await foreign.close();
  console.log("Estados sin fondo, capa ausente y manifiesto incompatible OK");
} finally {
  await browser.close();
}
