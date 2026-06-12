#!/usr/bin/env bash
# install.sh — 安裝 ccc 多帳號切換（依你裝了什麼，自動挑模組）
# 用法：bash install.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
BIN="$HOME/bin"
mkdir -p "$BIN"

has() { command -v "$1" >/dev/null 2>&1; }
install_one() { cp "$HERE/$1" "$BIN/$1"; chmod +x "$BIN/$1"; echo "  ✅ $BIN/$1"; }

echo "偵測環境…"
if ! has fzf; then
  case "$(uname -s)" in
    Darwin) echo "❌ 需要 fzf：brew install fzf" ;;
    Linux)  echo "❌ 需要 fzf：sudo apt install fzf（或 dnf/pacman/brew）" ;;
    *)      echo "❌ 需要 fzf，請先安裝後再執行" ;;
  esac
  exit 1
fi

# 偵測使用者的 shell rc（給後面的設定指引用正確檔名）
case "$(basename "${SHELL:-/bin/bash}")" in
  zsh)  RC="$HOME/.zshrc" ;;
  bash) RC="$HOME/.bashrc" ;;
  *)    RC="$HOME/.profile" ;;
esac
echo ""

# 選單核心一定裝
echo "安裝核心選單："
install_one ccc

# ── Claude 模組 ───────────────────────────────────────────────────────────────
if has claude; then
  echo "偵測到 Claude Code → 安裝 Claude 模組："
  install_one ccc-resume2
  install_one ccc-mirror-config
  install_one ccc-watch
  CLAUDE_OK=1
else
  echo "－ 沒偵測到 claude，略過 Claude 模組"
  CLAUDE_OK=0
fi

# ── Codex 模組 ────────────────────────────────────────────────────────────────
if has codex; then
  echo "偵測到 Codex → 安裝 Codex 模組："
  install_one ccc-codex-resume
  CODEX_OK=1
else
  echo "－ 沒偵測到 codex，略過 Codex 模組"
  CODEX_OK=0
fi

echo ""
echo "════════ 接下來的設定（只做你需要的）════════"
echo ""
echo "0) 確認 ~/bin 在 PATH："
echo "     echo 'export PATH=\"\$HOME/bin:\$PATH\"' >> $RC"
echo ""

if [ "$CLAUDE_OK" = 1 ]; then
  cat <<TXT
── Claude 第二帳號 ──────────────────────────
1) 設第二帳號目錄（絕對路徑，避免 keychain 雜湊漂移）：
     echo 'export CLAUDE_CONFIG_DIR_2="\$HOME/.claude-2"' >> $RC
     source $RC
2) 登入第二帳號一次（用第二個 email 跑 /login）：
     CLAUDE_CONFIG_DIR="\$HOME/.claude-2" claude

TXT
fi

if [ "$CODEX_OK" = 1 ]; then
  cat <<'TXT'
── Codex 多帳號 ─────────────────────────────
1) 建兩個 home 並各自登入（名字可自取，例 a / b）：
     CODEX_HOME="$HOME/.codex-homes/a" codex login
     CODEX_HOME="$HOME/.codex-homes/b" codex login
   （ccc 會自動列出 ~/.codex-homes 底下所有 home）

TXT
fi

echo "完成後輸入 ccc，選單只會顯示你實際裝好的 agent。"
echo "Antigravity / Gemini 若有裝會自動出現，沒有就不顯示，純選配。"
