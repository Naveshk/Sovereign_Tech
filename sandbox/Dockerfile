FROM python:3.12-slim

# Minimal runtime: no curl/wget/ssh/git and no application dependencies.
RUN useradd --create-home --uid 10001 sandbox
WORKDIR /workspace
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER sandbox

CMD ["python", "--version"]
