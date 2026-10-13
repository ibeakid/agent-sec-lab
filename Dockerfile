# Deliberately weak container image for D4 scanning practice. Never deploy.
# Run with the port bound to loopback only:
#   docker run --rm -p 127.0.0.1:8000:8000 agent-sec-lab
FROM python:3.11

# Temporary (D5, 2026-10-14): CVE-2026-96889 (librsvg, HIGH) is fixed in Debian but not yet in python:3.11.
# Remove once the upstream base image ships librsvg 2.60.0+dfsg-1+deb13u1 or later.
RUN apt-get update \
 && apt-get install -y --only-upgrade librsvg2-2 librsvg2-common librsvg2-dev gir1.2-rsvg-2.0 \
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
