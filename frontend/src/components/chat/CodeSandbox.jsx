import React, {useMemo, useState} from 'react';
import {executeSandbox} from '../../services/api';
import {Check, Copy, Download, Terminal, Play, Loader2} from 'lucide-react';

function parseCode(content = '') {
  const blocks = [];
  const re = /```([\w#+.-]*)\s*\n?([\s\S]*?)```/g;
  let last = 0;
  let match;
  while ((match = re.exec(content))) {
    if (match.index > last) blocks.push({type: 'text', value: content.slice(last, match.index)});
    blocks.push({type: 'code', language: match[1] || 'text', value: match[2].replace(/^\n/, '').trimEnd()});
    last = re.lastIndex;
  }
  if (last < content.length) blocks.push({type: 'text', value: content.slice(last)});
  return blocks.length ? blocks : [{type: 'text', value: content}];
}

export default function CodeSandbox({content, user}) {
  const blocks = useMemo(() => parseCode(content), [content]);
  const [copied, setCopied] = useState(null);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState(null);

  const copy = async (value, index) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(index);
      setTimeout(() => setCopied(null), 1200);
    } catch {}
  };

  const download = (value, language) => {
    const ext = {python:'py', javascript:'js', typescript:'ts', java:'java', cpp:'cpp', c:'c', html:'html', css:'css', json:'json', bash:'sh', sh:'sh'}[language] || 'txt';
    const blob = new Blob([value], {type: 'text/plain;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `sovereign-code.${ext}`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return <div className="code-response">
    {blocks.map((block, i) => block.type === 'code' ? (
      <div className="code-sandbox" key={i}>
        <div className="code-sandbox-head">
          <span><Terminal size={14}/> Code Sandbox <small className="sandbox-secure-badge">Docker isolated</small></span>
          <span className="code-language">{block.language}</span>
          <div className="code-actions">
            <button onClick={() => copy(block.value, i)} title="Copy code">{copied === i ? <Check size={14}/> : <Copy size={14}/>}</button>
            <button onClick={() => download(block.value, block.language)} title="Download code"><Download size={14}/></button>
            {['python','py'].includes(block.language.toLowerCase())&&<button disabled={running} onClick={async()=>{setRunning(true);setRunResult(null);try{setRunResult(await executeSandbox({code:block.value,language:'python',timeout:10,user}))}catch(e){setRunResult({status:'error',error:e.message})}finally{setRunning(false)}}} title="Run in isolated Docker sandbox">{running?<Loader2 size={14} className="spin"/>:<Play size={14}/>}</button>}
          </div>
        </div>
        <pre><code>{block.value}</code></pre>
        {runResult&&<div className={`sandbox-result ${runResult.status}`}><strong>Sandbox: {runResult.status.toUpperCase()}</strong><div>Network: {runResult.network||'disabled'} · Exit: {runResult.exit_code ?? '—'} · {runResult.duration ?? 0}s</div>{runResult.stdout&&<pre>{runResult.stdout}</pre>}{runResult.stderr&&<pre>{runResult.stderr}</pre>}{runResult.error&&<div>{runResult.error}</div>}</div>}
      </div>
    ) : <div className="response-text" key={i}>{block.value}</div>)}
  </div>;
}
