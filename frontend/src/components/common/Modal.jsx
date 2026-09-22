export default function Modal({children,onClose}){return <div className="modal-backdrop"><div className="modal">{children}<button onClick={onClose}>Close</button></div></div>}
