
import React from 'react';import{Download,UserRound,Sparkles}from'lucide-react';import{apiUrl}from'../../services/api';import CodeSandbox from'./CodeSandbox';import ApprovalCard from './ApprovalCard';
function WorkflowSummary({state, taskType, files, approval}) {
  if (!state) return null;
  // Normal chat should end with the answer, not a wall of backend timings.
  // Keep workflow details for actual workbench tasks, artifacts, approvals and files.
  const isGeneral = !taskType || taskType === 'general';
  if (isGeneral && !files?.length && !approval) return null;
  const stages = (state.stages || []).filter(s => s && s.status !== 'pending');
  if (!stages.length && state.status !== 'error') return null;
  return <details className="workflow-summary">
    <summary>Execution details · {state.status || 'completed'}</summary>
    <div className="workflow-summary-items">
      {state.duration_ms != null && <span>{state.duration_ms} ms</span>}
      {stages.map(s => <span key={s.name}>{s.name} · {s.status}{s.duration_ms != null ? ` · ${s.duration_ms} ms` : ''}</span>)}
    </div>
  </details>;
}
function RichText({content=''}){const lines=content.replace(/\r/g,'').split('\n');return <div className="rich-text">{lines.map((line,i)=>{if(!line.trim())return <div className="rich-gap" key={i}/>;if(/^### /.test(line))return <h4 key={i}>{line.slice(4)}</h4>;if(/^## /.test(line))return <h3 key={i}>{line.slice(3)}</h3>;if(/^# /.test(line))return <h2 key={i}>{line.slice(2)}</h2>;if(/^\s*[-*] /.test(line))return <li key={i}>{line.replace(/^\s*[-*] /,'')}</li>;const parts=line.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);return <p key={i}>{parts.map((p,j)=>p.startsWith('**')?<strong key={j}>{p.slice(2,-2)}</strong>:p.startsWith('`')?<code key={j}>{p.slice(1,-1)}</code>:p)}</p>})}</div>}
export default function MessageBubble({message}){const user=message.role==='user',coding=message.taskType==='coding'||message.taskType==='multimodal_coding'||/```/.test(message.content||'');return <div className={`message-row ${user?'user':'assistant'}`}><div className="message-avatar">{user?<UserRound size={15}/>:<Sparkles size={15}/>}</div><div className="bubble">{coding&&!user?<CodeSandbox content={message.content} user={message.user}/>:<RichText content={message.content}/>} {message.fileName&&<div className="attachment">📎 {message.fileName}</div>}{message.model&&<div className="message-model">Local model · {message.model}</div>}{!user&&<WorkflowSummary state={message.workflowState} taskType={message.taskType} files={message.files} approval={message.approval}/>} {message.approval&&<ApprovalCard approval={message.approval} user={message.user}/>} {message.files?.map(f=>{const raw=f.download_url||`/files/${f.filename}`;const path=raw.startsWith('/api/')?raw.slice(4):raw.startsWith('/')?raw:('/'+raw);return <a className="download" key={f.filename} href={apiUrl(path)} target="_blank" rel="noreferrer" download={f.filename}><Download size={15}/>{f.title||f.filename}</a>})}</div></div>}
