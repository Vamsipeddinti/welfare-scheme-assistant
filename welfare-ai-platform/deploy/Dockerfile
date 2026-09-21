FROM node:24-alpine AS frontend
WORKDIR /web
RUN corepack enable && corepack prepare pnpm@11.19.0 --activate
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend ./
RUN pnpm build

FROM python:3.12.14-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    MODEL_DIR=/app/model-cache STATIC_DIR=/app/frontend/dist \
    UPLOAD_DIR=/app/runtime/uploads CHROMA_DIR=/app/runtime/chroma \
    LLM_MODE=local DEMO_MODE=false HF_HUB_DISABLE_TELEMETRY=1 \
    HF_HOME=/app/.cache/huggingface HF_HUB_DISABLE_SYMLINKS_WARNING=1
COPY backend/requirements.lock backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt
# This public pinned model is baked outside the mounted runtime volume.
# Build-time preparation deliberately needs no application secrets or database.
# HF_HOME is redirected under /app because the default /root/.cache is not
# guaranteed to be writable in every build environment; retry a few times
# to absorb transient network failures, then fail the build loudly (rather
# than shipping an image with an empty model cache that crashes at runtime).
RUN mkdir -p "$MODEL_DIR" "$HF_HOME" \
    && for attempt in 1 2 3; do \
         python -c "from huggingface_hub import snapshot_download; snapshot_download('sentence-transformers/all-MiniLM-L6-v2', revision='bc57282bc374d33e0d6c4de27f12dc1c2a87f37a', cache_dir='/app/model-cache', allow_patterns=['*.json','*.safetensors','*.txt','1_Pooling/*'])" && break; \
         echo "Model download attempt $attempt failed, retrying in 5s..."; \
         sleep 5; \
       done \
    && find "$MODEL_DIR" -name '*.safetensors' -print -quit | grep -q . \
    || (echo "ERROR: embedding model artifacts are missing after retries; failing the build instead of shipping a broken image" && exit 1)
COPY backend ./backend
COPY data ./data
COPY scripts ./scripts
COPY deploy/start.py ./deploy/start.py
COPY --from=frontend /web/dist ./frontend/dist
RUN useradd --create-home --uid 10001 welfare && mkdir -p /app/runtime && chown -R welfare:welfare /app
# The entrypoint initializes only its fixed volume directories, then drops privileges.
USER root
EXPOSE 8000
CMD ["python", "/app/deploy/start.py"]
