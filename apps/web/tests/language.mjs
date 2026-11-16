// Prueba local del interruptor de idioma: frontend en 3001 (no requiere la API).
// El inglés es el idioma principal; el español se activa con el interruptor.
import { chromium } from "playwright";
import assert from "node:assert/strict";

const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || "C:/Program Files/Google/Chrome/Application/chrome.exe" });
const base = process.env.IYOK_TEST_URL || "http://localhost:3001";

try {
  for (const width of [1280, 390]) {
    const page = await browser.newPage({ viewport: { width, height: 800 } });
    await page.goto(base);
    await page.getByRole("heading", { name: /Understanding Earth/ }).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.lang), "en");
    assert.equal(await page.getByRole("link", { name: "Research", exact: true }).isVisible(), true);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.getByRole("button", { name: "Cambiar el idioma a español" }).click();
    await page.getByRole("heading", { name: /Entender la Tierra/ }).waitFor();
    assert.equal(await page.evaluate(() => document.documentElement.lang), "es");
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.reload();
    await page.getByRole("heading", { name: /Entender la Tierra/ }).waitFor();
    await page.getByRole("button", { name: "Cambiar el idioma a inglés" }).click();
    await page.getByRole("heading", { name: /Understanding Earth/ }).waitFor();
    await page.close();
  }
  console.log("language toggle: ok");
} finally {
  await browser.close();
}
