import React from 'react';
import {Check, LoaderCircle, Circle} from 'lucide-react';

export default function ExecutionSteps({steps}) {
  const safeSteps = Array.isArray(steps) ? steps.filter(Boolean) : [];
  if (!safeSteps.length) return null;
  return <div className="execution">
    <div className="execution-title">Backend execution</div>
    {safeSteps.map((s, index) => {
      const key = s?.key || `step-${index}`;
      const status = s?.status || 'pending';
      return <div className="exec-step" key={key}>
        <span className={status === 'completed' ? 'done' : status === 'running' ? 'running' : 'pending'}>
          {status === 'completed' ? <Check size={13}/> : status === 'running' ? <LoaderCircle size={13}/> : <Circle size={10}/>} 
        </span>
        <span>{s?.label || 'Processing step'}</span>
        {s?.model && <small title={s?.ollama_model || s.model}>{s.model}</small>}
      </div>;
    })}
  </div>;
}
