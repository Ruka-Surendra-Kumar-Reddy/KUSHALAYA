const { chromium } = require("@playwright/test");
(async () => {
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1280, height: 900 } });
  await p.goto("http://family.localhost:3010/login", { waitUntil: "networkidle", timeout: 240000 });
  console.log("login URL:", p.url());
  await p.locator('input[type=email]').fill("lakshmi.family@sunrise-care.example");
  await p.locator('input[type=password]').fill("demo1234");
  await p.locator('button[type=submit]').click();
  await p.waitForTimeout(4000);
  console.log("after login:", p.url());
  const name = await p.locator(".ks-avatar-name").textContent().catch(() => null);
  const avatar = await p.locator(".ks-avatar").first().textContent().catch(() => null);
  console.log("avatar initials:", avatar, "| name shown:", name || "(none)");
  await p.locator(".ks-topbar").screenshot({ path: `${process.argv[2]}/topbar.png` }).catch(() => {});
  await b.close();
})();
