import React, {useEffect, useState} from 'react';
import {CheckCircle2, Copy, QrCode, ShieldCheck, XCircle} from 'lucide-react';
import {artifactSecurity, artifactVerify, artifactQrUrl, apiUrl} from '../../services/api';

export default function ArtifactSecurityPanel({draftId, user}) {
  const [security, setSecurity] = useState(null);
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  useEffect(() => {
    if (!draftId) return;
    setBusy(true);
    artifactSecurity(draftId, user.role)
      .then(data => { setSecurity(data); setMsg(''); })
      .catch(e => setMsg(e.message))
      .finally(() => setBusy(false));
  }, [draftId, user.role]);

  const verify = async () => {
    if (!security?.qr?.payload) return;
    setBusy(true);
    try {
      setResult(await artifactVerify(security.qr.payload, user.role));
      setMsg('');
    } catch (e) {
      setMsg(e.message);
    } finally {
      setBusy(false);
    }
  };

  const copyPayload = async () => {
    if (!security?.qr?.payload) return;
    try {
      await navigator.clipboard.writeText(security.qr.payload);
      setMsg('QR verification payload copied.');
    } catch {
      setMsg('Clipboard access is unavailable.');
    }
  };

  if (!draftId) return null;

  return (
    <div className="manager-card artifact-security-card">
      <div className="security-head">
        <div>
          <span className="eyebrow">ARTIFACT SECURITY</span>
          <h3>Integrity & Provenance</h3>
          <p>Local SHA-256, provenance and QR verification for the approved artifact.</p>
        </div>
        <QrCode size={24}/>
      </div>
      {busy && !security && <div className="empty-table">Loading security metadata…</div>}
      {msg && <div className="info-banner">{msg}</div>}
      {security && (
        <>
          <div className="security-grid">
            <div className="security-qr">
              <img src={artifactQrUrl(draftId, user.role)} alt="Artifact verification QR code"/>
              <span>Scan or copy the local verification payload.</span>
            </div>
            <div className="security-details">
              <div><small>Artifact</small><b>{security.artifact.filename}</b></div>
              <div><small>SHA-256</small><code>{security.artifact.sha256}</code></div>
              <div><small>Provenance ID</small><code>{security.provenance.provenance_id}</code></div>
              <div><small>Provenance SHA-256</small><code>{security.provenance.provenance_sha256}</code></div>
              <div><small>Draft</small><b>v{security.draft_version} · {security.draft_id}</b></div>
            </div>
          </div>
          <div className="security-actions">
            <button className="secondary small-btn" onClick={copyPayload}><Copy size={14}/> COPY QR PAYLOAD</button>
            <button className="primary small-btn" onClick={verify} disabled={busy}><ShieldCheck size={14}/> VERIFY LOCALLY</button>
          </div>
          {result && (
            <div className={`security-result ${result.valid ? 'valid' : 'invalid'}`}>
              {result.valid ? <CheckCircle2 size={17}/> : <XCircle size={17}/>}
              <div>
                <strong>{result.valid ? 'Verification passed' : 'Verification failed'}</strong>
                <span>{result.message}</span>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
