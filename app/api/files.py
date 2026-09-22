from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os

router = APIRouter()
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
GENERATED_DIR = os.path.join(BASE_DIR, "data", "generated")

@router.get("/files/{filename}")
def download_file(filename: str):
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(GENERATED_DIR, safe_filename)
    if not os.path.isfile(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    media_types = {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".pdf": "application/pdf",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".zip": "application/zip",
    }
    return FileResponse(path=file_path, filename=safe_filename, media_type=media_types.get(os.path.splitext(safe_filename)[1].lower(), "application/octet-stream"))
