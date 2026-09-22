import React, {useState} from 'react';
import {CheckCircle2, Download, LockKeyhole, RefreshCw, ShieldCheck, XCircle} from 'lucide-react';
import {apiUrl, decideHumanReview, rejectHumanReview} from '../../services/api';

function fileUrl(raw) {
  if (!raw) return '#';
  const path = raw.startsWith('/api/') ? raw.slice(4) : raw.startsWith('/') ? raw : `/${raw}`;
  return apiUrl(path);
}

function RichText({content=''}) {
  return <div className="rich-text">{String(content || '').replace(/\r/g,'').split('\n').map((line,i)=>{
    if(!line.trim()) return <div className="rich-gap" key={i}/>;
    if(/^### /.test(line)) return <h4 key={i}>{line.slice(4)}</h4>;
    if(/^## /.test(line)) return <h3 key={i}>{line.slice(3)}</h3>;
    if(/^# /.test(line)) return <h2 key={i}>{line.slice(2)}</h2>;
    if(/^\s*[-*] /.test(line)) return <li key={i}>{line.replace(/^\s*[-*] /,'')}</li>;
    return <p key={i}>{line}</p>;
  })}</div>;
}

export default function ApprovalCard({approval, user}) {
  const initial = approval || {};
  const [review, setReview] = useState(initial.review || null);
  const [draft, setDraft] = useState(initial.draft || initial.review?.draft || null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState(null);

  const pending = review?.status === 'pending';
  const title = draft?.title || review?.action || 'Deliverable review';
  const revision = draft?.version || review?.draft_version || 1;

  const identityMissing = !user?.employee_id && !user?.employeeId;

  const approve = async () => {
    if (!review?.id || busy || !pending || identityMissing) return;
    setBusy(true); setError(''); setDone(null);
    try {
      const result = await decideHumanReview(review.id, {
        role: user?.role,
        employee_id: user?.employee_id || user?.employeeId,
        username: user?.username,
        decision: 'approved',
        note: ''
      });
      setReview(result.review || {...review, status:'approved'});
      setDone(result.artifact || null);
      if (!result.artifact) setError('Approval was recorded, but no final artifact was returned.');
    } catch (e) {
      setError(e.message || 'Approval failed.');
    } finally { setBusy(false); }
  };

  const reject = async () => {
    if (!review?.id || busy || !pending || identityMissing) return;
    const feedback = window.prompt('Enter feedback for the next draft version:');
    if (!feedback || !feedback.trim()) return;
    setBusy(true); setError(''); setDone(null);
    try {
      const result = await rejectHumanReview(review.id, {
        role: user?.role,
        employee_id: user?.employee_id || user?.employeeId,
        username: user?.username,
        feedback: feedback.trim()
      });
      setReview(result.review || null);
      setDraft(result.draft || result.review?.draft || null);
    } catch (e) {
      setError(e.message || 'Revision failed.');
    } finally { setBusy(false); }
  };

  if (!review) return null;

  if (done) {
    return <section className="approval-card approval-complete">
      <div className="approval-head"><div><span className="eyebrow">HUMAN APPROVAL COMPLETED</span><h3><CheckCircle2 size={18}/> Approved</h3></div><ShieldCheck size={22}/></div>
      <p>Final artifact generated successfully after human approval.</p>
      <a className="download approval-download" href={fileUrl(done.download_url)} target="_blank" rel="noreferrer" download={done.filename}>
        <Download size={16}/> Download {done.filename}
      </a>
    </section>;
  }

  return <section className="approval-card">
    <div className="approval-head">
      <div>
        <span className="eyebrow">HUMAN APPROVAL REQUIRED</span>
        <h3><LockKeyhole size={18}/> {title}</h3>
      </div>
      <span className="pending-pill">REVISION {revision}</span>
    </div>
    <div className="approval-notice">This is a pre-deliverable verification gate. Final DOCX/artifact generation is blocked until you approve this draft.</div>
    <div className="approval-draft"><RichText content={draft?.content || 'Draft content is unavailable.'}/></div>
    {identityMissing && <div className="info-banner">Your authenticated account identity is required to review this draft.</div>}
    {error && <div className="error banner">{error}</div>}
    {pending && <div className="approval-actions">
      <button className="primary small-btn" disabled={busy || identityMissing} onClick={approve}>{busy ? <><RefreshCw size={14}/> Processing…</> : <><CheckCircle2 size={14}/> Accept & Generate DOCX</>}</button>
      <button className="danger-btn small-btn" disabled={busy || identityMissing} onClick={reject}><XCircle size={14}/> Reject & Revise</button>
    </div>}
  </section>;
}
