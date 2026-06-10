// Dev-only helper: screenshot key views to verify the UI renders.
import { chromium } from "playwright";

const base = "http://localhost:5173";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });

async function shot(name) {
  await page.waitForTimeout(1200);
  await page.screenshot({ path: `../_shots/${name}.png` });
  console.log("shot", name);
}

const nav = (name) => page.locator(".nav button", { hasText: name });

await page.goto(base, { waitUntil: "networkidle" });
await shot("01-chat");

await nav("Customers").click();
await shot("02-customers");

await nav("Campaigns").click();
await shot("03-campaigns");

// open first campaign if present
const open = page.getByText("Open →").first();
if (await open.count()) { await open.click(); await shot("04-campaign-detail"); }

await nav("Segments").click();
await shot("05-segments");

await browser.close();
console.log("done");
