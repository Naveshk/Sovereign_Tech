import React,{useEffect,useState} from 'react';
import {KeyRound,ShieldCheck,LockKeyhole} from 'lucide-react';
import {encryptionStatus} from '../../services/api';

export default function EncryptionStatusPanel({user}) {
  const [data,setData]=useState(null);
  const [error,setError]=useState('');
  useEffect(()=>{
    if(!user)return;
    encryptionStatus(user).then(setData).catch(e=>setError(e.message||'Unable to read encryption status.'));
  },[user?.employee_id,user?.employeeId,user?.username,user?.role]);
  return <div className="manager-card artifact-security-card">
    <div className="security-head">
      <div><span className="eyebrow">LOCAL KEY MANAGEMENT</span><h3>AES-256-GCM at Rest</h3>
      <p>Sensitive workflow data is encrypted locally. No cloud key service is required.</p></div>
      <KeyRound size={24}/>
    </div>
    {error&&<div className="info-banner">{error}</div>}
    {data&&<div className="security-grid">
      <div className="security-details">
        <div><small>Algorithm</small><b>{data.encryption.algorithm}</b></div>
        <div><small>Key ID</small><code>{data.encryption.key_id}</code></div>
        <div><small>Key source</small><b>{data.encryption.key_source}</b></div>
        <div><small>Mode</small><b>{data.encryption.offline?'Offline / local':'Unknown'}</b></div>
      </div>
      <div className="security-details">
        <div><small>Protected fields</small><b>{data.protected_storage.length} local stores</b></div>
        <div><small>Authentication</small><b><ShieldCheck size={14}/> Registered identity</b></div>
        <div><small>Encryption status</small><b><LockKeyhole size={14}/> Enabled</b></div>
      </div>
    </div>}
  </div>;
}
