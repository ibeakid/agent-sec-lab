# Deliberately weak container image for D4 scanning practice. Never deploy.
# Run with the port bound to loopback only:
#   docker run --rm -p 127.0.0.1:8000:8000 agent-sec-lab
FROM python:3.11

# Apply Debian security fixes newer than the python:3.11 base image (D5, 2026-10-14).
# Without this, the Trivy gate (--ignore-unfixed) fails whenever Debian ships a fix the base image
# lacks (seen: librsvg CVE-2026-96889, curl CVE-2026-8286/-8927). Trade-off: builds are less
# reproducible. Revisit with the slim base (D6) and a pinned digest.
RUN apt-get update \
 && apt-get upgrade -y \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# setuptools is not needed at runtime (the app runs from .venv) and vendors vulnerable jaraco.context/wheel
RUN pip install uv \
 && pip uninstall -y setuptools

COPY . .

RUN uv sync --frozen --no-dev

ENV OLLAMA_URL=http://host.docker.internal:11434

EXPOSE 8000

CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
