import { getSnapshotPage } from '../../frontend/src/lib/offlineSnapshot.js';
function openDatabase() {
  return new Promise((resolve,reject) => {
    const request=indexedDB.open('aman_offline_snapshot',2);
    request.onupgradeneeded=()=>{const db=request.result;const store=db.createObjectStore('assets',{keyPath:'id'});store.createIndex('by-activity','activity_id');db.createObjectStore('meta',{keyPath:'activityId'});};
    request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);
  });
}
function done(tx){return new Promise((resolve,reject)=>{tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);});}
window.runSnapshotBench=async(count)=>{
  const activityId='benchmark-'+count, db=await openDatabase();
  for(let i=0;i<count;i+=512){const tx=db.transaction('assets','readwrite');for(let j=i;j<Math.min(i+512,count);j++)tx.objectStore('assets').put({id:`${activityId}-${String(j).padStart(7,'0')}`,activity_id:activityId,
    asset_name:`Kursi ${j}`,purchase_price:`${100+j%20}.01`,created_at:'2026-10-15',purchase_date:'2026-09-15',
    condition:j%2?'Baik':'Rusak Ringan',status:j%3?'Aktif':'Maintenance',thumbnail:'data:image/jpeg;base64,'+'a'.repeat(4096)});await done(tx);}
  const tx=db.transaction('meta','readwrite');tx.objectStore('meta').put({activityId,userId:'synthetic-owner',lastSync:new Date().toISOString(),revision:1,count});await done(tx);db.close();
  const query={ownerId:'synthetic-owner',kodeSatker:'qa',search:'Kursi',filters:{condition:['Baik','Rusak Ringan'],priceMin:'110',dateFrom:'2026-09-03'},sort:'price_desc'};
  const before=performance.now();const first=await getSnapshotPage(activityId,query);const firstMs=performance.now()-before;
  const next=performance.now();const second=await getSnapshotPage(activityId,{...query,page:2});const secondMs=performance.now()-next;
  const changedStart=performance.now();const changed=await getSnapshotPage(activityId,{...query,filters:{...query.filters,priceMin:"115"}});const changedQueryMs=performance.now()-changedStart;
  return{count,firstMs,secondMs,changedQueryMs,changedQuery:changed.timing,first:first.timing,second:second.timing,total:first.total,firstID:first.items[0]?.id,page2ID:second.items[0]?.id,heap:performance.memory?.usedJSHeapSize,thumbnailBytes:4096};
};
