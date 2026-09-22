from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.health import router as health_router
from app.api.chat import router as chat_router
from app.api.files import router as files_router
from app.api.knowledge import router as knowledge_router
from app.api.auth import router as auth_router
from app.api.sandbox import router as sandbox_router
from app.api.network import router as network_router
from app.api.engineering import router as engineering_router
from app.api.artifacts import router as artifacts_router
from app.api.conversations import router as conversations_router
from app.api.observability import router as observability_router

app = FastAPI(
    title="Sovereign AI Workbench",
    description="On-Premise Agentic AI Backend",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(files_router, prefix="/api")
app.include_router(knowledge_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(sandbox_router, prefix="/api")
app.include_router(network_router, prefix="/api")
app.include_router(engineering_router, prefix="/api")
app.include_router(artifacts_router, prefix="/api")
app.include_router(conversations_router, prefix="/api")
app.include_router(observability_router, prefix="/api")
