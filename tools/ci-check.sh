#!/usr/bin/env bash
# ci-check.sh — 本地與 CI 共用的把關檢查；任何一項失敗就回傳非 0。
# 本地跑：  bash tools/ci-check.sh
# CI 會在每次 push（動到 tools/）時自動跑這支。
set -uo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

SHELL_FILES="tools/setup.sh tools/healthcheck.sh tools/ci-check.sh \
tools/cccswitch/scripts/ccc tools/cccswitch/scripts/ccc-watch \
tools/cccswitch/scripts/ccc-resume2 tools/cccswitch/scripts/ccc-mirror-config \
tools/cccswitch/scripts/ccc-codex-resume tools/cccswitch/scripts/install.sh \
tools/statusline/statusline-command.sh"

FAIL=0
step() { printf '\n=== %s ===\n' "$1"; }
pass() { printf '  \033[32mPASS\033[0m %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; FAIL=1; }

# ── 1. 語法 ──────────────────────────────────────────────────────────────────
step "1) bash -n 語法檢查"
for f in $SHELL_FILES; do
  if bash -n "$f" 2>/dev/null; then pass "$f"; else fail "$f : 語法錯誤"; fi
done

# ── 2. shellcheck（只在 error 級擋；warning 為風格，不擋）────────────────────
step "2) shellcheck (error 級)"
if command -v shellcheck >/dev/null 2>&1; then
  for f in $SHELL_FILES; do
    if shellcheck -S error "$f" >/dev/null 2>&1; then pass "$f"
    else fail "$f : shellcheck error"; shellcheck -S error "$f" || true; fi
  done
else
  printf '  SKIP : 沒裝 shellcheck（CI 會自動裝）\n'
fi

# ── 3. 全形字地雷掃描（$var 緊接非 ASCII → macOS bash 3.2 會炸）─────────────
step "3) multibyte landmine scan"
if hits=$(grep -nP '\$[A-Za-z_][A-Za-z0-9_]*[^\x00-\x7F]' $SHELL_FILES 2>/dev/null); then
  fail "發現 \$var 緊接全形字（請改 \${var}）："
  printf '%s\n' "$hits"
else
  pass "no landmines"
fi

# ── 4. statusline 行為煙霧測試 ───────────────────────────────────────────────
step "4) statusline smoke tests"
SL="tools/statusline/statusline-command.sh"
sample='{"rate_limits":{"five_hour":{"used_percentage":42,"resets_at":9999999999},"seven_day":{"used_percentage":18,"resets_at":9999999999}},"context_window":{"used_percentage":30},"model":{"display_name":"Test"},"workspace":{"current_dir":"/tmp/x"}}'
[ -n "$(printf '%s' "$sample" | bash "$SL" 2>/dev/null)" ] && pass "wide mode 有輸出" || fail "wide mode 無輸出"
[ -n "$(printf '%s' "$sample" | COLUMNS=40 bash "$SL" 2>/dev/null)" ] && pass "narrow mode 有輸出" || fail "narrow mode 無輸出"
if printf '%s' '{}' | bash "$SL" >/dev/null 2>&1; then pass "空 JSON 不崩"; else fail "空 JSON 崩潰"; fi

# ── 結果 ─────────────────────────────────────────────────────────────────────
step "結果"
if [ "$FAIL" -eq 0 ]; then printf '  \033[32m✅ 全部通過\033[0m\n'; else printf '  \033[31m❌ 有檢查失敗\033[0m\n'; fi
exit "$FAIL"
