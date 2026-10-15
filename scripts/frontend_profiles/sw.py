import json,time,urllib.parse,argparse
from pathlib import Path
import requests
from websockets.sync.client import connect
parser=argparse.ArgumentParser();parser.add_argument('--cdp',type=int,default=9224);parser.add_argument('--port',type=int,default=8788);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();ROOT=args.out;ROOT.mkdir(parents=True,exist_ok=True);state=ROOT/'state.json';CDP=f'http://127.0.0.1:{args.cdp}';ORIGIN=f'http://127.0.0.1:{args.port}'
class Tab:
 def __init__(self,url):
  p=requests.put(CDP+'/json/new?'+urllib.parse.quote(url,safe=':/')).json();self.id=p['id'];self.ws=connect(p['webSocketDebuggerUrl'],origin=f'http://localhost:{args.cdp}',max_size=4000000);self.seq=0
  self.call('Page.enable');self.call('Network.enable');self.call('Page.bringToFront')
 def call(self,method,params=None):
  self.seq+=1;n=self.seq;self.ws.send(json.dumps({'id':n,'method':method,'params':params or {}}))
  while True:
   r=json.loads(self.ws.recv(timeout=40))
   if r.get('id')==n:
    assert 'error' not in r,r
    d=r.get('result',{});assert 'exceptionDetails' not in d,d
    return d
 def ev(self,s):return self.call('Runtime.evaluate',{'expression':s,'awaitPromise':True,'returnByValue':True})['result'].get('value')
 def wait(self,s,timeout=15):
  until=time.monotonic()+timeout
  while time.monotonic()<until:
   if self.ev(s):return
   time.sleep(.1)
  raise AssertionError('timeout '+s)
 def offline(self,on):self.call('Network.emulateNetworkConditions',{'offline':on,'latency':0,'downloadThroughput':-1,'uploadThroughput':-1})
def deploy(i,failed=[],offline=False,drop=[],corrupt=[]):state.write_text(json.dumps({'release':i,'failed':failed,'offline':offline,'drop':drop,'corrupt':corrupt}))
meta="(async()=>await(await(await caches.open('inventory-release-meta-v1')).match('/__aman_release_meta__')).json())()"
def marker(tab):return tab.ev(meta)['current']
results={};started=time.monotonic()
for p in requests.get(CDP+'/json/list').json():
 if p.get('url','').startswith(ORIGIN):requests.get(CDP+'/json/close/'+p['id'])
deploy('aaa');one=Tab('about:blank');one.call('Storage.clearDataForOrigin',{'origin':ORIGIN,'storageTypes':'all'});one.call('Page.navigate',{'url':ORIGIN+'/'})
one.wait("!!navigator.serviceWorker?.controller && window.appRelease==='aaa'");one.ev('window.queued');time.sleep(.2)
assert marker(one)=='aaa';results['firstColdInstall']=True
one.ev("document.querySelector('#draft').value='Draf tab pertama tetap'")
deploy('bbb');one.ev('(async()=>{await(await navigator.serviceWorker.getRegistration()).update();return true})()');one.wait("window.lastWorkerMessage?.releaseId==='bbb'")
two=Tab(ORIGIN+'/');two.wait("!!navigator.serviceWorker?.controller && window.appRelease==='bbb'");time.sleep(.2)
metadata=one.ev(meta);assert sorted(p['releaseId'] for p in metadata['pins'].values())==['aaa','bbb'],metadata
deploy('bbb',offline=True);editor=one.ev("import('/static/js/editor.aaa.js').then(m=>m.version)");lightbox=one.ev("import('/static/js/lightbox.aaa.js').then(m=>m.version)")
assert editor==lightbox=='aaa';assert one.ev("document.querySelector('#draft').value")=='Draf tab pertama tetap';results['oldTabUnseenEditorLightboxOffline']=True
two.call('Page.reload');two.wait("window.appRelease==='bbb' && !!navigator.serviceWorker?.controller");results['newReleaseOfflineColdReload']=True;deploy('bbb')
# New chunk404 cannot displace the valid active release.
deploy('ccc',['/static/js/editor.ccc.js']);one.ev('(async()=>{await(await navigator.serviceWorker.getRegistration()).update();return true})()');time.sleep(1)
assert marker(one)=='bbb';assert 'inventory-release-ccc' not in one.ev('caches.keys()');results['chunk404InstallRetainsPrevious']=True
# Offline update cannot replace the active worker/cache.
deploy('ddd',drop=['/static/js/editor.ddd.js'])
assert one.ev('(async()=>{try{await(await navigator.serviceWorker.getRegistration()).update();await new Promise(r=>setTimeout(r,500));return true}catch{return true}})()')
assert marker(one)=='bbb';deploy('bbb');results['interruptedUpdateRetainsPrevious']=True
# Correct MIME with wrong bytes is rejected by native Request integrity.
deploy('eee',corrupt=['/static/js/editor.eee.js']);one.ev('(async()=>{await(await navigator.serviceWorker.getRegistration()).update();await new Promise(r=>setTimeout(r,700));return true})()')
assert marker(one)=='bbb';assert 'inventory-release-eee' not in one.ev('caches.keys()');results['sriMismatchRetainsPrevious']=True;deploy('bbb')
# Native quota override blocks a new cache entry; successful network body still arrives.
one.call('Storage.overrideQuotaForOrigin',{'origin':ORIGIN,'quotaSize':1})
quota=one.ev("(async()=>{const r=await fetch('/static/js/lazy.bbb.js');await r.text();await new Promise(r=>setTimeout(r,300));return {ok:r.ok,cached:!!await(await caches.open('inventory-release-bbb')).match('/static/js/lazy.bbb.js')}})()")
assert quota['ok'] and not quota['cached'],quota;results['nativeQuotaPreservesNetworkResponse']=quota
one.call('Storage.overrideQuotaForOrigin',{'origin':ORIGIN})
queue=one.ev("new Promise((resolve,reject)=>{const q=indexedDB.open('aman-queued-fixture',1);q.onsuccess=()=>{const r=q.result.transaction('queue').objectStore('queue').get('saved');r.onsuccess=()=>{resolve(r.result);q.result.close()};r.onerror=reject};q.onerror=reject})")
assert queue=={'draft':'tetap'};results['idbQueueAndDraftPreserved']=True
results['releaseCaches']=one.ev('caches.keys()');results['pins']=one.ev(meta)['pins'];results['elapsedSeconds']=round(time.monotonic()-started,2)
ROOT.joinpath('sw-results.json').write_text(json.dumps(results,indent=2));print(json.dumps(results),flush=True)
one.ws.close();two.ws.close()
