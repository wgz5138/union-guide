#!/usr/bin/env bash
# setup.sh — ccc + statusline 一鍵安裝器（偵測 OS，可重複跑）
# 用法：
#   bash tools/setup.sh                 # 裝 ccc + statusline（帳號①）
#   bash tools/setup.sh --accounts 3    # 另外預建帳號槽 ②③（空殼，等登入）
#   bash tools/setup.sh --no-deps       # 跳過自動裝相依工具
# 相容 macOS（內建 bash 3.2）/ Linux / WSL。純加裝，不刪你的東西。
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"     # = tools/
ACCOUNTS=1; DO_DEPS=1

while [ $# -gt 0 ]; do
  case "$1" in
    --accounts) ACCOUNTS="${2:-1}"; shift 2 ;;
    --accounts=*) ACCOUNTS="${1#*=}"; shift ;;
    --no-deps) DO_DEPS=0; shift ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) shift ;;
  esac
done

sec()  { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
ok()   { printf '  \033[32m✅\033[0m %s\n' "$1"; }
info() { printf '  \033[36mℹ️ \033[0m %s\n' "$1"; }
warn() { printf '  \033[33m⚠️ \033[0m %s\n' "$1"; }
die()  { printf '  \033[31m❌ %s\033[0m\n' "$1"; exit 1; }
has()  { command -v "$1" >/dev/null 2>&1; }
run()  { printf '  $ %s\n' "$*"; "$@"; }

# ── 偵測 OS 與 shell rc ───────────────────────────────────────────────────────
case "$(uname -s)" in
  Darwin) OS=mac ;;
  Linux)  OS=linux; grep -qiE 'microsoft|wsl' /proc/version 2>/dev/null && OS=wsl ;;
  *)      OS=other ;;
esac
case "$(basename "${SHELL:-/bin/bash}")" in
  zsh)  RC="$HOME/.zshrc" ;;
  bash) RC="$HOME/.bashrc" ;;
  *)    RC="$HOME/.profile" ;;
esac
sec "環境"
info "OS=${OS}    shell rc=${RC}"

# ── 1. 相依工具 ──────────────────────────────────────────────────────────────
sec "相依工具"
if [ "$DO_DEPS" = 1 ]; then
  missing=""
  for c in fzf jq python3 git; do has "$c" || missing="$missing $c"; done
  # mac 另外需要新版 bash（內建 3.2 太舊，statusline 顏色不全）
  if [ "$OS" = mac ] && ! { [ -x /opt/homebrew/bin/bash ] || [ -x /usr/local/bin/bash ]; }; then
    missing="$missing bash"
  fi
  if [ -n "$missing" ]; then
    info "缺少：${missing}"
    case "$OS" in
      mac)
        has brew || die "請先裝 Homebrew 再重跑：/bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        run brew install ${missing} ;;
      *)
        if   has apt-get; then run sudo apt-get update; run sudo apt-get install -y ${missing}
        elif has dnf;     then run sudo dnf install -y ${missing}
        elif has pacman;  then run sudo pacman -S --noconfirm ${missing}
        elif has apk;     then run sudo apk add ${missing}
        else die "找不到套件管理器，請手動安裝：${missing}"; fi ;;
    esac
  else
    ok "相依工具齊全（fzf/jq/python3/git）"
  fi
else
  warn "--no-deps：跳過相依工具安裝"
fi

# ── 2. Claude Code ───────────────────────────────────────────────────────────
sec "Claude Code"
if has claude; then
  ok "已安裝：$(claude --version 2>/dev/null | head -1)"
else
  warn "claude 沒裝，執行官方安裝器…"
  curl -fsSL https://claude.ai/install.sh | bash || die "Claude Code 安裝失敗，請見 https://code.claude.com/docs"
  export PATH="$HOME/.local/bin:$PATH"
fi

# ── 3. ccc 腳本 → ~/bin ──────────────────────────────────────────────────────
sec "ccc 腳本"
mkdir -p "$HOME/bin"
for f in ccc ccc-watch ccc-resume2 ccc-mirror-config; do
  cp "$HERE/cccswitch/scripts/$f" "$HOME/bin/$f"; chmod +x "$HOME/bin/$f"
done
ok "已安裝 ccc / ccc-watch / ccc-resume2 / ccc-mirror-config → ~/bin"
if has codex; then
  cp "$HERE/cccswitch/scripts/ccc-codex-resume" "$HOME/bin/"; chmod +x "$HOME/bin/ccc-codex-resume"
  ok "偵測到 codex → 也裝了 ccc-codex-resume"
fi

# ── 4. PATH 寫進 rc（不重複）─────────────────────────────────────────────────
sec "PATH"
add_path() { grep -qF "$1" "$RC" 2>/dev/null && info "已存在：$1" || { echo "$1" >> "$RC"; ok "加入 ${RC}：$1"; }; }
touch "$RC"
add_path 'export PATH="$HOME/bin:$PATH"'
add_path 'export PATH="$HOME/.local/bin:$PATH"'

# ── 5. statusline + settings.json（OS 對應的 bash 路徑）──────────────────────
sec "statusline"
mkdir -p "$HOME/.claude"
cp "$HERE/statusline/statusline-command.sh" "$HOME/.claude/"
BASHBIN="bash"
if [ "$OS" = mac ]; then
  for b in /opt/homebrew/bin/bash /usr/local/bin/bash; do [ -x "$b" ] && { BASHBIN="$b"; break; }; done
fi
SLCMD="$BASHBIN $HOME/.claude/statusline-command.sh"
SF="$HOME/.claude/settings.json"
[ -s "$SF" ] || echo '{}' > "$SF"
if has jq && jq -e . "$SF" >/dev/null 2>&1; then
  jq --arg c "$SLCMD" '.statusLine = {"type":"command","command":$c}' "$SF" > "$SF.tmp" && mv "$SF.tmp" "$SF"
  ok "statusline 已設定：$SLCMD"
else
  warn "settings.json 不是合法 JSON，沒動它。請手動加 statusLine（見 statusline/README.md）"
fi

# ── 6. 帳號槽（選配）─────────────────────────────────────────────────────────
if [ "${ACCOUNTS:-1}" -gt 1 ] 2>/dev/null; then
  sec "帳號槽 ②..${ACCOUNTS}"
  n=2
  while [ "$n" -le "$ACCOUNTS" ]; do
    mkdir -p "$HOME/.claude-$n"
    "$HOME/bin/ccc-mirror-config" "$HOME/.claude-$n" >/dev/null 2>&1 && ok "帳號槽 ${n} 已建立並鏡像設定" || warn "帳號槽 ${n} 鏡像失敗"
    n=$((n+1))
  done
fi

# ── 完成 ─────────────────────────────────────────────────────────────────────
sec "完成"
ok "安裝完畢（OS=${OS}）"
printf '\n  下一步：\n'
printf '    1) 讓 PATH 生效：  source %s   （或開新終端機）\n' "$RC"
printf '    2) 登入 Claude：   claude       （首次會走登入流程）\n'
printf '    3) 體檢驗證：      bash %s/healthcheck.sh\n' "$HERE"
[ "${ACCOUNTS:-1}" -gt 1 ] && printf '    4) 帳號 ②..%s 是空殼，等有付費帳號再登入啟用\n' "$ACCOUNTS"
printf '    選單：             ccc\n'
