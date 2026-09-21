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
    LLM_MODE=local DEMO_MODE=false HF_HUB_DISABLE_TELEMETRY=1
COPY backend/requirements.lock backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt
# This public pinned model is baked outside the mounted runtime volume.
# Build-time preparation deliberately needs no application secrets or database.
RUN python -c "from huggingface_hub import snapshot_download; snapshot_download('sentence-transformers/all-MiniLM-L6-v2', revision='bc57282bc374d33e0d6c4de27f12dc1c2a87f37a', cache_dir='/app/model-cache', allow_patterns=['*.json','*.safetensors','*.txt','1_Pooling/*'])"
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
