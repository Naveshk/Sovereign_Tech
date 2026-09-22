from __future__ import annotations

import datetime as dt
import os
import platform
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

EVIDENCE_DIR = Path(os.getenv("SWB_NETWORK_EVIDENCE_DIR", "data/network_evidence"))
MAX_DURATION_SECONDS = 30
MAX_PACKETS = 500


def _tcpdump_command(duration: int, packet_count: int) -> list[str]:
    # Text output is intentional: it is easier to inspect offline and avoids
    # storing packet payloads. -nn prevents DNS/service-name lookups.
    return [
        "tcpdump", "-nn", "-tt", "-l", "-i", "any",
        "-c", str(packet_count),
    ]


def tcpdump_capability() -> dict[str, Any]:
    path = shutil.which("tcpdump")
    if not path:
        return {
            "available": False,
            "path": None,
            "platform": platform.system(),
            "reason": "tcpdump executable not found",
        }
    return {
        "available": True,
        "path": path,
        "platform": platform.system(),
        "reason": "tcpdump executable available; packet capture may still require elevated privileges",
    }


def capture_tcpdump_evidence(duration_seconds: int = 10, packet_count: int = 100) -> dict[str, Any]:
    """Capture short, payload-free packet evidence.

    This never claims an air gap by itself. It reports whether tcpdump could
    capture and gives the exact local evidence file for offline inspection.
    """
    capability = tcpdump_capability()
    if not capability["available"]:
        return {"status": "unavailable", **capability}

    duration = max(1, min(int(duration_seconds), MAX_DURATION_SECONDS))
    count = max(1, min(int(packet_count), MAX_PACKETS))
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = EVIDENCE_DIR / f"tcpdump_{stamp}.txt"
    cmd = _tcpdump_command(duration, count)
    started = time.monotonic()
    proc = None
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            stdout, stderr = proc.communicate(timeout=duration)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                stdout, stderr = proc.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
        elapsed = round((time.monotonic() - started) * 1000, 2)
        text = stdout or ""
        # Keep evidence metadata + packet headers, never packet payloads.
        content = (
            f"timestamp_utc={stamp}\n"
            f"duration_seconds={duration}\n"
            f"packet_limit={count}\n"
            f"command={' '.join(cmd)}\n"
            f"return_code={proc.returncode}\n"
            f"elapsed_ms={elapsed}\n"
            f"stderr={stderr.strip()[:2000]}\n"
            f"--- packet headers ---\n{text[:100000]}"
        )
        path.write_text(content, encoding="utf-8")
        return {
            "status": "captured" if proc.returncode in (0, -15, -2) else "error",
            "path": str(path),
            "duration_seconds": duration,
            "packet_limit": count,
            "return_code": proc.returncode,
            "elapsed_ms": elapsed,
            "command": cmd,
            "note": "Header-only tcpdump evidence. Absence of external packets is evidence for the capture window, not a permanent air-gap guarantee.",
        }
    except (PermissionError, OSError) as exc:
        return {
            "status": "permission_denied" if isinstance(exc, PermissionError) else "error",
            "path": None,
            "command": cmd,
            "error": str(exc),
            "note": "tcpdump may require elevated privileges and an appropriate capture interface.",
        }


def read_evidence(limit: int = 20) -> list[dict[str, Any]]:
    if not EVIDENCE_DIR.exists():
        return []
    files = sorted(EVIDENCE_DIR.glob("tcpdump_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)[:max(1, min(limit, 100))]
    return [
        {"filename": p.name, "path": str(p), "size_bytes": p.stat().st_size,
         "modified_at": dt.datetime.fromtimestamp(p.stat().st_mtime, dt.timezone.utc).isoformat()}
        for p in files
    ]
