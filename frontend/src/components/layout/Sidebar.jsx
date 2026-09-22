import React from 'react';
import {Activity, Archive, KeyRound, LogOut, Network, Plus, UserRound} from 'lucide-react';
import Logo from './Logo';

export default function Sidebar({onNewChat, conversations, onOpen, user, onLogout, activeId}) {
  const manager = user?.role === 'Manager';
  const safeConversations = Array.isArray(conversations)
    ? conversations.filter(c => c?.id && !String(c.id).startsWith('__'))
    : [];

  return <aside className="sidebar">
    <Logo/>
    <button className="new-chat" onClick={onNewChat}><Plus size={18}/>New Chat</button>

    <div className="history">
      <div className="side-label">Recent Chats</div>
      {safeConversations.length ? safeConversations.map((c, index) => (
        <button
          key={c.id || index}
          className={`history-item ${activeId===c.id?'active':''}`}
          onClick={()=>onOpen(c.id)}
          title={c.title || 'Conversation'}
        >
          <span>{c.title || 'Conversation'}</span>
          <small>{c.messageCount ?? (Array.isArray(c.messages) ? c.messages.length : 0)} messages</small>
        </button>
      )) : (
        <div className="history-empty">No previous chats yet</div>
      )}
    </div>

    {manager && <div className="side-section manager-links">
      <div className="side-label">Manager</div>
      <button className={`side-link ${activeId==='__observability__'?'active':''}`} onClick={()=>onOpen('__observability__')}><Activity size={18}/>Observability</button>
      <button className={`side-link ${activeId==='__encryption__'?'active':''}`} onClick={()=>onOpen('__encryption__')}><KeyRound size={18}/>Security / Encryption</button>
      <button className={`side-link ${activeId==='__network__'?'active':''}`} onClick={()=>onOpen('__network__')}><Network size={18}/>Network Evidence</button>
      <button className={`side-link ${activeId==='__artifacts__'?'active':''}`} onClick={()=>onOpen('__artifacts__')}><Archive size={18}/>Artifact Library</button>
    </div>}

    <div className="profile-card">
      <div className="avatar"><UserRound size={19}/></div>
      <div className="profile-text"><b>{user?.username || 'User'}</b><span>{user?.role || 'User'}</span></div>
      <button className="icon-button" onClick={onLogout} title="Logout"><LogOut size={18}/></button>
    </div>
  </aside>;
}
