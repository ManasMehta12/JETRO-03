FROM python:3.11-slim
COPY --from=ghcr.io/astral-sh/uv:0.13.5 /uv /usr/local/bin/uv
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY takumi-backend/pyproject.toml takumi-backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY takumi-backend/ ./
RUN useradd --create-home --uid 10001 takumi && mkdir -p /data/media && chown -R takumi:takumi /data
USER takumi
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001", "--no-access-log"]
