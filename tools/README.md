# tools/

兩套 Claude Code 個人工具，整合進本 repo 以便版本控管與分享。

## 📂 cccswitch/ — AI agent 多帳號無縫切換

把一個會撞使用限制的帳號，變成兩個輪流用、且**同一場對話接得起來**的帳號。
支援 Claude Code 與 Codex，模組可分開裝。完整說明見 [`cccswitch/SKILL.md`](cccswitch/SKILL.md)。

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

## 整合時修正的 bug

匯入時做了測試（Linux/bash 5.2），修掉以下問題：

| 檔案 | 問題 | 修正 |
|---|---|---|
| `statusline/statusline-command.sh` | 帳號區塊的 `5h`/`7d` 百分比顯示成 `35%%`（多一個 `%`），因為字串是經 `printf '%b'` 當參數輸出，而非格式字串 | `%%` → `%` |
| `statusline/statusline-command.sh` | 7d 重置日期在 Linux 完全不顯示：`fmt_reset_date` 的 `date -d` fallback 少了開頭的 `+`，GNU date 報錯 | 補上 `+` |
| `cccswitch/scripts/install.sh` | 寫死 `~/.zshrc` 與 `brew`，在 Linux/bash 給錯誤指引 | 依 `$SHELL` 偵測 rc 檔、依 `uname` 給對應的 fzf 安裝指令 |
