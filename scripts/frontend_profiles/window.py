import json,time,argparse
from pathlib import Path
import requests
from websockets.sync.client import connect
parser=argparse.ArgumentParser();parser.add_argument('--cdp',type=int,default=9224);parser.add_argument('--port',type=int,default=8787);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();args.out.mkdir(parents=True,exist_ok=True)
page=next(p for p in requests.get(f'http://127.0.0.1:{args.cdp}/json/list').json() if p['type']=='page')
with connect(page['webSocketDebuggerUrl'],origin=f'http://localhost:{args.cdp}',open_timeout=5,max_size=20*1024*1024) as ws:
 seq=0
 def call(method,params=None):
  global seq
  seq+=1;ident=seq;ws.send(json.dumps({'id':ident,'method':method,'params':params or {}}))
  while True:
   d=json.loads(ws.recv(timeout=60))
   if d.get('id')==ident:
    assert 'error' not in d,d
    r=d.get('result',{});assert 'exceptionDetails' not in r,r
    return r
 def ev(expr,wait=False):return call('Runtime.evaluate',{'expression':expr,'awaitPromise':wait,'returnByValue':True})['result'].get('value')
 call('Page.enable');call('Page.bringToFront');call('Emulation.setDeviceMetricsOverride',{'width':360,'height':800,'deviceScaleFactor':1,'mobile':False})
 out=[]
 for mode,sel in [('mobile','mobile-cards-scroll'),('gallery','gallery-grid')]:
  call('Page.navigate',{'url':f'http://127.0.0.1:{args.port}/mobile.html?mode='+mode})
  for _ in range(100):
   if ev('window.qa?.assets?.length || 0'):break
   time.sleep(.05)
  t=time.monotonic()
  expr='''(async()=>{const el=document.querySelector('[data-testid="%s"]');let stagnant=0,prior=0;for(let i=0;i<2500&&window.qa.last<200;i++){el.scrollTop=el.scrollHeight;el.dispatchEvent(new Event('scroll'));await new Promise(r=>setTimeout(r,60));if(window.qa.last===prior)stagnant++;else stagnant=0;prior=window.qa.last;if(stagnant>300)throw new Error('stuck down '+JSON.stringify({...window.qa,history:undefined,assets:undefined}));}await new Promise(r=>setTimeout(r,50));return{...window.qa,history:undefined,requests:undefined,maxPages:Math.max(...window.qa.history.map(x=>x.pages)),maxBytes:Math.max(...window.qa.history.map(x=>x.bytes)),domCards:document.querySelectorAll('[data-scroll-asset-id]').length};})()'''%sel
  down=ev(expr,True);assert down['last']==200,down
  anchor="""(()=>{const el=document.querySelector('[data-testid="%s"]');return [...el.querySelectorAll('[data-scroll-asset-id]')].find(x=>x.getBoundingClientRect().bottom>el.getBoundingClientRect().top)?.dataset.scrollAssetId})()"""%sel
  before=ev(anchor);n=ev('window.qa.requests.length');ev('window.qaRefresh()',True);time.sleep(.15)
  refresh={'before':before,'after':ev(anchor),'requestedPages':ev('window.qa.requests.slice(%s)'%n)}
  assert refresh['before']==refresh['after'],refresh
  assert len(refresh['requestedPages'])<=4,refresh
  up=ev('''(async()=>{const el=document.querySelector('[data-testid="%s"]');let stagnant=0,prior=0;for(let i=0;i<2500&&window.qa.first>1;i++){el.scrollTop=0;el.dispatchEvent(new Event('scroll'));await new Promise(r=>setTimeout(r,60));if(window.qa.first===prior)stagnant++;else stagnant=0;prior=window.qa.first;if(stagnant>300)throw new Error('stuck up '+JSON.stringify({...window.qa,history:undefined,assets:undefined}));}return{...window.qa,history:undefined,requests:undefined,maxPages:Math.max(...window.qa.history.map(x=>x.pages)),maxBytes:Math.max(...window.qa.history.map(x=>x.bytes)),domCards:document.querySelectorAll('[data-scroll-asset-id]').length};})()'''%sel,True)
  assert up['first']==1,up
  assert down['maxPages']<=6 and up['maxPages']<=6 and up['maxBytes']<=8*1024*1024,(down,up)
  assert up['draft']=='Draft tetap' and up['selected']==['p1-0'],up
  item={'mode':mode,'elapsedSeconds':round(time.monotonic()-t,2),'down':down,'refresh':refresh,'up':up};out.append(item)
  args.out.joinpath('window-results.json').write_text(json.dumps(out,indent=2));print(json.dumps(item),flush=True)
