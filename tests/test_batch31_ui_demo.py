from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_vite_scripts_use_node_entrypoint():
    package = json.loads((FRONTEND / "package.json").read_text(encoding="utf-8"))
    scripts = package["scripts"]
    assert scripts["build"] == "node ./node_modules/vite/bin/vite.js build"
    assert scripts["dev"] == "node ./node_modules/vite/bin/vite.js"
    assert scripts["preview"] == "node ./node_modules/vite/bin/vite.js preview"


def test_batch33_removes_deprecated_sih_demo_session():
    dashboard = (FRONTEND / "src/pages/Dashboard.jsx").read_text(encoding="utf-8")
    assert "DemoFlowPanel" not in dashboard
    assert '__demo__' not in dashboard
    assert not (FRONTEND / "src/components/admin/DemoFlowPanel.jsx").exists()


def test_final_ui_has_mobile_and_workflow_polish():
    css = (FRONTEND / "src/styles/global.css").read_text(encoding="utf-8")
    for token in ("demo-panel", "demo-steps", "@media(max-width:520px)", ".execution", ".download"):
        assert token in css
