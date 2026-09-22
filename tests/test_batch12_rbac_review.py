
import os, tempfile
os.environ["SOVEREIGN_TEST_DB"] = ""  # retained for compatibility; DB path is module-defined
from app.services import auth_db

def test_human_review_lifecycle():
    original = auth_db.DB_PATH
    with tempfile.TemporaryDirectory() as td:
        auth_db.DB_PATH = __import__("pathlib").Path(td) / "test.db"
        auth_db.init_db()
        auth_db.create_user("E001", "engineer", "pass1234", "Engineer")
        auth_db.create_user("D001", "developer", "pass1234", "Developer")
        review = auth_db.create_human_review("E001", "engineer", "approval_note_review", "test.docx", requester_role="Engineer")
        assert review["status"] == "pending"
        assert auth_db.list_human_reviews("pending")[0]["id"] == review["id"]
        resolved = auth_db.resolve_human_review(review["id"], "E001", "engineer", "Engineer", "approved", "Reviewed locally")
        assert resolved["status"] == "approved"
        assert resolved["reviewer_role"] == "Engineer"
        assert auth_db.list_human_reviews("pending") == []
        try:
            auth_db.resolve_human_review(review["id"], "E001", "engineer", "Engineer", "approved")
            assert False, "duplicate decision should fail"
        except ValueError:
            pass
    auth_db.DB_PATH = original

def test_wrong_account_cannot_resolve():
    original = auth_db.DB_PATH
    with tempfile.TemporaryDirectory() as td:
        auth_db.DB_PATH = __import__("pathlib").Path(td) / "test.db"
        auth_db.init_db()
        auth_db.create_user("E002", "engineer", "pass1234", "Engineer")
        review = auth_db.create_human_review("E002", "engineer", "approval_note_review", "test.docx", requester_role="Engineer")
        auth_db.create_user("D002", "developer", "pass1234", "Developer")
        try:
            auth_db.resolve_human_review(review["id"], "D002", "developer", "Developer", "approved")
            assert False, "different account must not approve this review"
        except PermissionError:
            pass
        resolved = auth_db.resolve_human_review(review["id"], "E002", "engineer", "Engineer", "approved")
        assert resolved["status"] == "approved"
    auth_db.DB_PATH = original
