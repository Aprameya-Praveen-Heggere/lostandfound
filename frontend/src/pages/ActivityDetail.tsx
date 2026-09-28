import {useEffect,useState} from 'react';
import {Calendar,CheckCircle2,MapPin,PackageSearch,RefreshCw} from 'lucide-react';
import {Link,useParams} from 'react-router-dom';
import Layout from '../components/Layout';
import {Back,ErrorBox,Page,Status} from '../components/Shared';
import {api} from '../services/api';
import type {FoundItem,LostReport} from '../types';

export default function ActivityDetail({mode}:{mode:'lost'|'found'}){
 const {id}=useParams();
 const [item,setItem]=useState<LostReport|FoundItem>(),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 useEffect(()=>{setItem(undefined);setError('');api<LostReport|FoundItem>(`/${mode==='lost'?'lost-reports':'found-items'}/${id}`).then(setItem).catch(e=>setError(e.message))},[id,mode]);
 async function changeStatus(next:'OPEN'|'CLOSED'|'RECOVERED'){
  setBusy(true);setError('');
  try{setItem(await api<LostReport>(`/lost-reports/${id}/status`,{method:'PATCH',body:JSON.stringify({status:next})}))}
  catch(e){setError((e as Error).message)}finally{setBusy(false)}
 }
 return <Layout><Page narrow><Back to="/dashboard"/><ErrorBox message={error}/>
  {!item&&!error?<div className="card p-12 text-center text-slate-500">Loading report…</div>:item&&<>
   <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start"><div><p className="eyebrow">{item.reference}</p><h1 className="mt-2 text-4xl font-extrabold">{item.name}</h1><p className="mt-2 text-slate-500">{item.category.name}</p></div><Status value={item.status}/></div>
   <section className="card mt-8 p-6 sm:p-8"><p className="text-slate-600">{item.description||'No description was provided.'}</p><div className="mt-6 grid gap-4 rounded-xl bg-cream p-5 sm:grid-cols-2"><p className="flex items-center gap-2"><MapPin size={18} className="text-forest"/><span><strong>{mode==='lost'?'Last seen':'Found at'}:</strong> {item.location}</span></p><p className="flex items-center gap-2"><Calendar size={18} className="text-forest"/><span><strong>Date:</strong> {new Date(mode==='lost'?(item as LostReport).date_lost:(item as FoundItem).date_found).toLocaleDateString()}</span></p>{item.color&&<p><strong>Color:</strong> {item.color}</p>}{item.brand&&<p><strong>Brand/type:</strong> {item.brand}</p>}{mode==='found'&&<p className="sm:col-span-2"><strong>Current custody:</strong> {(item as FoundItem).custody}</p>}</div>
    <div className="mt-6 border-t pt-6"><h2 className="text-lg font-bold">Available actions</h2>{mode==='lost'?<div className="mt-4 flex flex-wrap gap-3">{item.status==='OPEN'&&<><Link className="btn-primary" to={`/lost/${item.id}/matches`}><PackageSearch size={18}/>View possible matches</Link><button type="button" disabled={busy} className="btn-secondary" onClick={()=>changeStatus('RECOVERED')}><CheckCircle2 size={18}/>I recovered this item</button><button type="button" disabled={busy} className="btn-secondary" onClick={()=>changeStatus('CLOSED')}>Stop searching</button></>}{item.status==='CLOSED'&&<button type="button" disabled={busy} className="btn-primary" onClick={()=>changeStatus('OPEN')}><RefreshCw size={18}/>Reopen report</button>}{item.status==='RECOVERED'&&<p className="rounded-xl bg-mint p-4 text-sm text-forest">This report is complete because the item was marked recovered.</p>}</div>:<div className="mt-4 flex flex-wrap gap-3"><Link className="btn-primary" to={`/lost/discover?category=${item.category_id}`}><PackageSearch size={18}/>Browse similar found items</Link><p className="w-full text-sm text-slate-500">Status and custody changes are handled by an authorized lost-and-found officer.</p></div>}</div>
   </section>
  </>}
 </Page></Layout>
}
