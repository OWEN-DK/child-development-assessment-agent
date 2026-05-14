# ============================================
# RAG Platform 后端 Dockerfile
# 两阶段构建：uv 安装 → 瘦身运行时
# ============================================

# ---- Stage 1: 构建依赖 ----
FROM --platform=linux/amd64 ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /app/backend

COPY pyproject.toml uv.lock ./

RUN uv sync --no-dev --no-install-project

# ---- Stage 2: 最小运行时 ----
FROM --platform=linux/amd64 python:3.13-slim-bookworm

WORKDIR /app/backend

COPY --from=builder /app/backend/.venv /app/backend/.venv

# 清理 .venv 中不必要的文件
RUN find /app/backend/.venv -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
    find /app/backend/.venv -type d -name tests -exec rm -rf {} + 2>/dev/null; \
    find /app/backend/.venv -type f -name "*.pyc" -delete 2>/dev/null; \
    find /app/backend/.venv -type f -name "*.pyo" -delete 2>/dev/null; \
    rm -rf /app/backend/.venv/share /app/backend/.venv/man 2>/dev/null; \
    echo "Slimming complete"

COPY src/ src/

RUN groupadd -g 1000 appuser && \
    useradd -m -u 1000 -g appuser appuser && \
    mkdir -p /app/app_data/data \
              /app/app_data/storage/chroma \
              /app/app_data/storage/bm25 \
              /app/app_data/storage/documents \
              /app/app_data/temp_uploads \
              /app/backend/logs && \
    chown -R appuser:appuser /app

ENV PATH="/app/backend/.venv/bin:$PATH" \
    PYTHONPATH="/app/backend" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 51002

CMD ["uvicorn", "src.server:create_app", "--host", "0.0.0.0", "--port", "51002", "--factory"]
