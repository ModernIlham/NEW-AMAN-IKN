import json, time, argparse
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
            data=json.loads(ws.recv(timeout=60))
            if data.get('id')==ident:
                assert 'error' not in data,data
                result=data.get('result',{})
                assert 'exceptionDetails' not in result,result
                return result
    call('Page.enable');call('Page.navigate',{'url':f'http://127.0.0.1:{args.port}/index.html'})
    for _ in range(100):
        ready=call('Runtime.evaluate',{'expression':'typeof window.runSnapshotBench','returnByValue':True})['result'].get('value')
        if ready=='function':break
        time.sleep(.1)
    results=[]
    for count in [1000,10000,50000]:
        call('HeapProfiler.collectGarbage')
        result=call('Runtime.evaluate',{'expression':f'window.runSnapshotBench({count})','awaitPromise':True,'returnByValue':True})['result']['value']
        call('HeapProfiler.collectGarbage')
        result['retainedHeap']=call('Runtime.evaluate',{'expression':'performance.memory.usedJSHeapSize','returnByValue':True})['result']['value']
        results.append(result);print(json.dumps(result),flush=True)
        args.out.joinpath('snapshot-results.json').write_text(json.dumps(results,indent=2))
