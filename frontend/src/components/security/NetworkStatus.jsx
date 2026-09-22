import React,{useEffect,useState} from 'react';
import {ShieldCheck,WifiOff} from 'lucide-react';
import {networkStatus} from '../../services/api';
export default function NetworkStatus(){
 const [data,setData]=useState(null);
 useEffect(()=>{let active=true;const load=()=>networkStatus().then(x=>active&&setData(x)).catch(()=>active&&setData(null));load();const id=setInterval(load,10000);return()=>{active=false;clearInterval(id)}},[]);
 const safe=data?.air_gapped, c=data?.controls;
 return <div className={`network-status ${safe?'safe':'unknown'}`} title={data?.evidence_note||''}>
  {safe?<ShieldCheck size={14}/>:<WifiOff size={14}/>}<span>{safe?'Sovereignty protected':'Network status unavailable'}</span>
  {data&&<small>External: {data.external_connections} · Sandbox: {data.sandbox_network} · Cloud: {c?.cloud_calls?.status||'UNKNOWN'} · Firewall: {c?.host_firewall?.status||'UNKNOWN'}</small>}
 </div>;
}
