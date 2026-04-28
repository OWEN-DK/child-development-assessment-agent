# ============================================
# 儿童发展评估系统 - 后端 Dockerfile
# 两阶段构建：uv 安装 → 瘦身运行时
#
# 构建命令：
#   docker compose build
#   docker compose build --no-cache
#
# 注意：
#   bookworm (Debian 12) 的 glibc 2.36 兼容 manylinux_2_35，
#   可正常安装 onnxruntime 等 ML 依赖。
#   旧服务器 (glibc < 2.27) 必须使用 Docker 部署。
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

# 清理 .venv 中不必要的文件，减小镜像体积（保留 .dist-info 以确保包元数据完整）
RUN find /app/backend/.venv -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; \
    find /app/backend/.venv -type d -name tests -exec rm -rf {} + 2>/dev/null; \
    find /app/backend/.venv -type d -name test -exec rm -rf {} + 2>/dev/null; \
    find /app/backend/.venv -type f -name "*.pyc" -delete 2>/dev/null; \
    find /app/backend/.venv -type f -name "*.pyo" -delete 2>/dev/null; \
    find /app/backend/.venv -type f -name "*.a" -path "*/onnxruntime/*" -delete 2>/dev/null; \
    find /app/backend/.venv -type f -name "*.pxd" -delete 2>/dev/null; \
    find /app/backend/.venv -type f -name "*.h" -path "*/numpy/*" -delete 2>/dev/null; \
    find /app/backend/.venv -type f -name "*.h" -path "*/onnxruntime/*" -delete 2>/dev/null; \
    rm -rf /app/backend/.venv/share /app/backend/.venv/man 2>/dev/null; \
    echo "Slimming complete"

COPY src/ src/
COPY config/ config/

RUN groupadd -g 1000 appuser && \
    useradd -m -u 1000 -g appuser appuser && \
    mkdir -p /app/app_data/data/configs/versions \
              /app/app_data/storage/vector_store \
              /app/app_data/storage/index \
              /app/app_data/storage/snapshots \
              /app/app_data/storage/source_documents \
              /app/app_data/storage/test_case_drafts \
              /app/app_data/storage/test_sets \
              /app/app_data/storage/test_cases_history \
              /app/app_data/storage/test_runs \
              /app/app_data/storage/reports \
              /app/app_data/temp_uploads \
              /app/app_data/cache \
              /app/backend/logs && \
    chown -R appuser:appuser /app

ENV PATH="/app/backend/.venv/bin:$PATH" \
    PYTHONPATH="/app/backend" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER appuser

EXPOSE 51002

CMD ["uvicorn", "src.server:create_app", "--host", "0.0.0.0", "--port", "51002", "--factory"]
