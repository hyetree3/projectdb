#!/usr/bin/env bash
# 백엔드(FastAPI :8000) / 프론트엔드(Vite :5173) 개발 서버를 한 번에 관리하는 스크립트.
#
# 사용법:
#   scripts/dev.sh start   - 두 서버를 백그라운드로 기동
#   scripts/dev.sh stop    - 두 서버 종료
#   scripts/dev.sh status  - 실행 상태와 포트 표시
#
# 주의(Windows): uvicorn --reload와 npm run dev는 각각 실제 서버 프로세스를
# 감싸는 자식 프로세스를 만든다. `$!`로 잡히는 PID(런처)와 실제로 포트를
# 점유하는 PID(자식)가 다르기 때때문에, PID 저장값이 아니라 "포트를 점유 중인
# PID"를 netstat으로 찾아 taskkill //T(트리 전체)로 종료해야 확실히 멈춘다.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$ROOT_DIR/.pids"
mkdir -p "$PID_DIR"

BACKEND_LAUNCHER_PID_FILE="$PID_DIR/backend.launcher.pid"
FRONTEND_LAUNCHER_PID_FILE="$PID_DIR/frontend.launcher.pid"
BACKEND_LOG="$PID_DIR/backend.log"
FRONTEND_LOG="$PID_DIR/frontend.log"

BACKEND_PORT=8000
FRONTEND_PORT=5173

find_pid_by_port() {
  # netstat 출력에서 해당 포트로 LISTENING 중인 프로세스의 PID를 찾는다.
  # set -e 환경에서 grep이 못 찾으면(exit 1) 스크립트 전체가 죽으므로 || true로 방어한다.
  local port="$1"
  netstat -ano 2>/dev/null | grep -E "[:.]${port}[[:space:]].*LISTENING" | awk '{print $NF}' | head -n1 || true
}

start_backend() {
  if [ -n "$(find_pid_by_port "$BACKEND_PORT")" ]; then
    echo "[백엔드] 이미 실행 중 - http://localhost:$BACKEND_PORT"
    return
  fi
  (cd "$ROOT_DIR" && nohup uv run uvicorn app.main:app --reload --port "$BACKEND_PORT" >"$BACKEND_LOG" 2>&1 &
   echo $! > "$BACKEND_LAUNCHER_PID_FILE")
  echo "[백엔드] 시작됨 - http://localhost:$BACKEND_PORT (로그: .pids/backend.log)"
}

start_frontend() {
  if [ -n "$(find_pid_by_port "$FRONTEND_PORT")" ]; then
    echo "[프론트엔드] 이미 실행 중 - http://localhost:$FRONTEND_PORT"
    return
  fi
  (cd "$ROOT_DIR/frontend" && nohup npm run dev -- --port "$FRONTEND_PORT" >"$FRONTEND_LOG" 2>&1 &
   echo $! > "$FRONTEND_LAUNCHER_PID_FILE")
  echo "[프론트엔드] 시작됨 - http://localhost:$FRONTEND_PORT (로그: .pids/frontend.log)"
}

stop_by_port() {
  local port="$1" name="$2"
  local pid
  pid="$(find_pid_by_port "$port")"
  if [ -n "$pid" ]; then
    taskkill //F //T //PID "$pid" >/dev/null 2>&1 || true
    echo "[$name] 중지됨 (포트 $port, PID $pid)"
  else
    echo "[$name] 실행 중이 아님"
  fi
}

status_by_port() {
  local port="$1" name="$2"
  local pid
  pid="$(find_pid_by_port "$port")"
  if [ -n "$pid" ]; then
    echo "[$name] 실행 중 - http://localhost:$port (PID $pid)"
  else
    echo "[$name] 중지됨"
  fi
}

case "${1:-}" in
  start)
    start_backend
    start_frontend
    ;;
  stop)
    stop_by_port "$BACKEND_PORT" "백엔드"
    stop_by_port "$FRONTEND_PORT" "프론트엔드"
    rm -f "$BACKEND_LAUNCHER_PID_FILE" "$FRONTEND_LAUNCHER_PID_FILE"
    ;;
  status)
    status_by_port "$BACKEND_PORT" "백엔드"
    status_by_port "$FRONTEND_PORT" "프론트엔드"
    ;;
  *)
    echo "사용법: $0 {start|stop|status}"
    exit 1
    ;;
esac
