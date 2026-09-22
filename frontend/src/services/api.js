
const API_BASE=import.meta.env.VITE_API_BASE_URL||'http://127.0.0.1:8000/api';
export const apiUrl=p=>`${API_BASE}${p}`;
async function req(path,opts={}){const r=await fetch(apiUrl(path),{headers:{'Content-Type':'application/json',...(opts.headers||{})},...opts});if(!r.ok){let m=`Request failed (${r.status})`;try{m=(await r.json()).detail||m}catch{}throw new Error(m)}return r.json()}
export const health=()=>fetch(apiUrl('/health')).then(r=>{if(!r.ok)throw Error('Backend unavailable');return r.json()});
export const signup=d=>req('/auth/signup',{method:'POST',body:JSON.stringify(d)});
export const login=d=>req('/auth/login',{method:'POST',body:JSON.stringify(d)});
export const knowledgeStatus=()=>req('/knowledge/status');
export const managerFiles=role=>req(`/admin/files?role=${encodeURIComponent(role)}`);
export const auditLogs=role=>req(`/admin/audit?role=${encodeURIComponent(role)}`);
export function uploadKnowledge({file,user}){const fd=new FormData();fd.append('file',file);return new Promise((resolve,reject)=>{const x=new XMLHttpRequest();x.open('POST',apiUrl('/knowledge/upload'));x.setRequestHeader('X-Employee-ID',user.employee_id||user.employeeId||'');x.setRequestHeader('X-Role',user.role||'');x.onload=()=>{try{const d=JSON.parse(x.responseText);x.status>=200&&x.status<300?resolve(d):reject(Error(d.detail||'Upload failed'))}catch{reject(Error('Invalid server response'))}};x.onerror=()=>reject(Error('Network error'));x.send(fd)})}
export async function streamChat({message,conversationId,conversationHistory=[],file,user,onEvent,signal}){const fd=new FormData();fd.append('message',message||'');fd.append('conversation_id',conversationId||'');fd.append('conversation_history',JSON.stringify(conversationHistory||[]));if(file)fd.append('file',file);const r=await fetch(apiUrl('/chat/stream'),{method:'POST',body:fd,signal,headers:{'X-Employee-ID':user?.employee_id||user?.employeeId||'','X-Role':user?.role||''}});if(!r.ok)throw Error(await r.text()||`Request failed (${r.status})`);const reader=r.body.getReader(),dec=new TextDecoder();let buf='';while(true){const {value,done}=await reader.read();if(done)break;buf+=dec.decode(value,{stream:true});const chunks=buf.split('\n\n');buf=chunks.pop()||'';for(const chunk of chunks){const lines=chunk.split('\n');const ev=lines.find(x=>x.startsWith('event:'))?.slice(6).trim()||'message';const dl=lines.find(x=>x.startsWith('data:'));if(dl)try{onEvent(ev,JSON.parse(dl.slice(5)))}catch{}}}}

export const networkStatus=()=>req('/network/status');
export const networkControls=()=>req('/network/controls');
export const networkEvidenceStatus=()=>req('/network/evidence/status');
export const captureNetworkEvidence=({durationSeconds=10,packetCount=100,user})=>req(`/network/evidence/capture?duration_seconds=${durationSeconds}&packet_count=${packetCount}&employee_id=${encodeURIComponent(user?.employee_id||user?.employeeId||'')}&username=${encodeURIComponent(user?.username||'')}&role=${encodeURIComponent(user?.role||'')}`,{method:'POST'});
export async function executeSandbox({code,language='python',timeout=10,user}){return req('/sandbox/execute',{method:'POST',body:JSON.stringify({code,language,timeout}),headers:{'X-Employee-ID':user?.employee_id||user?.employeeId||'','X-Role':user?.role||''}});}

export const verifyAuditLedger=role=>req(`/admin/audit/verify?role=${encodeURIComponent(role)}`);
export const auditProvenance=({role,draftId,reviewId,provenanceId,artifactSha256})=>{const q=new URLSearchParams({role:role||''});if(draftId)q.set('draft_id',draftId);if(reviewId)q.set('review_id',reviewId);if(provenanceId)q.set('provenance_id',provenanceId);if(artifactSha256)q.set('artifact_sha256',artifactSha256);return req(`/admin/audit/provenance?${q.toString()}`)};
export const receiptUrl=(auditId,role)=>apiUrl(`/admin/audit/${auditId}/receipt.pdf?role=${encodeURIComponent(role)}`);

export const humanReviews=(role,status,employeeId='',username='')=>req(`/reviews?role=${encodeURIComponent(role)}&employee_id=${encodeURIComponent(employeeId||'')}&username=${encodeURIComponent(username||'')}${status?`&status=${encodeURIComponent(status)}`:''}`);
export const pendingHumanReviews=(role,employeeId='',username='')=>req(`/human-review/pending?role=${encodeURIComponent(role)}&employee_id=${encodeURIComponent(employeeId||'')}&username=${encodeURIComponent(username||'')}`);
export const decideHumanReview=(id,{role,employee_id,username,decision,note})=>req(`/human-review/${id}/approve?role=${encodeURIComponent(role)}&employee_id=${encodeURIComponent(employee_id||'')}&username=${encodeURIComponent(username||'')}`,{method:'POST'});
export const rejectHumanReview=(id,{role,employee_id,username,feedback})=>req(`/human-review/${id}/reject?role=${encodeURIComponent(role)}&employee_id=${encodeURIComponent(employee_id||'')}&username=${encodeURIComponent(username||'')}`,{method:'POST',body:JSON.stringify({feedback})});
export const rejectDraft=(id,{role,employee_id,username,feedback})=>rejectHumanReview(id,{role,employee_id,username,feedback});
export const draftVersions=(id,role)=>req(`/drafts/${encodeURIComponent(id)}/versions?role=${encodeURIComponent(role)}`);

export const artifactSecurity=(draftId,role)=>req(`/artifacts/${encodeURIComponent(draftId)}/security?role=${encodeURIComponent(role)}`);
export const artifactVerify=(payload,role)=>req(`/artifacts/verify?role=${encodeURIComponent(role)}`,{method:'POST',body:JSON.stringify({payload})});
export const artifactQrUrl=(draftId,role)=>apiUrl(`/artifacts/${encodeURIComponent(draftId)}/qr?role=${encodeURIComponent(role)}`);

export const artifactLibrary=role=>req(`/artifacts/library?role=${encodeURIComponent(role)}`);
export const artifactVerifyLocal=(draftId,role)=>req(`/artifacts/${encodeURIComponent(draftId)}/verify-local?role=${encodeURIComponent(role)}`,{method:'POST'});
export const artifactManifest=(draftId,role)=>req(`/artifacts/${encodeURIComponent(draftId)}/manifest?role=${encodeURIComponent(role)}`);

export const conversationList=(user)=>req('/conversations',{headers:{'X-Employee-ID':user?.employee_id||user?.employeeId||'','X-Role':user?.role||''}});
export const conversationMessages=(id,user)=>req(`/conversations/${encodeURIComponent(id)}/messages`,{headers:{'X-Employee-ID':user?.employee_id||user?.employeeId||'','X-Role':user?.role||''}});
export const createConversation=(title,user,conversationId)=>req('/conversations',{method:'POST',body:JSON.stringify({title,conversation_id:conversationId||null}),headers:{'X-Employee-ID':user?.employee_id||user?.employeeId||'','X-Role':user?.role||''}});
export const archiveConversation=(id,user)=>req(`/conversations/${encodeURIComponent(id)}`,{method:'DELETE',headers:{'X-Employee-ID':user?.employee_id||user?.employeeId||'','X-Role':user?.role||''}});

export const observability=user=>req('/observability',{headers:{'X-Employee-ID':user?.employee_id||user?.employeeId||'','X-Role':user?.role||''}});

export const encryptionStatus=user=>req(`/security/encryption?employee_id=${encodeURIComponent(user?.employee_id||user?.employeeId||'')}&username=${encodeURIComponent(user?.username||'')}&role=${encodeURIComponent(user?.role||'')}`);
