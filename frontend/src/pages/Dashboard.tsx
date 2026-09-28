import {useEffect,useState} from 'react';
import {ArrowRight,Bell,ClipboardList,PackageSearch} from 'lucide-react';
import {Link} from 'react-router-dom';
import Layout from '../components/Layout';
import {ErrorBox,Page,Status} from '../components/Shared';
import {api} from '../services/api';
import type {Claim,LostReport,FoundItem,Notification} from '../types';

export default function Dashboard(){
 const [data,setData]=useState<{lost:LostReport[];found:FoundItem[];claims:Claim[];notes:Notification[]}>({lost:[],found:[],claims:[],notes:[]});
 const [error,setError]=useState('');
 useEffect(()=>{Promise.all([api<LostReport[]>('/lost-reports/me'),api<FoundItem[]>('/found-items/me'),api<Claim[]>('/claims/me'),api<Notification[]>('/notifications/me')]).then(([lost,found,claims,notes])=>setData({lost,found,claims,notes})).catch(e=>setError(e.message))},[]);
 async function markRead(note:Notification){
  if(note.is_read)return;
  try{await api(`/notifications/${note.id}/read`,{method:'PATCH'});setData(current=>({...current,notes:current.notes.map(x=>x.id===note.id?{...x,is_read:true}:x)}))}
  catch(e){setError((e as Error).message)}
 }
 return <Layout><Page>
  <p className="eyebrow">Your Findora space</p><h1 className="mt-2 text-4xl font-extrabold">My activity</h1><p className="mt-3 text-slate-600">Open any report to see its details and available actions.</p><ErrorBox message={error}/>
  <section className="mt-10 grid gap-5 lg:grid-cols-3">
   <div className="card p-6 lg:col-span-2"><h2 className="flex items-center gap-2 text-xl font-bold"><ClipboardList className="text-forest"/>My claims</h2>{data.claims.length?<div className="mt-5 divide-y">{data.claims.map(c=><article className="py-4" key={c.id}><div className="flex items-start justify-between gap-3"><div><h3 className="font-bold">{c.found_item.name}</h3><p className="mt-1 text-sm text-slate-500">Submitted {new Date(c.created_at).toLocaleDateString()}</p></div><Status value={c.status}/></div>{c.rejection_reason&&<p className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">Reason: {c.rejection_reason}</p>}<Link className="mt-3 inline-flex items-center gap-1 text-sm font-bold text-forest hover:underline" to={`/activity/found/${c.found_item.id}`}>View claimed item <ArrowRight size={15}/></Link></article>)}</div>:<Empty text="You haven’t submitted any claims yet."/>}</div>
   <div className="card p-6"><h2 className="flex items-center gap-2 text-xl font-bold"><Bell className="text-amber"/>Updates</h2>{data.notes.length?<div className="mt-5 space-y-3">{data.notes.slice(0,5).map(n=><button type="button" key={n.id} onClick={()=>markRead(n)} disabled={n.is_read} className={`block w-full rounded-lg p-2 text-left transition ${!n.is_read?'border-l-2 border-amber bg-amber/5 hover:bg-amber/10':'cursor-default text-slate-500'}`}><span className="text-sm font-bold">{n.title}</span><span className="mt-1 block text-xs">{n.message}</span>{!n.is_read&&<span className="mt-2 block text-xs font-bold text-forest">Mark as read</span>}</button>)}</div>:<Empty text="No new updates."/>}</div>
  </section>
  <section className="mt-5 grid gap-5 lg:grid-cols-2"><ReportList mode="lost" title="My lost reports" items={data.lost}/><ReportList mode="found" title="My found reports" items={data.found}/></section>
 </Page></Layout>
}

function Empty({text}:{text:string}){return <div className="py-10 text-center text-sm text-slate-400"><PackageSearch className="mx-auto mb-3"/>{text}</div>}
function ReportList({title,items,mode}:{title:string;items:(LostReport|FoundItem)[];mode:'lost'|'found'}){
 return <div className="card p-6"><h2 className="text-xl font-bold">{title}</h2>{items.length?<div className="mt-5 divide-y">{items.map(i=><article key={i.id} className="flex flex-col justify-between gap-3 py-4 sm:flex-row sm:items-center"><div><p className="font-bold">{i.name}</p><p className="mt-1 font-mono text-xs text-slate-500">{i.reference}</p></div><div className="flex flex-wrap items-center gap-2 sm:justify-end"><Status value={i.status}/><Link className="btn-secondary !px-3 !py-2 text-xs" to={`/activity/${mode}/${i.id}`}>View details</Link>{mode==='lost'&&i.status==='OPEN'&&<Link className="btn-primary !px-3 !py-2 text-xs" to={`/lost/${i.id}/matches`}>Possible matches</Link>}</div></article>)}</div>:<Empty text="Nothing here yet."/>}</div>
}
