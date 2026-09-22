import os
from fastapi import APIRouter, UploadFile, File, HTTPException, Header, Query
from app.services.rag.ingest import ingest_file
from app.services.rag.vector_store import count
from app.services.auth_db import audit, record_rag

router = APIRouter()
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
TEMP_DIR = os.path.join(BASE_DIR, 'data', 'knowledge_base', 'documents')
os.makedirs(TEMP_DIR, exist_ok=True)

@router.post('/knowledge/upload')
async def knowledge_upload(
    file: UploadFile = File(...),
    x_employee_id: str|None = Header(None),
    x_role: str|None = Header(None),
    classification: str = Query("internal"),
    allowed_roles: str = Query("Engineer,Developer,Manager"),
    department: str|None = Query(None),
):
    if x_role != 'Manager': raise HTTPException(403, 'Manager role required for RAG upload.')
    name = os.path.basename(file.filename or 'document')
    ext = os.path.splitext(name)[1].lower()
    if ext not in {'.pdf', '.docx', '.pptx', '.xlsx', '.txt', '.md', '.csv'}:
        raise HTTPException(400, 'Supported knowledge files: PDF, DOCX, PPTX, XLSX, TXT, MD, CSV')
    path = os.path.join(TEMP_DIR, name)
    with open(path, 'wb') as f:
        f.write(await file.read())
    roles = [r.strip() for r in allowed_roles.split(",") if r.strip()]
    result=ingest_file(path, name, allowed_roles=roles, classification=classification, department=department)
    if result.get('status')=='completed':
        record_rag(name,result.get('chunks',0),x_employee_id or 'unknown'); audit(x_employee_id,None,x_role,'rag_upload',name)
    return result

@router.get('/knowledge/status')
def knowledge_status():
    return {'documents_indexed_chunks': count(), 'embedding_model': os.getenv('OLLAMA_EMBEDDING_MODEL', 'qwen3-embedding:0.6b')}
