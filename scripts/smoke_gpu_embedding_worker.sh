#!/usr/bin/env bash
set -euo pipefail

WORKER_DIR="${AFH_GPU_WORKER_DIR:-$HOME/codex-gpu}"
PYTHON_BIN="${AFH_GPU_PYTHON:-$WORKER_DIR/envs/raganything/bin/python}"
HOST="${AFH_GPU_WORKER_HOST:-127.0.0.1}"
PORT="${AFH_GPU_WORKER_PORT:-8010}"
LOG_FILE="${AFH_GPU_WORKER_LOG:-/tmp/afh_gpu_embedding_worker.log}"

cd "$WORKER_DIR"
"$PYTHON_BIN" -m uvicorn gpu_rag_embedding_worker:app --host "$HOST" --port "$PORT" >"$LOG_FILE" 2>&1 &
pid=$!
trap 'kill "$pid" >/dev/null 2>&1 || true' EXIT

sleep 5
curl -fsS "http://$HOST:$PORT/health"
