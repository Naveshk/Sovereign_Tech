import app.services.sandbox.executor as ex
from app.services.sandbox.security import sandbox_security_profile


def test_security_profile_is_hardened():
    p = sandbox_security_profile()
    assert p["network"] == "none"
    assert p["user"] == "10001:10001"
    assert p["read_only_root"] is True
    assert p["no_new_privileges"] is True
    assert p["capabilities"] == "drop-all"
    assert p["seccomp"] == "default"
    assert p["ipc"] == "private"
    assert p["memory"] == "512m"
    assert p["memory_swap"] == "512m"
    assert p["pids_limit"] == "50"


def test_docker_command_enforces_isolation(tmp_path, monkeypatch):
    executor = ex.DockerSandboxExecutor(tmp_path)
    monkeypatch.setattr(executor, "_docker_available", lambda: (True, "test"))

    captured = {}
    class Proc:
        returncode = 0
        def communicate(self, timeout=None):
            return "ok", ""
    def fake_popen(command, **kwargs):
        captured["command"] = command
        return Proc()

    monkeypatch.setattr(ex.subprocess, "Popen", fake_popen)
    result = executor.execute("print(1)", timeout=5)
    cmd = captured["command"]

    assert result.status == "success"
    for flag in [
        ("--network", "none"),
        ("--user", "10001:10001"),
        ("--memory", "512m"),
        ("--memory-swap", "512m"),
        ("--cpus", "1"),
        ("--pids-limit", "50"),
        ("--cap-drop", "ALL"),
        ("--security-opt", "no-new-privileges:true"),
        ("--ipc", "private"),
        ("--read-only",),
        ("--init",),
        ("--force-rm",),
    ]:
        if len(flag) == 1:
            assert flag[0] in cmd
        else:
            i = cmd.index(flag[0])
            assert cmd[i+1] == flag[1]

    seccomp_values = [cmd[i + 1] for i, v in enumerate(cmd[:-1]) if v == "--security-opt"]
    assert "seccomp=default" in seccomp_values
    assert "--tmpfs" in cmd
    tmpfs = cmd[cmd.index("--tmpfs") + 1]
    assert "noexec" in tmpfs and "nosuid" in tmpfs and "nodev" in tmpfs
    assert "--ulimit" in cmd


def test_sandbox_security_endpoint():
    import app.api.sandbox as api
    result = api.sandbox_security()
    assert result["network_isolation"] is True
    assert result["user"] == "10001:10001"
