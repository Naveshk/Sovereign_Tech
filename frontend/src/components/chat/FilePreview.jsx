export default function FilePreview({file,onRemove}){return <div className="file-chip">📎 {file.name}<button onClick={onRemove}>×</button></div>}
