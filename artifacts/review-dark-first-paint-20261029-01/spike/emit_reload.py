"""Emit Playwright warm-reload measurement scripts (no cache clearing)."""

from __future__ import annotations

from pathlib import Path

HERE = Path(__file__).resolve().parent
FRAMES = HERE / "frames"
FRAMES.mkdir(exist_ok=True)

TEMPLATE = r"""
async (page) => {
  const PREFIX = "__PREFIX__";
  const URL = "__URL__";
  const SCHEME = "__SCHEME__";
  const OUT = "__OUT__";
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 4 });
  await page.emulateMedia({ colorScheme: SCHEME });
  await page.goto(URL, { waitUntil: "load", timeout: 90000 });
  await page.waitForFunction(
    () => document.getElementById("root")?.childElementCount > 0,
    null,
    { timeout: 90000 },
  );
  await page.waitForTimeout(1000);
  const frames = [];
  const reload = page.reload({ waitUntil: "commit", timeout: 90000 }).catch(() => null);
  const started = Date.now();
  let shot = false;
  for (;;) {
    const elapsed = Date.now() - started;
    let sample = null;
    try {
      sample = await page.evaluate(() => {
        const html = document.documentElement;
        const body = document.body;
        return {
          htmlBg: html ? getComputedStyle(html).backgroundColor : null,
          bodyBg: body ? getComputedStyle(body).backgroundColor : null,
          rootKids: document.getElementById("root")
            ? document.getElementById("root").childElementCount
            : -1,
        };
      });
    } catch (e) {
      sample = { error: String(e) };
    }
    frames.push({ elapsed, ...sample });
    if (!shot && sample && sample.htmlBg) {
      shot = true;
      try {
        await page.screenshot({ path: `${OUT}/${PREFIX}-first-${String(elapsed).padStart(5, "0")}.png` });
      } catch (e) {
        frames.push({ elapsed, shotError: String(e) });
      }
    }
    if (elapsed > 4000 && sample && sample.rootKids > 0) break;
    if (elapsed > 20000) break;
    await page.waitForTimeout(50);
  }
  await reload;
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
  await cdp.send("Emulation.setCPUThrottlingRate", { rate: 1 });
  return { prefix: PREFIX, scheme: SCHEME, states };
}
"""


def emit(prefix: str, url: str, scheme: str) -> None:
    body = (
        TEMPLATE.replace("__PREFIX__", prefix)
        .replace("__URL__", url)
        .replace("__SCHEME__", scheme)
        .replace("__OUT__", str(FRAMES))
    )
    (HERE / f"reload-{prefix}.js").write_text(body.strip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    for prefix, url in (
        ("baseline", "http://10.0.0.56:8501/"),
        ("patched", "http://10.0.0.56:8502/"),
    ):
        for scheme in ("dark", "light"):
            emit(f"{prefix}-{scheme}", url, scheme)
    print("written", sorted(p.name for p in HERE.glob("reload-*.js")))
