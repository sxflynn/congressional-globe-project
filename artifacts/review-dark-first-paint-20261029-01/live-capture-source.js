async (page) => {
  const url = "http://127.0.0.1:18503/";
  const out = "/Users/sflynn/Downloads/congressional globe project/artifacts/review-dark-first-paint-20261029-01/live-frames";
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Network.enable");
  await cdp.send("Emulation.setCPUThrottlingRate", {rate:4});
  await cdp.send("Network.emulateNetworkConditions", {offline:false, latency:300, downloadThroughput:200000, uploadThroughput:100000});
  const read = async () => page.evaluate(() => {
    const html=document.documentElement, body=document.body, root=document.getElementById("root");
    return {
      t:Math.round(performance.now()),
      htmlBg:html?getComputedStyle(html).backgroundColor:null,
      bodyBg:body?getComputedStyle(body).backgroundColor:null,
      scheme:matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light",
      width:innerWidth,
      rootKids:root?.childElementCount??-1,
      title:document.title,
      ready:document.readyState
    };
  }).catch(e=>({error:String(e)}));
  const scenarios = [];
  const settle = async(label) => {
    await page.waitForFunction(() => document.getElementById("root")?.childElementCount > 0, null, {timeout:90000});
    await page.waitForTimeout(500);
    const result=await read();
    await page.screenshot({path:out+"/"+label+"-final.png"});
    return result;
  };
  const captureCold = async (label, scheme, width) => {
    await page.setViewportSize({width,height:width===375?812:900});
    await page.emulateMedia({colorScheme:scheme});
    await cdp.send("Network.clearBrowserCache");
    await cdp.send("Network.setCacheDisabled", {cacheDisabled:true});
    const started=Date.now();
    await page.goto(url,{waitUntil:"commit",timeout:90000});
    const samples=[];
    for(const t of [0,300,1000]){
      const delay=t-(Date.now()-started); if(delay>0) await page.waitForTimeout(delay);
      samples.push(await read());
      await page.screenshot({path:out+"/"+label+"-cold-"+t+".png"});
    }
    const settled=await settle(label+"-cold");
    scenarios.push({label,kind:"cold",samples,settled});
    await cdp.send("Network.setCacheDisabled",{cacheDisabled:false});
  };
  const captureReload = async (label, scheme, width) => {
    await page.setViewportSize({width,height:width===375?812:900});
    await page.emulateMedia({colorScheme:scheme});
    const started=Date.now();
    await page.reload({waitUntil:"commit",timeout:90000});
    const samples=[];
    for(const t of [0,300]){
      const delay=t-(Date.now()-started); if(delay>0) await page.waitForTimeout(delay);
      samples.push(await read());
      await page.screenshot({path:out+"/"+label+"-reload-"+t+".png"});
    }
    const settled=await settle(label+"-reload");
    scenarios.push({label,kind:"reload",samples,settled});
  };
  await page.goto("about:blank");
  await captureCold("desktop-dark","dark",1280);
  await captureReload("desktop-dark","dark",1280);
  await captureCold("desktop-light","light",1280);
  await captureReload("desktop-light","light",1280);
  await captureCold("mobile-dark","dark",375);
  await captureReload("mobile-dark","dark",375);
  await captureCold("mobile-light","light",375);
  await captureReload("mobile-light","light",375);
  await cdp.send("Emulation.setCPUThrottlingRate",{rate:1});
  await cdp.send("Network.emulateNetworkConditions",{offline:false,latency:0,downloadThroughput:-1,uploadThroughput:-1});
  const earlyHead=await page.evaluate(()=>({
    patch:document.getElementById("review-desk-first-paint")?.textContent??null,
    meta:document.querySelector('meta[name="color-scheme"]')?.content??null,
    body:document.body?.innerText.slice(0,160)??null
  }));
  return {url,scenarios,earlyHead};
}
