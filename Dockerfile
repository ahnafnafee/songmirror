# --- Stage 1: build the React SPA ---
FROM node:22-slim@sha256:e9f565d32859f0cbfb52125eafe8be39390f24dac302dc3cdf566e8ba3ab21ee AS frontend
RUN corepack enable && corepack prepare pnpm@11.5.1 --activate
WORKDIR /frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build   # -> /frontend/dist

# --- Stage 2: Python runtime ---
FROM python:3.13.16-slim-bookworm@sha256:73aa5faee130c60da030e105ec971ccf57473fbd22ce73bd6fc9ba99a40b838d
COPY --from=ghcr.io/astral-sh/uv:0.13.5@sha256:32a7bb39b496babbd997b0a39a4d66c126bdaf5661b302bf6f06abda8deca6ff /uv /uvx /bin/

# ffmpeg + spotDL power the optional local download mirror.
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# spotDL as an isolated tool so its old pins never constrain the app's web stack
# (see downloads._spotdl_cmd, which finds it on PATH).
ENV UV_TOOL_DIR=/opt/uv-tools UV_TOOL_BIN_DIR=/usr/local/bin
RUN uv tool install "spotdl==4.6.0"

COPY main.py ./
COPY songmirror ./songmirror
COPY --from=frontend /frontend/dist ./frontend/dist

# SONGMIRROR_ENV_FILE points the engine at SettingsStore's managed env so wizard-saved
# credentials win over any stale .env.
ENV PYTHONUNBUFFERED=1 SONGMIRROR_DATA_DIR=/data SONGMIRROR_ENV_FILE=/data/app.env
ENV HOME=/data XDG_CACHE_HOME=/tmp/songmirror-cache
RUN groupadd --gid 1000 songmirror && useradd --uid 1000 --gid 1000 --create-home songmirror \
    && mkdir -p /data /music && chown songmirror:songmirror /data /music
WORKDIR /data
USER 1000:1000
EXPOSE 8080
CMD ["/app/.venv/bin/uvicorn", "songmirror.web:app", "--app-dir", "/app", "--host", "0.0.0.0", "--port", "8080"]
