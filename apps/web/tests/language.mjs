// Prueba local del interruptor de idioma y de las tres páginas: frontend en 3001 (no requiere la API).
// El inglés es el idioma principal; el español se activa con el interruptor.
import { chromium } from "playwright";
import assert from "node:assert/strict";

const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe" });
const base = process.env.IYOK_TEST_URL || "http://localhost:3001";
const shots = process.env.IYOK_SHOTS;
const noHorizontalScroll = (page) => page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);

try {
  for (const width of [1280, 390]) {
    const page = await browser.newPage({ viewport: { width, height: 800 } });

    // Landing: solo presentación y accesos.
    await page.goto(base);
    await page.getByRole("heading", { name: /Understanding Earth/ }).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.lang), "en");
    assert.equal(await page.getByText("Tests and technical scope").count(), 0);
    assert.equal(await page.locator("#period-start").count(), 0);
    assert.equal(await noHorizontalScroll(page), true);
    if (shots) await page.screenshot({ path: `${shots}/landing-${width}.png`, fullPage: true });

    // Investigación abierta.
    await page.getByRole("link", { name: "Read the open research" }).click();
    await page.waitForURL("**/investigacion");
    await page.getByRole("heading", { name: "Tests and technical scope" }).waitFor();
    assert.equal(await page.getByRole("link", { name: "Research", exact: true }).getAttribute("aria-current"), "page");
    assert.equal(await noHorizontalScroll(page), true);
    if (shots) await page.screenshot({ path: `${shots}/research-${width}.png` });

    // Gráficos y series. Next conserva la página anterior oculta; lo relevante es que no se vea.
    await page.getByRole("link", { name: "Charts & series", exact: true }).click();
    await page.waitForURL("**/explorar");
    await page.locator("#period-start").waitFor({ state: "attached" });
    assert.equal(await page.getByText("Tests and technical scope").isVisible(), false);
    assert.equal(await noHorizontalScroll(page), true);

    // Cambio de idioma y persistencia.
    await page.getByRole("button", { name: "Cambiar el idioma a español" }).click();
    await page.getByRole("heading", { name: /Haz una pregunta/ }).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.lang), "es");
    await page.goto(base);
    await page.getByRole("heading", { name: /Entender la Tierra/ }).waitFor();
    await page.getByRole("link", { name: "Comenzar a explorar" }).click();
    await page.waitForURL("**/explorar");
    await page.getByRole("button", { name: "Cambiar el idioma a inglés" }).click();
    await page.getByRole("heading", { name: /Ask a question/ }).waitFor();
    await page.close();
  }
  console.log("pages and language toggle: ok");
} finally {
  await browser.close();
}
