#!/usr/bin/env bash
# healthcheck.sh — ccc / statusline 安裝體檢（read-only，不改任何東西）
# 在每台機器各跑一次：  bash tools/healthcheck.sh
# 相容 macOS 內建 bash 3.2 / Linux bash 5 / WSL。
set -uo pipefail

OK=0; WARN=0; BAD=0
sec()  { printf '\n\033[1m== %s ==\033[0m\n' "$1"; }
ok()   { printf '  \033[32m✅\033[0m %s\n' "$1"; OK=$((OK+1)); }
warn() { printf '  \033[33m⚠️ \033[0m %s\n' "$1"; WARN=$((WARN+1)); }
bad()  { printf '  \033[31m❌\033[0m %s\n' "$1"; BAD=$((BAD+1)); }
has()  { command -v "$1" >/dev/null 2>&1; }

acct_dir() { [ "$1" = 1 ] && echo "$HOME/.claude" || echo "$HOME/.claude-$1"; }

# ── 環境 ─────────────────────────────────────────────────────────────────────
sec "環境"
OS=$(uname -s)
printf '  作業系統：%s    shell：%s\n' "$OS" "$(basename "${SHELL:-?}")"
bv="${BASH_VERSINFO:-0}"
if [ "${bv:-0}" -ge 4 ]; then ok "bash ${BASH_VERSION}（>= 4，狀態列顏色完整）"
else warn "bash ${BASH_VERSION:-未知} < 4：statusline 請用新版 bash 跑（mac：brew install bash，設定用 /opt/homebrew/bin/bash）"; fi

# ── 相依工具 ─────────────────────────────────────────────────────────────────
sec "相依工具"
for c in jq python3 git fzf; do
  if has "$c"; then ok "${c}：$(command -v "$c")"; else
    [ "$c" = fzf ] && bad "$c 沒裝（ccc 選單需要）" || warn "$c 沒裝"
  fi
done
if has claude; then ok "claude：$(claude --version 2>/dev/null | head -1)"
else bad "claude 沒裝或不在 PATH（核心）"; fi

# ── PATH ─────────────────────────────────────────────────────────────────────
sec "PATH"
case ":$PATH:" in *":$HOME/bin:"*) ok "~/bin 在 PATH";; *) warn "~/bin 不在 PATH（ccc 可能找不到）";; esac
case ":$PATH:" in *":$HOME/.local/bin:"*) ok "~/.local/bin 在 PATH";; *) warn "~/.local/bin 不在 PATH（claude 可能找不到）";; esac

# ── ccc 腳本 ─────────────────────────────────────────────────────────────────
sec "ccc 腳本"
for s in ccc ccc-watch ccc-resume2 ccc-mirror-config; do
  if has "$s"; then ok "$s"; else warn "$s 不在 PATH（跑 install.sh 安裝）"; fi
done

# ── statusline ───────────────────────────────────────────────────────────────
sec "statusline 狀態列"
SLF="$HOME/.claude/statusline-command.sh"
[ -f "$SLF" ] && ok "腳本存在：$SLF" || bad "找不到 ${SLF}（cp tools/statusline/statusline-command.sh ~/.claude/）"
SETTINGS="$HOME/.claude/settings.json"
if [ -f "$SETTINGS" ]; then
  if has jq && jq -e . "$SETTINGS" >/dev/null 2>&1; then
    cmd=$(jq -r '.statusLine.command // empty' "$SETTINGS" 2>/dev/null)
    [ -n "$cmd" ] && ok "settings.json 已設 statusLine：$cmd" || warn "settings.json 沒有 statusLine 設定"
  else bad "settings.json 不是合法 JSON"; fi
else warn "找不到 settings.json（登入 claude 後會建立，或自行加 statusLine）"; fi
# 實跑一次煙霧測試
if [ -f "$SLF" ]; then
  out=$(printf '%s' '{"rate_limits":{"five_hour":{"used_percentage":5,"resets_at":9999999999}},"context_window":{"used_percentage":10},"workspace":{"current_dir":"'"$PWD"'"}}' | bash "$SLF" 2>/dev/null)
  [ -n "$out" ] && ok "煙霧測試通過（有輸出）" || bad "煙霧測試無輸出（檢查 jq / bash 版本）"
fi

# ── Claude 帳號槽 ────────────────────────────────────────────────────────────
sec "Claude 帳號槽"
found=0
for n in $(seq 1 9); do
  d=$(acct_dir "$n")
  [ -d "$d" ] || continue
  found=$((found+1))
  note=""
  # 是否已鏡像主帳號設定（symlink）
  [ "$n" != 1 ] && { [ -L "$d/settings.json" ] && note="（設定已鏡像）" || note="（設定未鏡像，可跑 ccc-mirror-config ${d}）"; }
  # 是否已登入（Linux/WSL 看 .credentials.json；mac 在 Keychain 無法直接驗）
  login="?"
  [ -f "$d/.credentials.json" ] && login="已登入"
  ok "帳號 $n 槽：$d  登入=$login $note"
done
[ "$found" -gt 0 ] || warn "找不到任何 ~/.claude 帳號目錄"
[ "$OS" = "Darwin" ] && printf '     （mac 的登入狀態存在 Keychain，本腳本無法直接讀，顯示 ? 屬正常）\n'

# ── 總結 ─────────────────────────────────────────────────────────────────────
sec "總結"
printf '  ✅ %d 項正常    ⚠️  %d 項提醒    ❌ %d 項要處理\n' "$OK" "$WARN" "$BAD"
if [ "$BAD" -eq 0 ] && [ "$WARN" -eq 0 ]; then
  printf '  \033[32m這台機器一切健康！\033[0m\n'
elif [ "$BAD" -eq 0 ]; then
  printf '  大致健康，⚠️ 提醒項多半是「選配/未來才用到」，日常可忽略。\n'
else
  printf '  有 ❌ 項目需要處理，照各行括號裡的指令修即可。\n'
fi
