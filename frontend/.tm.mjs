import { chromium } from "playwright";
const S = process.argv[2], tag = process.argv[3] || "full";
const b = await chromium.launch();
const p = await (await b.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
await p.goto("http://localhost:3010/login");
await p.fill('input[type=email]', "manager@sunrise-care.example");
await p.fill('input[type=password]', "demo1234");
await p.keyboard.press("Enter");
await p.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 60000 });
for (const w of [1440, 768, 390]) {
  await p.setViewportSize({ width: w, height: w === 390 ? 844 : 900 });
  await p.goto("http://localhost:3010/users");
  await p.addStyleTag({ content: ".ks-siren,.ks-sos-bar{display:none!important}" });
  await p.waitForTimeout(4000);
  const ox = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  console.log(w, "overflowX", ox);
  await p.screenshot({ path: `${S}/team-${tag}-${w}.png`, fullPage: true });
}
await b.close();
