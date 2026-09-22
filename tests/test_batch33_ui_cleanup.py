from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


def test_batch33_dashboard_has_no_demo_or_standalone_human_review_session():
    source = (FRONTEND / "pages" / "Dashboard.jsx").read_text(encoding="utf-8")
    assert "DemoFlowPanel" not in source
    assert "HumanReviewPanel" not in source
    assert "__demo__" not in source
    assert "__review__" not in source
    assert "Manager Console" in source


def test_batch33_sidebar_removes_placeholder_chat_and_files_navigation():
    source = (FRONTEND / "components" / "layout" / "Sidebar.jsx").read_text(encoding="utf-8")
    assert "<MessageCircle" not in source
    assert "<Folder" not in source
    assert "Features" not in source
    assert ">Chat</" not in source
    assert ">Files</" not in source
    for label in ("Observability", "Security / Encryption", "Network Evidence", "Artifact Library"):
        assert label in source


def test_batch33_manager_console_has_no_approval_queue():
    source = (FRONTEND / "components" / "admin" / "ManagerPanel.jsx").read_text(encoding="utf-8")
    assert "HumanReviewPanel" not in source
    assert "Approvals" not in source
    assert "Approval Queue" not in source


def test_batch33_approval_card_is_inline_account_owned_review():
    source = (FRONTEND / "components" / "chat" / "ApprovalCard.jsx").read_text(encoding="utf-8")
    assert "HUMAN APPROVAL REQUIRED" in source
    assert "Accept & Generate DOCX" in source
    assert "Reject & Revise" in source
    assert "requester cannot approve" not in source.lower()


def test_batch33_sidebar_contains_persistent_recent_chat_history():
    source = (FRONTEND / "components" / "layout" / "Sidebar.jsx").read_text(encoding="utf-8")
    assert "Recent Chats" in source
    assert "No previous chats yet" in source
    assert "onOpen(c.id)" in source


def test_batch33_general_chat_hides_noisy_workflow_summary():
    source = (FRONTEND / "components" / "chat" / "MessageBubble.jsx").read_text(encoding="utf-8")
    assert "Normal chat should end with the answer" in source
    assert "taskType === 'general'" in source
    assert '<details className="workflow-summary">' in source


def test_batch33_general_follow_up_synthesis_uses_previous_context():
    source = (ROOT / "app" / "services" / "agent.py").read_text(encoding="utf-8")
    assert "if is_follow_up and conversation_context and not has_evidence_task" in source
    assert "RECENT CONVERSATION:" in source
    assert "Resolve references such as" in source
    assert "Do not answer as if the current message were a brand-new topic." in source
