import React from 'react';
import MessageBubble from './MessageBubble';
import ExecutionSteps from './ExecutionSteps';
import TypingIndicator from './TypingIndicator';

export default function MessageList({messages, loading, steps}) {
  const safeMessages = Array.isArray(messages) ? messages.filter(Boolean) : [];
  return <div className="message-list">
    {safeMessages.map((m, index) => <MessageBubble key={m?.id || `message-${index}`} message={m}/>) }
    {loading && <div className="message-row assistant"><div className="message-avatar">✦</div><div className="bubble"><ExecutionSteps steps={steps}/><TypingIndicator/></div></div>}
  </div>;
}
