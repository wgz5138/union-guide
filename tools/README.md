# tools/

兩套 Claude Code 個人工具，整合進本 repo 以便版本控管與分享。

## 📂 cccswitch/ — AI agent 多帳號無縫切換

把一個會撞使用限制的帳號，變成多個輪流用、且**同一場對話接得起來**的帳號。
支援 Claude Code 與 Codex，模組可分開裝。完整說明見 [`cccswitch/SKILL.md`](cccswitch/SKILL.md)。

> **多帳號（①②③…）**：Claude 帳號 ① = `~/.claude`，②③… = `~/.claude-2`、`~/.claude-3`…
> `ccc` 選單、跨帳號接力、狀態列徽章都會自動依「存在哪些 `~/.claude-N` 目錄」動態列出，
> 不限 2 個。新增一個帳號槽：`mkdir ~/.claude-3 && ccc-mirror-config ~/.claude-3`，
> 之後用該帳號登入一次即可（需付費方案；免費帳號無法使用 Claude Code）。

安裝（需 `fzf`；macOS 用 `brew install fzf`，Linux 用 `sudo apt install fzf`）：

```bash
bash tools/cccswitch/scripts/install.sh
```

它會偵測你裝了 `claude` 還是 `codex`，只裝對應模組，並印出後續設定步驟。

## 📂 statusline/ — 雙帳號額度 + context + git 狀態列

兩行式狀態列：第一行顯示 5h/7d 額度進度條、context 剩餘、目前帳號；第二行
顯示 git 分支、增刪行數、最後訊息。說明見 [`statusline/README.md`](statusline/README.md)。

```bash
cp tools/statusline/statusline-command.sh ~/.claude/
# 然後在 ~/.claude/settings.json 加入：
#   "statusLine": { "type": "command", "command": "bash $HOME/.claude/statusline-command.sh" }
```

需求：`jq`、`bash ≥ 4`、支援 truecolor 的終端機。

## 🩺 體檢腳本

每台機器裝好後（或之後想確認狀態），跑一次體檢（純檢查、不改任何東西）：

```bash
bash tools/healthcheck.sh
```

它會檢查：相依工具（jq/fzf/python3/git/claude）、PATH、ccc 腳本、statusline
（含實跑煙霧測試）、Claude 帳號槽與鏡像/登入狀態，最後給 ✅/⚠️/❌ 總結。
相容 macOS 內建 bash 3.2 / Linux bash 5 / WSL。

## 整合時修正的 bug

匯入時做了測試（Linux/bash 5.2），修掉以下問題：

| 檔案 | 問題 | 修正 |
|---|---|---|
| `statusline/statusline-command.sh` | 帳號區塊的 `5h`/`7d` 百分比顯示成 `35%%`（多一個 `%`），因為字串是經 `printf '%b'` 當參數輸出，而非格式字串 | `%%` → `%` |
| `statusline/statusline-command.sh` | 7d 重置日期在 Linux 完全不顯示：`fmt_reset_date` 的 `date -d` fallback 少了開頭的 `+`，GNU date 報錯 | 補上 `+` |
| `cccswitch/scripts/install.sh` | 寫死 `~/.zshrc` 與 `brew`，在 Linux/bash 給錯誤指引 | 依 `$SHELL` 偵測 rc 檔、依 `uname` 給對應的 fzf 安裝指令 |

## 後續強化：多帳號（①②③…）

原版 `ccc` / `ccc-resume2` / statusline 只寫死支援 2 個 Claude 帳號，已改寫為**動態支援任意帳號數**：

- `ccc`：依存在哪些 `~/.claude-N` 目錄動態列出帳號，並顯示下一個「未設定」槽。
- `ccc-resume2`：接力方向自動組出所有帳號間的配對（不再只有 1↔2）。
- `ccc-watch`：rate limit 提示改為「切換帳號接續」，交給 `ccc-resume2` 選目標。
- `statusline-command.sh`：帳號徽章 `badge_for` 支援 ①–⑨，並排區塊掃描所有 `~/.claude-N`。
- `ccc-mirror-config`：本來就吃任意目標目錄，無需改動。
