# Deliberately weak container image for D4 scanning practice. Never deploy.
# Run with the port bound to loopback only:
#   docker run --rm -p 127.0.0.1:8000:8000 agent-sec-lab
FROM python:3.11

WORKDIR /app

# setuptools is not needed at runtime (the app runs from .venv) and vendors vulnerable jaraco.context/wheel
RUN pip install uv \
 && pip uninstall -y setuptools

COPY . .

RUN uv sync --frozen --no-dev

ENV OLLAMA_URL=http://host.docker.internal:11434

EXPOSE 8000

CMD [".venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
