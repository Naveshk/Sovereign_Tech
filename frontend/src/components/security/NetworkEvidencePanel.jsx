import React,{useEffect,useState} from 'react';
import {Network,RefreshCw,ShieldCheck} from 'lucide-react';
import {networkEvidenceStatus,captureNetworkEvidence} from '../../services/api';

export default function NetworkEvidencePanel({user}){
 const [data,setData]=useState(null),[busy,setBusy]=useState(false),[error,setError]=useState('');
 const load=()=>networkEvidenceStatus().then(setData).catch(e=>setError(e.message||'Unable to read tcpdump status.'));
 useEffect(()=>{load()},[]);
 const capture=async()=>{setBusy(true);setError('');try{await captureNetworkEvidence({durationSeconds:10,packetCount:100,user});await load()}catch(e){setError(e.message||'Capture failed.')}finally{setBusy(false)}};
 const tcp=data?.tcpdump;
 return <section className="admin-panel">
   <div className="panel-header"><div><Network size={18}/><h2>Network Evidence</h2></div><button onClick={load} title="Refresh"><RefreshCw size={15}/></button></div>
   <p className="muted">Header-only tcpdump evidence for a short offline verification window. This does not by itself prove a permanent air gap.</p>
   <div className="status-grid">
    <div><span>tcpdump</span><strong>{tcp?.available?'AVAILABLE':'UNAVAILABLE'}</strong></div>
    <div><span>Platform</span><strong>{tcp?.platform||'—'}</strong></div>
   </div>
   {user?.role==='Manager'&&<button className="primary" disabled={busy||!tcp?.available} onClick={capture}>{busy?'Capturing…':'Capture 10s evidence'}</button>}
   {error&&<div className="error banner">{error}</div>}
   <div className="evidence-list">{(data?.recent_evidence||[]).map(x=><div className="evidence-row" key={x.filename}><ShieldCheck size={14}/><span>{x.filename}</span><small>{x.size_bytes} bytes</small></div>)}</div>
 </section>
}
