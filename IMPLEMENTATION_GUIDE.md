# Implementation guide — Priority 1, 2, 3 + OCR

## 1. Build the sandbox image

From the `Sovereign` project root:

```powershell
docker build -t sovereign-code-sandbox:latest ./sandbox
```

Test:

```powershell
docker run --rm --network none sovereign-code-sandbox:latest
```

## 2. Start the existing backend

Use the project's existing Python environment and start FastAPI as before. No migration is required for SQLite or ChromaDB.

## 3. Test the sandbox API

Open `/docs` and call `POST /api/sandbox/execute`:

```json
{
  "language": "python",
  "timeout": 10,
  "code": "print(10 + 20)"
}
```

Expected: `status=success`, `stdout=30`, `network=disabled`.

## 4. Prove network isolation

```powershell
docker run --rm --network none sovereign-code-sandbox:latest python -c "import urllib.request; urllib.request.urlopen('https://example.com', timeout=3)"
```

The request should fail because the sandbox has no network namespace.

## 5. Use the normal chat flow

Ask a coding task. The existing task analyzer routes it to Qwen2.5-Coder. The generated Python is then executed by `SandboxManager`; one bounded repair attempt is allowed if execution fails.

## 6. Network status

`GET /api/network/status` gives a local connection snapshot. It is intentionally labeled as a snapshot, not packet-level proof.

## 7. tcpdump evidence

On Windows 11, use WSL for packet capture:

```bash
sudo apt update
sudo apt install -y tcpdump
ip -br addr
sudo tcpdump -i any -nn -w sovereign-demo.pcap
```

Run the demo, stop capture with Ctrl+C, then inspect with:

```bash
tcpdump -nn -r sovereign-demo.pcap
```

Validate which WSL/Docker/loopback interfaces carry the traffic before making a zero-external-traffic claim.

## 8. Optional PaddleOCR

The base app does not force-install the heavy OCR stack. To enable dedicated local OCR:

```powershell
pip install -r requirements-ocr.txt
```

Scanned PDFs automatically try PaddleOCR first. If it is unavailable or produces no text, the existing local Qwen2.5-VL fallback is used. Text PDFs continue to use PyMuPDF.

## 9. Database safety

No SQLite schema migration is included. Sandbox workspaces live under `data/sandbox/workspaces/`. ChromaDB/RAG remains unchanged.
