import React, {useEffect, useState} from 'react';
import {Archive, CheckCircle2, Download, FileCheck2, RefreshCw, ShieldCheck, XCircle} from 'lucide-react';
import {artifactLibrary, artifactVerifyLocal, apiUrl} from '../../services/api';

async function hashFile(file) {
  const buffer = await file.arrayBuffer();
  const digest = await crypto.subtle.digest('SHA-256', buffer);
  return Array.from(new Uint8Array(digest)).map(b => b.toString(16).padStart(2, '0')).join('');
}

export default function ArtifactLibrary({user}) {
  const [artifacts, setArtifacts] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');
  const [results, setResults] = useState({});

  const refresh = async () => {
    setBusy(true);
    try {
      const data = await artifactLibrary(user.role);
      setArtifacts(data.artifacts || []);
      setMsg('');
    } catch (e) { setMsg(e.message); }
    finally { setBusy(false); }
  };
  useEffect(() => { refresh(); }, [user.role]);

  const verifyStored = async (item) => {
    setBusy(true);
    try {
      const result = await artifactVerifyLocal(item.draft_id, user.role);
      setResults(r => ({...r, [item.draft_id]: result}));
      setMsg('');
    } catch (e) { setMsg(e.message); }
    finally { setBusy(false); }
  };

  const verifyOfflineFile = async (item, event) => {
    const file = event.target.files?.[0];
    event.target.value = '';
    if (!file) return;
    try {
      const actual = await hashFile(file);
      const valid = file.name === item.filename && actual === item.sha256;
      setResults(r => ({...r, [item.draft_id]: {
        valid, status: valid ? 'verified' : 'mismatch',
        message: valid ? 'Downloaded file matches the recorded SHA-256.' : 'Filename or SHA-256 does not match the library record.',
        artifact: {...item, current_sha256: actual, hash_matches: actual === item.sha256, file_exists: true}
      }}));
    } catch (e) { setMsg(`Offline verification failed: ${e.message}`); }
  };

  return <section className="manager-panel artifact-library-panel">
    <div className="manager-head">
      <div>
        <span className="eyebrow">LOCAL ARTIFACT LIBRARY</span>
        <h2>Final Artifacts</h2>
        <p>Approved artifacts stored in the local workbench. No cloud storage or external verification is used.</p>
      </div>
      <button className="icon-button" onClick={refresh} disabled={busy}><RefreshCw size={18}/></button>
    </div>
    {msg && <div className="info-banner">{msg}</div>}
    {!artifacts.length && !busy && <div className="manager-card empty-table"><Archive size={22}/><div>No final artifacts in the local library yet.</div></div>}
    <div className="artifact-library-list">
      {artifacts.map(item => {
        const result = results[item.draft_id];
        return <div className="manager-card artifact-library-card" key={item.draft_id}>
          <div className="artifact-library-head">
            <div><div className="review-title"><Archive size={15}/> {item.title}</div><small>{item.filename} · Draft v{item.draft_version} · {item.artifact_type?.toUpperCase()}</small></div>
            <span className="verified-pill"><ShieldCheck size={12}/> LOCAL</span>
          </div>
          <div className="artifact-library-grid">
            <div><small>SHA-256</small><code>{item.sha256}</code></div>
            <div><small>Provenance</small><code>{item.provenance_id}</code></div>
            <div><small>Generated</small><b>{item.generated_at ? new Date(item.generated_at).toLocaleString() : 'Local record'}</b></div>
            <div><small>Review</small><b>#{item.review_id ?? '—'} · {item.reviewer_role || 'authorized reviewer'}</b></div>
          </div>
          <div className="artifact-library-actions">
            <a className="secondary small-btn" href={apiUrl(item.download_url?.replace(/^\/api/, '') || `/files/${encodeURIComponent(item.filename)}`)} target="_blank" rel="noreferrer"><Download size={14}/> DOWNLOAD</a>
            <button className="secondary small-btn" onClick={() => verifyStored(item)} disabled={busy}><FileCheck2 size={14}/> VERIFY STORED FILE</button>
            <label className="secondary small-btn"><ShieldCheck size={14}/> OFFLINE VERIFY<input type="file" hidden onChange={e => verifyOfflineFile(item, e)}/></label>
          </div>
          {result && <div className={`security-result ${result.valid ? 'valid' : 'invalid'}`}>{result.valid ? <CheckCircle2 size={17}/> : <XCircle size={17}/>}<div><strong>{result.valid ? 'Verification passed' : 'Verification failed'}</strong><span>{result.message}</span>{result.artifact?.current_sha256 && <code>{result.artifact.current_sha256}</code>}</div></div>}
        </div>;
      })}
    </div>
  </section>;
}
