import {useEffect,useState} from 'react';
import {Users} from 'lucide-react';
import Layout from '../components/Layout';
import {ErrorBox,Page} from '../components/Shared';
import {api,user as currentUser} from '../services/api';
import type {Role,User} from '../types';

export default function AdminUsers(){
  const [users,setUsers]=useState<User[]>([]),[error,setError]=useState(''),[busy,setBusy]=useState('');
  const load=()=>api<User[]>('/admin/users').then(setUsers).catch(e=>setError(e.message));
  useEffect(()=>{void load()},[]);
  async function change(id:string,role:Role){setBusy(id);setError('');try{await api(`/admin/users/${id}/role`,{method:'PATCH',body:JSON.stringify({role})});await load()}catch(e){setError((e as Error).message)}finally{setBusy('')}}
  return <Layout><Page><p className="eyebrow">Access management</p><h1 className="mt-2 text-4xl font-extrabold">People & roles</h1><p className="mt-3 text-slate-600">Assign operational access within your institution. Every change is audited.</p><ErrorBox message={error}/><div className="card mt-10 overflow-hidden"><div className="border-b p-6"><h2 className="flex items-center gap-2 text-xl font-bold"><Users className="text-forest"/>Institution users</h2></div><div className="divide-y">{users.map(person=><div className="flex flex-col justify-between gap-4 p-5 sm:flex-row sm:items-center" key={person.id}><div><p className="font-bold">{person.name}{person.id===currentUser()?.id&&<span className="ml-2 text-xs text-slate-400">You</span>}</p><p className="mt-1 text-sm text-slate-500">{person.email}</p></div><label className="flex items-center gap-3"><span>Role</span><select aria-label={`Role for ${person.name}`} className="field !mt-0 !w-40" value={person.role} disabled={busy===person.id||person.id===currentUser()?.id} onChange={e=>change(person.id,e.target.value as Role)}><option value="USER">User</option><option value="OFFICER">Officer</option><option value="ADMIN">Administrator</option></select></label></div>)}</div></div></Page></Layout>
}
