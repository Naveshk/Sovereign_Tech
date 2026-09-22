
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_deprecated_manager_review_routes_removed():
    source = (ROOT / "app" / "api" / "auth.py").read_text()
    assert '@router.get("/admin/reviews")' not in source
    assert '@router.post("/admin/reviews/{review_id}/decision")' not in source
    assert '@router.get("/reviews")' in source
    assert '@router.post("/reviews/{review_id}/decision")' in source


def test_vite_uses_node_entrypoint():
    package = (ROOT / "frontend" / "package.json").read_text()
    assert 'node ./node_modules/vite/bin/vite.js' in package
    assert 'node_modules/.bin/vite' not in package


def test_runtime_secret_paths_are_ignored():
    gitignore = (ROOT / ".gitignore").read_text()
    assert "data/keys/*" in gitignore
    assert "data/sovereign.db" in gitignore


def test_final_package_has_no_stale_build_or_nested_checkpoints():
    assert not (ROOT / "frontend" / "dist").exists()
    assert not (ROOT / "Sovereign_T-Batch22.zip").exists()
    assert not (ROOT / "Sovereign_T-Batch24.zip").exists()
