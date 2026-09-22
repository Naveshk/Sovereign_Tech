from pathlib import Path

SANDBOX_IMAGE = "sovereign-code-sandbox:latest"
DEFAULT_TIMEOUT = 10
MAX_TIMEOUT = 30
MEMORY_LIMIT = "512m"
CPU_LIMIT = "1"
PIDS_LIMIT = "50"
SANDBOX_USER = "10001:10001"
MEMORY_SWAP_LIMIT = MEMORY_LIMIT
TMPFS_LIMIT = "64m"


def validate_code(code: str, language: str) -> tuple[bool, str | None]:
    if language.lower() not in {"python", "py"}:
        return False, "Only Python execution is enabled in the secure sandbox."
    if not code or not code.strip():
        return False, "Code cannot be empty."
    if len(code.encode("utf-8")) > 256 * 1024:
        return False, "Code is too large (maximum 256 KB)."
    return True, None


def safe_workspace(root: Path, run_id: str) -> Path:
    workspace = (root / run_id).resolve()
    root_resolved = root.resolve()
    if root_resolved not in workspace.parents:
        raise ValueError("Invalid sandbox workspace path")
    workspace.mkdir(parents=True, exist_ok=False)
    return workspace


def sandbox_security_profile() -> dict:
    """Return the fixed local sandbox security contract without secrets."""
    return {
        "image": SANDBOX_IMAGE,
        "network": "none",
        "user": SANDBOX_USER,
        "memory": MEMORY_LIMIT,
        "memory_swap": MEMORY_SWAP_LIMIT,
        "cpus": CPU_LIMIT,
        "pids_limit": PIDS_LIMIT,
        "read_only_root": True,
        "tmpfs": f"/tmp:noexec,nosuid,nodev,size={TMPFS_LIMIT}",
        "capabilities": "drop-all",
        "no_new_privileges": True,
        "seccomp": "default",
        "ipc": "private",
        "ulimits": {"nofile": 64, "fsize_bytes": 10485760},
        "network_isolation": True,
    }
