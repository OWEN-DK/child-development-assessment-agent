#!/usr/bin/env bash
# ============================================
# 儿童发展评估系统 - Docker Compose 部署脚本
#
# 用法：
#   ./scripts/deploy.sh start          # 启动（后台）
#   ./scripts/deploy.sh start --build  # 重新构建后启动
#   ./scripts/deploy.sh stop           # 停止并移除容器
#   ./scripts/deploy.sh restart        # 重启
#   ./scripts/deploy.sh status         # 查看状态
#   ./scripts/deploy.sh logs           # 实时查看日志
#   ./scripts/deploy.sh logs backend   # 查看指定服务日志
#   ./scripts/deploy.sh clean          # 停止并清理所有资源（含镜像）
#   ./scripts/deploy.sh help           # 查看帮助
# ============================================

set -euo pipefail

# 项目根目录（脚本所在目录的上一级）
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_ROOT"

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# 检查 docker 和 docker compose 是否可用
check_deps() {
    if ! command -v docker &>/dev/null; then
        log_error "docker 未安装，请先安装 Docker"
        exit 1
    fi
    if ! docker compose version &>/dev/null; then
        log_error "docker compose 不可用，请安装 Docker Compose V2"
        exit 1
    fi
}

# 确保必要的宿主机目录存在
ensure_dirs() {
    mkdir -p app_data logs
}

cmd_start() {
    local build_flag=""
    if [[ "${1:-}" == "--build" ]]; then
        build_flag="--build"
    fi

    ensure_dirs
    log_info "启动服务..."
    docker compose up -d $build_flag

    log_info "等待健康检查..."
    local retries=12
    local container="child-dev-backend"
    while [[ $retries -gt 0 ]]; do
        local health
        health=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "unknown")
        if [[ "$health" == "healthy" ]]; then
            log_info "服务已就绪 (healthy)"
            log_info "访问地址: http://localhost:${APP_PORT:-51002}"
            return 0
        fi
        if [[ "$health" == "unhealthy" ]]; then
            log_error "健康检查失败，查看日志: $0 logs"
            return 1
        fi
        retries=$((retries - 1))
        sleep 5
    done

    log_warn "健康检查超时，服务可能仍在启动中，查看日志: $0 logs"
}

cmd_stop() {
    log_info "停止服务..."
    docker compose down
    log_info "服务已停止"
}

cmd_restart() {
    cmd_stop
    cmd_start "${1:-}"
}

cmd_status() {
    docker compose ps
}

cmd_logs() {
    local service="${1:-backend}"
    docker compose logs -f "$service"
}

cmd_clean() {
    log_warn "即将停止并清理所有容器、镜像和卷"
    read -rp "确认继续？(y/N) " confirm
    if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
        log_info "已取消"
        return 0
    fi
    docker compose down --rmi local --volumes --remove-orphans
    log_info "清理完成"
}

cmd_help() {
    cat <<'EOF'
儿童发展评估系统 - 部署脚本

用法: ./scripts/deploy.sh <命令> [选项]

命令:
  start [--build]   启动服务（后台运行），--build 强制重新构建镜像
  stop              停止并移除容器
  restart [--build] 重启服务
  status            查看容器运行状态
  logs [service]    实时查看日志（默认 backend）
  clean             停止并清理所有资源（含本地镜像）
  help              显示此帮助

示例:
  ./scripts/deploy.sh start              # 直接启动
  ./scripts/deploy.sh start --build      # 构建镜像后启动
  ./scripts/deploy.sh logs               # 查看后端日志
  ENV_FILE=backend/.env.test ./scripts/deploy.sh start  # 使用测试配置
EOF
}

# --- 入口 ---

check_deps

case "${1:-help}" in
    start)   cmd_start "${2:-}" ;;
    stop)    cmd_stop ;;
    restart) cmd_restart "${2:-}" ;;
    status)  cmd_status ;;
    logs)    cmd_logs "${2:-}" ;;
    clean)   cmd_clean ;;
    help|*)  cmd_help ;;
esac
