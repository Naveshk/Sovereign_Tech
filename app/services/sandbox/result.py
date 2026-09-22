from dataclasses import asdict, dataclass


@dataclass
class SandboxResult:
    status: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    duration: float = 0.0
    network: str = "disabled"
    language: str = "python"
    timed_out: bool = False
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
