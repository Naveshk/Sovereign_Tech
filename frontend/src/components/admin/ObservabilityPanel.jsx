import {useEffect,useState} from 'react';
import {Activity,RefreshCw} from 'lucide-react';
import {observability} from '../../services/api';

export default function ObservabilityPanel({user}){
  const [data,setData]=useState(null),[error,setError]=useState('');
  const load=()=>observability(user).then(setData).catch(e=>setError(e.message||'Unable to load observability.'));
  useEffect(()=>{load()},[user?.role]);
  const metrics=data?.metrics||{};
  return <section className="admin-panel">
    <div className="panel-header"><div><h2><Activity size={18}/> Workflow Observability</h2><p>Local in-memory latency and operational metrics. No prompts or document contents are recorded.</p></div><button onClick={load} className="secondary"><RefreshCw size={15}/> Refresh</button></div>
    {error&&<div className="error banner">{error}</div>}
    {!Object.keys(metrics).length&&!error?<div className="empty-state">No workflow metrics recorded yet.</div>:<div className="artifact-grid">
      {Object.entries(metrics).map(([name,m])=><article className="artifact-card" key={name}>
        <strong>{name.replaceAll('.',' · ')}</strong>
        <div className="artifact-meta">Count: {m.count} · Success: {m.success} · Errors: {m.errors}</div>
        <div className="artifact-meta">Avg: {m.latency_ms?.avg ?? '—'} ms · P95: {m.latency_ms?.p95 ?? '—'} ms · Max: {m.latency_ms?.max ?? '—'} ms</div>
        {m.last?.model_id&&<div className="artifact-meta">Model: {m.last.model_id}</div>}
      </article>)}
    </div>}
  </section>;
}
