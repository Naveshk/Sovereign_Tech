from app.services.sandbox.executor import DockerSandboxExecutor


class SandboxManager:
    def __init__(self):
        self.executor = DockerSandboxExecutor()

    def execute(self, code: str, language: str = "python", timeout: int = 10) -> dict:
        return self.executor.execute(code=code, language=language, timeout=timeout).to_dict()


sandbox_manager = SandboxManager()
