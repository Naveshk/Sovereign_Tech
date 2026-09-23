# Sovereign code sandbox

Build from the project root:

`docker build -t sovereign-code-sandbox:latest ./sandbox`

The FastAPI sandbox service runs this image with `--network none` and additional resource/security limits. The image itself intentionally contains only the Python runtime.
