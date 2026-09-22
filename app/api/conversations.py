from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from app.services.auth_db import (
    ROLES,
    append_conversation_message,
    archive_conversation,
    ensure_conversation,
    get_conversation,
    get_conversation_messages,
    list_conversations,
)

router = APIRouter()


def _identity(employee_id: str | None, role: str | None):
    if not employee_id or role not in ROLES:
        raise HTTPException(status_code=403, detail="Authorized local user required.")
    return employee_id


class ConversationCreateRequest(BaseModel):
    conversation_id: str | None = None
    title: str = "New Chat"


class ConversationMessageRequest(BaseModel):
    role: str
    content: str
    metadata: dict = {}


@router.get("/conversations")
def conversations(
    x_employee_id: str | None = Header(None),
    x_role: str | None = Header(None),
    limit: int = 100,
):
    employee_id = _identity(x_employee_id, x_role)
    return {"conversations": list_conversations(employee_id, limit=limit)}


@router.post("/conversations")
def create_conversation(
    body: ConversationCreateRequest,
    x_employee_id: str | None = Header(None),
    x_role: str | None = Header(None),
):
    employee_id = _identity(x_employee_id, x_role)
    try:
        return {"conversation": ensure_conversation(body.conversation_id, employee_id, body.title)}
    except PermissionError as exc:
        raise HTTPException(403, str(exc))


@router.get("/conversations/{conversation_id}")
def conversation_detail(
    conversation_id: str,
    x_employee_id: str | None = Header(None),
    x_role: str | None = Header(None),
):
    employee_id = _identity(x_employee_id, x_role)
    try:
        conversation = get_conversation(conversation_id, employee_id)
        if not conversation:
            raise HTTPException(404, "Conversation not found.")
        return {"conversation": conversation}
    except PermissionError as exc:
        raise HTTPException(403, str(exc))


@router.get("/conversations/{conversation_id}/messages")
def conversation_messages(
    conversation_id: str,
    x_employee_id: str | None = Header(None),
    x_role: str | None = Header(None),
    limit: int = 500,
):
    employee_id = _identity(x_employee_id, x_role)
    try:
        messages = get_conversation_messages(conversation_id, employee_id, limit=limit)
        if messages is None:
            raise HTTPException(404, "Conversation not found.")
        return {"conversation_id": conversation_id, "messages": messages}
    except PermissionError as exc:
        raise HTTPException(403, str(exc))


@router.post("/conversations/{conversation_id}/messages")
def add_conversation_message(
    conversation_id: str,
    body: ConversationMessageRequest,
    x_employee_id: str | None = Header(None),
    x_role: str | None = Header(None),
):
    employee_id = _identity(x_employee_id, x_role)
    try:
        return {"message": append_conversation_message(
            conversation_id, employee_id, body.role, body.content, body.metadata
        )}
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
    except ValueError as exc:
        raise HTTPException(400, str(exc))


@router.delete("/conversations/{conversation_id}")
def archive(
    conversation_id: str,
    x_employee_id: str | None = Header(None),
    x_role: str | None = Header(None),
):
    employee_id = _identity(x_employee_id, x_role)
    try:
        result = archive_conversation(conversation_id, employee_id)
        if not result:
            raise HTTPException(404, "Conversation not found.")
        return {"conversation": result}
    except PermissionError as exc:
        raise HTTPException(403, str(exc))
