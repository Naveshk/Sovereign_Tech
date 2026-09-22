export default function ConversationItem({conversation,onClick}){return <button className="history-item" onClick={onClick}>{conversation.title}</button>}
