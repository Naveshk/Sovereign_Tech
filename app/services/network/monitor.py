import socket
import subprocess
from collections import Counter


def _is_private_or_local(ip: str) -> bool:
    try:
        addr = socket.inet_pton(socket.AF_INET, ip)
        first = addr[0]
        second = addr[1]
        return ip.startswith("127.") or ip.startswith("10.") or ip.startswith("192.168.") or (172 <= first <= 172 and 16 <= second <= 31)
    except OSError:
        return ip in {"::1", "localhost"} or ip.lower().startswith("fe80:")


def connection_snapshot() -> dict:
    # Prefer psutil when available; otherwise return a truthful unavailable state.
    try:
        import psutil
        connections = psutil.net_connections(kind="inet")
        established = [c for c in connections if c.status == "ESTABLISHED" and c.raddr]
        external = []
        local = []
        for c in established:
            remote_ip = c.raddr.ip
            (local if _is_private_or_local(remote_ip) else external).append(remote_ip)
        return {
            "available": True,
            "established_connections": len(established),
            "local_connections": len(local),
            "external_connections": len(external),
            "external_destinations": sorted(set(external))[:50],
            "cloud_calls": 0,
            "note": "Connection snapshot is not packet-level proof; use tcpdump for evidence capture.",
        }
    except Exception as exc:
        return {"available": False, "established_connections": 0, "local_connections": 0, "external_connections": 0, "external_destinations": [], "cloud_calls": 0, "note": str(exc)}


def tcpdump_available() -> bool:
    try:
        r = subprocess.run(["tcpdump", "--version"], capture_output=True, text=True, timeout=3)
        return r.returncode == 0 or "tcpdump" in (r.stdout + r.stderr).lower()
    except Exception:
        return False
