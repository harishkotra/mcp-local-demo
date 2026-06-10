#!/usr/bin/env bash
# Usage: ./run_demo.sh [naive|hardened|compare] [model]
# Default: hardened qwen3.5:2b

set -e
cd "$(dirname "$0")"

MODE="${1:-hardened}"
MODEL="${2:-qwen3.5:2b}"

echo ""
echo "┌─────────────────────────────────────────────┐"
echo "│     Running MCP Fully Local — Demo           │"
echo "│     Mode: $MODE   Model: $MODEL"
echo "│     No tokens leave this machine. Real weather via wttr.in  │"
echo "└─────────────────────────────────────────────┘"
echo ""

case "$MODE" in
  naive)
    echo ">>> Naive client — expect failures"
    /Users/kotra/.venv/bin/python3 client_naive.py "$MODEL"
    ;;
  hardened)
    echo ">>> Hardened client — same model, better results"
    /Users/kotra/.venv/bin/python3 client_hardened.py "$MODEL"
    ;;
  compare)
    echo ">>> Model comparison table"
    /Users/kotra/.venv/bin/python3 compare_models.py
    ;;
  side-by-side)
    # Requires tmux
    if ! command -v tmux &>/dev/null; then
      echo "tmux not found — run naive and hardened separately"
      exit 1
    fi
    SESSION="mcp-demo"
    tmux new-session -d -s "$SESSION" -x 220 -y 50
    tmux split-window -h -t "$SESSION"
    tmux send-keys -t "$SESSION:0.0" "python3 client_naive.py $MODEL" Enter
    tmux send-keys -t "$SESSION:0.1" "sleep 2 && python3 client_hardened.py $MODEL" Enter
    tmux attach-session -t "$SESSION"
    ;;
  *)
    echo "Usage: $0 [naive|hardened|compare|side-by-side] [model]"
    exit 1
    ;;
esac
