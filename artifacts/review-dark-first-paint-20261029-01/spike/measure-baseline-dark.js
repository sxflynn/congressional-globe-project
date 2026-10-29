async (page) => {
  const PREFIX = "baseline-dark";
  const URL = "http://10.0.0.56:8501/";
  const SCHEME = "dark";
  const OUT = "/Users/sflynn/Downloads/congressional globe project/artifacts/review-dark-first-paint-20261029-01/spike/frames";
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Network.clearBrowserCache");
  await cdp.send("Network.setCacheDisabled", { cacheDisabled: true });
  await cdp.send("Network.emulateNetworkConditions", {
    offline: false,
    latency: 300,
    downloadThroughput: 200000,
    uploadThroughput: 100000,
  });
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  await page.emulateMedia({ colorScheme: SCHEME });
  const frames = [];
  const shots = [300, 800, 1500, 3000, 6000, 12000];
  let nextShot = 0;
  let navError = null;
  const nav = page.goto(URL, { waitUntil: "commit", timeout: 90000 }).catch((e) => {
    navError = String(e);
  });
  const started = Date.now();
  for (;;) {
    const elapsed = Date.now() - started;
    let sample = null;
    try {
      sample = await page.evaluate(() => {
        const html = document.documentElement;
        const body = document.body;
        return {
          t: Math.round(performance.now()),
          htmlBg: html ? getComputedStyle(html).backgroundColor : null,
          bodyBg: body ? getComputedStyle(body).backgroundColor : null,
          rootKids: document.getElementById("root")
            ? document.getElementById("root").childElementCount
            : -1,
          scheme: matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light",
          ready: document.readyState,
        };
      });
    } catch (e) {
      sample = { error: String(e) };
    }
    frames.push({ elapsed, ...sample });
    if (nextShot < shots.length && elapsed >= shots[nextShot]) {
      try {
        await page.screenshot({
          path: `${OUT}/${PREFIX}-${String(elapsed).padStart(6, "0")}.png`,
        });
      } catch (e) {
        frames.push({ elapsed, shotError: String(e) });
      }
      nextShot += 1;
    }
    const settled = sample && sample.rootKids > 0;
    if ((settled && elapsed > 1500) || elapsed > 45000 || navError) break;
    await page.waitForTimeout(100);
  }
  await nav;
  await page.waitForTimeout(1500);
  try {
    frames.push({
      elapsed: Date.now() - started,
      final: await page.evaluate(() => ({
        htmlBg: getComputedStyle(document.documentElement).backgroundColor,
        bodyBg: getComputedStyle(document.body).backgroundColor,
        title: document.title,
      })),
    });
    await page.screenshot({ path: `${OUT}/${PREFIX}-final.png` });
  } catch (e) {
    frames.push({ finalError: String(e) });
  }
  await cdp.send("Network.setCacheDisabled", { cacheDisabled: false });
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });
  await cdp.send("Network.emulateNetworkConditions", {
    offline: false,
    latency: 0,
    downloadThroughput: -1,
    uploadThroughput: -1,
  });
  const states = [];
  for (const f of frames) {
    if (!("htmlBg" in f)) continue;
    const key = `${f.htmlBg}|${f.bodyBg}|${f.rootKids}`;
    const last = states[states.length - 1];
    if (!last || last.key !== key) {
      states.push({
        key,
        from: f.elapsed,
        to: f.elapsed,
        htmlBg: f.htmlBg,
        bodyBg: f.bodyBg,
        rootKids: f.rootKids,
      });
    } else {
      last.to = f.elapsed;
    }
  }
  const final = frames.filter((f) => f.final).map((f) => f.final)[0] ?? null;
  return { prefix: PREFIX, url: URL, scheme: SCHEME, navError, states, final };
}
