/* Local synthetic native-IDB checks. node offline-cdp.cjs HARNESS_DIR RESULT_DIR */
const fs = require('fs'), path = require('path'), http = require('http'), { spawn } = require('child_process');
const assert = require('assert/strict');
const fixture = path.resolve(process.argv[2]), output = path.resolve(process.argv[3]);
const pause = ms => new Promise(r => setTimeout(r, ms));
const server = http.createServer((req, res) => {
  const file = path.join(fixture, req.url === '/bundle.js' ? 'bundle.js' : 'index.html');
  res.setHeader('Content-Type', file.endsWith('.js') ? 'text/javascript' : 'text/html');
  fs.createReadStream(file).pipe(res);
});
let browser; const clients = [];
async function page() {
  const tab = await (await fetch('http://127.0.0.1:9235/json/new?about:blank', { method: 'PUT' })).json();
  const ws = new WebSocket(tab.webSocketDebuggerUrl); clients.push(ws);
  await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
  let seq = 0; const pending = new Map();
  ws.onmessage = e => { const r = JSON.parse(e.data); if (!r.id) return;
    const p = pending.get(r.id); pending.delete(r.id);
    if (r.error || r.result?.exceptionDetails) p.reject(new Error(JSON.stringify(r.error || r.result.exceptionDetails)));
    else p.resolve(r.result);
  };
  const call = (method, params = {}) => new Promise((resolve, reject) => { const id = ++seq; pending.set(id, {resolve, reject}); ws.send(JSON.stringify({id, method, params})); });
  const evaluate = async expression => (await call('Runtime.evaluate', {expression, awaitPromise:true, returnByValue:true})).result.value;
  const ready = async () => { for (let i = 0; i < 100; i++) { if (await evaluate('typeof window.runSnapshotBench') === 'function') return; await pause(50); } throw new Error('Fixture did not load'); };
  await call('Page.enable'); await call('Page.navigate', {url:'http://127.0.0.1:8787/index.html'}); await ready();
  return { tab, call, evaluate, ready };
}
(async () => {
  await new Promise(resolve => server.listen(8787, '127.0.0.1', resolve));
  browser = spawn('/usr/bin/chromium', ['--headless','--no-sandbox','--disable-gpu','--disable-dev-shm-usage',
    '--disable-background-networking','--no-first-run','--enable-precise-memory-info',
    '--user-data-dir='+fs.mkdtempSync('/tmp/aman-idb-browser-'),'--remote-debugging-port=9235','about:blank'], {stdio:'ignore'});
  let started = false;
  for (let i=0; i<100; i++) { try { await fetch('http://127.0.0.1:9235/json/version'); started=true; break; } catch { await pause(100); } }
  assert(started, 'Chromium CDP unavailable');
  const a = await page(), b = await page();
  await a.evaluate(`(async()=>{
    const base={pemilik:'qa',satkerAktif:'s1',statusKey:'asset',isEdit:true,editId:'asset',usePatch:true,baseVersion:5};
    await outbox.appendOperation({...base,antreanId:'first',idempotencyKey:'stable-first',payload:{photo_ops:{add:['p'.repeat(2*1024*1024)]}}},'tabA');
    await outbox.appendOperation({...base,antreanId:'second',idempotencyKey:'stable-second',payload:{asset_name:'Edit kedua'}},'tabA');
  })()`);
  const claims = await Promise.all([a.evaluate(`(async()=>{window.ticket=await outbox.claimOperation('qa','A');return !!window.ticket})()`),
    b.evaluate(`(async()=>{window.ticket=await outbox.claimOperation('qa','B');return !!window.ticket})()`)]);
  assert.equal(claims.filter(Boolean).length,1);
  const winner = claims[0] ? a : b, survivor = claims[0] ? b : a;
  await fetch('http://127.0.0.1:9235/json/close/'+winner.tab.id);
  await survivor.call('Page.reload'); await pause(100); await survivor.ready();
  await survivor.call('Network.enable');
  await survivor.call('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});
  const recovered = await survivor.evaluate(`(async()=>{
    const t=await outbox.claimOperation('qa','survivor',Date.now()+outbox.OUTBOX_LEASE_MS+10);
    const unchanged=t.idempotencyKey==='stable-first'&&t.baseVersion===5&&t.payload.photo_ops.add[0]==='p'.repeat(2*1024*1024);
    await outbox.acknowledgeOperation(t,{id:'asset',version:6});
    const next=await outbox.claimOperation('qa','survivor');
    const ordered=next.antreanId==='second'&&next.baseVersion===6&&next.payload.asset_name==='Edit kedua';
    await outbox.acknowledgeOperation(next,{id:'asset',version:7});
    return {unchanged,ordered,remaining:(await outbox.readOperations('qa')).items.length,photoBytes:2*1024*1024};
  })()`);
  assert(recovered.unchanged && recovered.ordered); assert.equal(recovered.remaining,0);
  const evidence={nativeIDB:true,twoRealTabs:true,claimWinners:1,closedSendingTab:true,reloadedSurvivor:true,offlineDuringRecovery:true,leaseExpiry:'simulated clock advance',...recovered};
  fs.mkdirSync(output,{recursive:true}); fs.writeFileSync(path.join(output,'outbox-native.json'),JSON.stringify(evidence,null,2)); console.log(JSON.stringify(evidence));
  await survivor.call('Network.emulateNetworkConditions',{offline:false,latency:0,downloadThroughput:-1,uploadThroughput:-1});
  const results=[];
  for (const count of [1000,10000,50000]) {
    await survivor.call('HeapProfiler.collectGarbage');
    const r=await survivor.evaluate(`runSnapshotBench(${count})`);
    await survivor.call('HeapProfiler.collectGarbage');
    r.retainedHeap=await survivor.evaluate('performance.memory.usedJSHeapSize');
    results.push(r); console.log(JSON.stringify(r));
    fs.writeFileSync(path.join(output,'snapshot-indexed.json'),JSON.stringify(results,null,2));
  }
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>{for(const ws of clients)ws.close();browser?.kill();server.close();});
