import React, { useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import axios from 'axios';
import VirtualizedMobileCards from '../../frontend/src/components/assets/VirtualizedMobileCards.jsx';
import AssetGalleryView from '../../frontend/src/components/assets/AssetGalleryView.jsx';
import { TooltipProvider } from '../../frontend/src/components/ui/tooltip.jsx';
import { buatCacheHalamanAset } from '../../frontend/src/lib/cacheHalamanAset.js';
import { buatPemuatDaftarAset } from '../../frontend/src/lib/pemuatDaftarAset.js';
import { usePenjagaPermintaan } from '../../frontend/src/hooks/usePenjagaPermintaan.js';
import { usePosisiDaftarAset } from '../../frontend/src/hooks/usePosisiDaftarAset.js';
const requests=[];
axios.get=async(url)=>{const page=Number(new URL(url,'http://test').searchParams.get('page'))||1;requests.push(page);return{data:{items:Array.from({length:50},(_,i)=>({id:`p${page}-${i}`,version:1,asset_code:`Kode ${page}-${i}`,asset_name:`Kursi ${page}-${i}`,status:'Aktif',condition:'Baik',inventory_status:'Ditemukan',notes:'a'.repeat(4000),activity_id:'qa'})),page,total:10000,total_pages:200}};};
function App(){
 const[assets,setAssets]=useState([]),[first,setFirst]=useState(1),[last,setLast]=useState(1),[busy,setBusy]=useState(false),[draft,setDraft]=useState('Draft tetap'),[selected,setSelected]=useState(new Set(['p1-0']));
 const cache=useMemo(()=>buatCacheHalamanAset(),[]),guard=usePenjagaPermintaan('qa'),main=useRef(null),list=useRef(null),history=useRef([]);
 const{daftarkan,rekamPosisi}=usePosisiDaftarAset(main,list);
 const loader=buatPemuatDaftarAset({activity:{id:'qa'},filters:{},isOnlineRef:{current:true},getPendingItems:()=>[],serverHasPendingRow:(a,b)=>a.id===b.id,
  mobilePageCache:cache,mobileLoading:busy,mobileCurrentPage:last,mobileFirstPage:first,totalPages:200,pageSize:50,debouncedSearch:'',filterCategory:[],sortBy:'newest',
  penjaga:guard,lingkupPermintaan:'qa',buildFilterParams:()=>{},setAssets:()=>{},setTotalItems:()=>{},setTotalPages:()=>{},setCurrentPage:()=>{},setStats:()=>{},
  setMobileAssets:setAssets,setMobileCurrentPage:setLast,setMobileFirstPage:setFirst,setMobileLoading:setBusy,setOfflineLastSync:()=>{},setOfflineServed:()=>{},setLoadingMessage:()=>{},sebelumGantiJendela:()=>rekamPosisi(true)});
 useEffect(()=>{loader.doFetch(1,50,'',[],'newest');},[]);
 useEffect(()=>{history.current.push({...cache.metrics(),first,last});window.qa={...cache.metrics(),busy,sibuk:guard.sibuk("mobile"),first,last,assets:assets.map(a=>a.id),draft,selected:[...selected],requests:[...requests],history:history.current};
  window.qaMore=loader.loadMoreMobile;window.qaPrev=loader.loadPrevMobile;window.qaRefresh=()=>loader.doFetchJendela(1,50,'',[],'newest');});
 const props={daftarkanGulir:daftarkan,assets,onVisibleAssets:cache.setVisible,onLoadMore:loader.loadMoreMobile,onLoadPrev:loader.loadPrevMobile,hasPrev:first>1,hasMore:last<200,isLoadingMore:busy,totalItems:10000,selectedAssets:selected,onToggleSelect:id=>setSelected(prev=>{const next=new Set(prev);next.has(id)?next.delete(id):next.add(id);return next;})};
 return<TooltipProvider><main ref={main}><input aria-label="Draf QA" value={draft} onChange={e=>setDraft(e.target.value)}/><div ref={list}>{location.search.includes('gallery')?<AssetGalleryView {...props}/>:<VirtualizedMobileCards {...props}/>}</div></main></TooltipProvider>;
}
createRoot(document.getElementById('root')).render(<App/>);
