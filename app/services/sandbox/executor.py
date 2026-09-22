import subprocess
import time
from pathlib import Path

from app.services.sandbox.result import SandboxResult
from app.services.sandbox.security import (
    CPU_LIMIT,
    DEFAULT_TIMEOUT,
    MAX_TIMEOUT,
    MEMORY_LIMIT,
    PIDS_LIMIT,
    SANDBOX_IMAGE,
    SANDBOX_USER,
    MEMORY_SWAP_LIMIT,
    TMPFS_LIMIT,
    safe_workspace,
    validate_code,
)


class DockerSandboxExecutor:
    def __init__(self, workspace_root: str | Path | None = None):
        base = Path(workspace_root) if workspace_root else Path(__file__).resolve().parents[3] / "data" / "sandbox" / "workspaces"
        self.workspace_root = base.resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    def _docker_available(self) -> tuple[bool, str]:
        try:
            result = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"], capture_output=True, text=True, timeout=5)
        except FileNotFoundError:
            return False, "Docker CLI was not found. Start Docker Desktop and ensure docker is available in PATH."
        except subprocess.TimeoutExpired:
            return False, "Docker did not respond within 5 seconds."
        if result.returncode != 0:
            return False, result.stderr.strip() or "Docker engine is unavailable."
        return True, result.stdout.strip() or "available"

    def execute(self, code: str, language: str = "python", timeout: int = DEFAULT_TIMEOUT) -> SandboxResult:
        valid, error = validate_code(code, language)
        if not valid:
            return SandboxResult(status="rejected", language=language, error=error)

        timeout = max(1, min(int(timeout), MAX_TIMEOUT))
        available, docker_error = self._docker_available()
        if not available:
            return SandboxResult(status="error", language=language, network="disabled", error=docker_error)

        import uuid
        run_id = str(uuid.uuid4())
        workspace = safe_workspace(self.workspace_root, run_id)
        code_file = workspace / "main.py"
        code_file.write_text(code, encoding="utf-8")
        container_name = f"sovereign-sbx-{run_id[:12]}"

        command = [
    "docker", "run",
    "--rm",
    "--name", container_name,

    # Network isolation
    "--network", "none",

    # User isolation
    "--user", SANDBOX_USER,

    # Resource limits
    "--memory", MEMORY_LIMIT,
    "--memory-swap", MEMORY_SWAP_LIMIT,
    "--cpus", CPU_LIMIT,
    "--pids-limit", PIDS_LIMIT,

    # Security
    "--cap-drop", "ALL",
    "--security-opt", "no-new-privileges:true",
    "--ipc", "private",

    # Filesystem isolation
    "--read-only",
    "--tmpfs", f"/tmp:rw,noexec,nosuid,nodev,size={TMPFS_LIMIT}",

    # Process/file limits
    "--ulimit", "nofile=64:64",
    "--ulimit", "fsize=10485760:10485760",

    "--init",

    # Environment
    "-e", "PYTHONDONTWRITEBYTECODE=1",

    # Workspace
    "-v", f"{workspace.as_posix()}:/workspace:rw",
    "-w", "/workspace",

    # Image + command
    SANDBOX_IMAGE,
    "python", "main.py",
]
        started = time.monotonic()
        timed_out = False
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                subprocess.run(["docker", "kill", container_name], capture_output=True, text=True, timeout=5)
                stdout, stderr = process.communicate(timeout=5)
            duration = round(time.monotonic() - started, 3)
            if timed_out:
                return SandboxResult(status="timeout", stdout=stdout[-12000:], stderr=stderr[-12000:], exit_code=None, duration=duration, timed_out=True)
            status = "success" if process.returncode == 0 else "failed"
            return SandboxResult(status=status, stdout=stdout[-12000:], stderr=stderr[-12000:], exit_code=process.returncode, duration=duration)
        except Exception as exc:
            return SandboxResult(status="error", duration=round(time.monotonic() - started, 3), error=str(exc))
        finally:
            import shutil
            shutil.rmtree(workspace, ignore_errors=True)
