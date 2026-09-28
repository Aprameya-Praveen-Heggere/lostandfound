import type {User} from '../types'
const BASE=import.meta.env.VITE_API_URL||'/api/v1'
export const token=()=>localStorage.getItem('findora_token')
export const user=():User|null=>{try{return JSON.parse(localStorage.getItem('findora_user')||'null')}catch{return null}}
export function saveAuth(data:{access_token:string;user:User}){localStorage.setItem('findora_token',data.access_token);localStorage.setItem('findora_user',JSON.stringify(data.user))}
export function clearAuth(){localStorage.removeItem('findora_token');localStorage.removeItem('findora_user')}
export async function api<T>(path:string,options:RequestInit={}):Promise<T>{
 const headers=new Headers(options.headers);if(!(options.body instanceof FormData))headers.set('Content-Type','application/json');if(token())headers.set('Authorization',`Bearer ${token()}`)
 const response=await fetch(`${BASE}${path}`,{...options,headers});if(!response.ok){let message='Something went wrong';try{const body=await response.json();message=typeof body.detail==='string'?body.detail:body.detail?.[0]?.msg||message}catch{}throw new Error(message)}
 if(response.status===204)return undefined as T;return response.json()
}
