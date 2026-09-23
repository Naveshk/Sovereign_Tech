
## Runtime flow

React → FastAPI `/chat/stream` → task analyzer/model router → local Ollama/RAG/file tools.
For coding: Qwen2.5-Coder → `SandboxManager` → Docker container → result/verification → SSE/UI.

## Docker sandbox

- Python-only execution initially.
- Non-root image user.
- `--network none`.
- 512 MB memory, 1 CPU, 50 PIDs.
- All Linux capabilities dropped.
- `no-new-privileges`.
- Read-only container root plus temporary `/tmp`.
- Temporary per-run workspace and automatic cleanup.
- 10 second default timeout, 30 second hard maximum.
- One bounded repair/retry attempt in the agent.

## network isolation

The sandbox has no network namespace. This is separate from host-wide egress control. A full air-gapped deployment also needs a reviewed host firewall policy and no cloud API configuration.

## monitoring

`GET /api/network/status` reports a connection snapshot and whether tcpdump is available. It deliberately does not claim packet-level proof. The `security/monitoring/tcpdump/` guide explains how to capture evidence in WSL/Linux and how to account for loopback/Docker interfaces.

## OCR

Scanned PDFs now try local PaddleOCR first (optional dependency in `requirements-ocr.txt`). If PaddleOCR is unavailable or returns no useful text, the existing local Qwen2.5-VL page analysis remains the fallback. Text PDFs continue using PyMuPDF extraction.

## Important deployment note

Do not apply firewall templates blindly. Adapt them to the final Linux network topology and test in a maintenance window. Windows 11 development can use Docker Desktop/WSL for the sandbox while host firewall/network evidence is validated separately.


## network evidence
- Application policy blocks external outbound URLs by default.
- Docker sandbox uses `--network none` for isolated execution.
- tcpdump capability is reported separately from packet-capture evidence.
- Manager-only short header capture is available at `/api/network/evidence/capture`.
- Host firewall enforcement is environment-specific; final deployment should use reviewed default-deny egress rules (prefer nftables where available).
