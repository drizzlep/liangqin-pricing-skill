import { createRequire } from "node:module";
import { pathToFileURL } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const [htmlPath, imagePath, widthArg, heightArg] = process.argv.slice(2);

if (!htmlPath || !imagePath) {
  console.error("Usage: node render_quote_card_playwright.mjs <htmlPath> <imagePath> [width] [height]");
  process.exit(1);
}

const width = Number(widthArg || "1080");
const height = Number(heightArg || "1920");

const browser = await chromium.launch({ headless: true });

try {
  const page = await browser.newPage({
    viewport: { width, height },
    deviceScaleFactor: 1,
  });

  await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "load" });
  await page.evaluate(async () => {
    if (document.fonts?.ready) {
      await document.fonts.ready;
    }
  });
  await page.screenshot({
    path: imagePath,
    type: "jpeg",
    quality: 92,
    fullPage: false,
  });
} finally {
  await browser.close();
}
