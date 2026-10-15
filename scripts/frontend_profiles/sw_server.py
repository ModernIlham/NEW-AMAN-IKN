import json,argparse,hashlib,base64
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8788);parser.add_argument('--out',type=Path,required=True);args=parser.parse_args();ROOT=args.out;ROOT.mkdir(parents=True,exist_ok=True);STATE=ROOT/'state.json';TEMPLATE=Path(__file__).resolve().parents[2]/'frontend/public/service-worker.js'
def static_body(path):
 part=path.rsplit('/',1)[-1].split('.');mod,version=part[:2]
 return f'window.appRelease={json.dumps(version)};' if mod=='main' else f'export const version={json.dumps(version)};' + ('\n/*'+'a'*1000000+'*/' if mod=='lazy' else '')
def release(i):
 assets=[f'/static/js/{k}.{i}.js' for k in ['main','editor','lightbox','lazy']]
 return {'id':i,'main':assets[0],'assets':assets,'critical':assets[:3], 'integrity':{file:'sha256-'+base64.b64encode(hashlib.sha256(static_body(file).encode()).digest()).decode() for file in assets}}
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  state=json.loads(STATE.read_text());i=state['release'];path=self.path.split('?')[0];r=release(i)
  if state.get('offline') or path in state.get('drop',[]):
   self.close_connection=True;return
  status=200;kind='application/javascript';cache='public,max-age=31536000,immutable'
  if path in state.get('failed',[]):status=404;body='missing'
  elif path=='/service-worker.js':body=TEMPLATE.read_text().replace('/* AMAN_LIGHTBOX_PRECACHE */ []',json.dumps([r['critical'][2]])).replace('/* AMAN_RELEASE_MANIFEST */ null',json.dumps(r));cache='no-cache'
  elif path=='/manifest.json':body='{}';kind='application/json'
  elif path.startswith('/static/js/'):
   body=static_body(path) + ('\n//wrong content' if path in state.get('corrupt',[]) else '')
  else:
   kind='text/html';cache='no-cache';body=f'''<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><input id="draft" value="Draft belum disimpan"><script src="{r['main']}"></script><script>
window.pin=()=>navigator.serviceWorker.controller?.postMessage({{type:'AMAN_PIN_RELEASE',main:'{r['main']}'}});
navigator.serviceWorker.addEventListener('controllerchange',pin);navigator.serviceWorker.addEventListener('message',e=>{{window.lastWorkerMessage=e.data;pin();}});
navigator.serviceWorker.register('/service-worker.js',{{updateViaCache:'none'}}).then(()=>navigator.serviceWorker.ready).then(pin);
window.queued=new Promise((resolve,reject)=>{{const q=indexedDB.open('aman-queued-fixture',1);q.onupgradeneeded=()=>q.result.createObjectStore('queue');q.onsuccess=()=>{{const tx=q.result.transaction('queue','readwrite');tx.objectStore('queue').put({{draft:'tetap'}},'saved');tx.oncomplete=()=>{{q.result.close();resolve(true)}};}};q.onerror=reject;}});
</script>'''
  self.send_response(status);self.send_header('Content-Type',kind);self.send_header('Cache-Control',cache);self.send_header('Content-Length',str(len(body.encode())));self.end_headers();self.wfile.write(body.encode())
 def log_message(self,*args):pass
STATE.write_text(json.dumps({'release':'aaa','failed':[]}))
ThreadingHTTPServer(('127.0.0.1',args.port),Handler).serve_forever()
