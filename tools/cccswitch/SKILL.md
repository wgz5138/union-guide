---
name: ccc-switch
description: 在自己的電腦建立「AI agent 多帳號無縫切換」系統（ccc）。用兩個便宜帳號取代一個貴方案，撞到使用限制時一鍵切換、並把同一場對話接續到另一帳號繼續跑。支援 Claude Code 與 Codex，模組可分開裝（只有其中一個也行）。觸發詞：ccc、帳號切換、multi-account、第二個 claude 帳號、codex 多帳號、額度爆了怎麼切、conversation resume across accounts。
---

# ccc — AI agent 多帳號無縫切換

> 一句話：把一個會 hit limit 的帳號，變成兩個輪流用、且**同一場對話接得起來**的帳號。

## 核心精神：對話繼承（provider-agnostic）

不管是 Claude 還是 Codex，原理只有一句話：

> **用環境變數隔離身份，用「複製一場對話檔 + 在另一身份 resume」接續歷史。**

每一場對話其實是一個 `.jsonl` 檔躺在硬碟上。所以「換帳號繼續同一場對話」不需要任何雲端魔法——把那個檔複製到另一個帳號的目錄，再用那個帳號 `resume` 它就好。額度算第二個帳號的，脈絡卻完全不斷。

**⚠️ Claude Code 2.1.169+ 注意事項**：新版 jsonl 包含 `bridge-session` 條目（伺服器端對話狀態），綁定原帳號的 API session。`ccc-resume2` 會在複製時自動清除這些條目，讓目標帳號從本地紀錄重建對話。

這就是整套系統的靈魂。其他都是讓它順手的工程。

| | Claude Code | Codex |
|---|---|---|
| 身份隔離 | `CLAUDE_CONFIG_DIR` 環境變數 | `CODEX_HOME` 環境變數 |
| 對話檔位置 | `<config>/projects/<cwd>/<id>.jsonl` | `<home>/sessions/YYYY/MM/DD/rollout-*.jsonl` |
| 接續指令 | `claude --resume <id>` | `codex resume <uuid>` |
| 接力腳本 | `ccc-resume2` | `ccc-codex-resume` |

**你不必跟我一模一樣。** 只有 Claude 就裝 Claude 模組；只有 Codex 就裝 Codex 模組；兩個都有就都裝。Antigravity、Gemini 純選配，裝了 ccc 會自動偵測顯示，沒有就不出現。

## 安裝（自動挑模組）

前置：`fzf`（必要）、`python3`、`~/bin` 在 PATH；`claude` / `codex` 至少裝一個。

```bash
bash ~/.claude/skills/ccc-switch/scripts/install.sh
```

它會偵測你裝了什麼，只裝對應模組，並印出「接下來只做你需要的設定」。然後輸入 `ccc` 就有選單。

## Claude 模組

四層設計，進階用戶照這個複製：

| 層 | 機制 | 關鍵 term |
|---|---|---|
| **身份層** | 一個帳號 = 一個設定目錄 | `CLAUDE_CONFIG_DIR`。帳號1 = 不設（預設 `~/.claude`）；帳號2 = `~/.claude-2` |
| **認證層** | macOS Keychain 自動隔離 token | 服務名 = `Claude Code-credentials-<sha256(設定目錄絕對路徑)[:8]>`；**未設變數時用裸名** `Claude Code-credentials` |
| **設定層** | symlink 鏡像，自動同步 | `ccc-mirror-config` 把 `settings/rules/skills/commands/agents/hooks` 用 `ln -s` 鏈到帳號2 |
| **歷史層** | 按需複製單一對話檔（自動清除 bridge-session） | `ccc-resume2`：過濾 bridge-session → 複製 `.jsonl` → `claude --resume` |
| **偵測層** | rate limit 自動提示切換 | `ccc-watch`：包裝 claude，exit 時偵測 rate limit → 提示接力 |

### ⚠️ Keychain 雜湊陷阱（最大的雷）

Claude 的 token 服務名會根據 `CLAUDE_CONFIG_DIR` 做 sha256 雜湊。

- 帳號2 設了 `CLAUDE_CONFIG_DIR=~/.claude-2` → 找雜湊版條目 ✅
- **但若對「主帳號」也硬設 `CLAUDE_CONFIG_DIR=~/.claude`** → 去找雜湊版（空的）→ **每次都要重登**

**鐵律：resume 回主帳號必須「裸跑」**（完全不設變數）。`ccc-resume2` 已內建判斷。

設定：
```bash
echo 'export CLAUDE_CONFIG_DIR_2="$HOME/.claude-2"' >> ~/.zshrc && source ~/.zshrc
CLAUDE_CONFIG_DIR="$HOME/.claude-2" claude   # 用第二個 email 跑 /login
```

## Codex 模組

Codex 用 `CODEX_HOME` 隔離身份，登入 token 是各 home 自己的 `auth.json`（refresh_token 自動刷新，不會每次重登，沒有 Keychain 雜湊雷）。

設定：
```bash
CODEX_HOME="$HOME/.codex-homes/a" codex login
CODEX_HOME="$HOME/.codex-homes/b" codex login
```
`ccc` 會自動列出 `~/.codex-homes` 底下所有 home，外加「Codex 接力」。

## ⚠️ 安全邊界：哪些絕對不能共用

兩帳號**同時跑**時，這些檔會被並發寫入弄壞，必須各自獨立：
Claude 的 `.claude.json` / `projects/` / `sessions/`；Codex 的各自 `sessions/`。

這也是為什麼接續用「**按需複製單一對話檔**」，而不是把整個資料夾 symlink 接通——後者雙開會 corrupt（Anthropic issue #18998 / #5024）。

## 用法

| 你要做的事 | 怎麼做 |
|---|---|
| 一般工作 | `ccc` → 選主帳號（自動走 `ccc-watch`，rate limit 時會提示切換） |
| 撞 limit、自動提示 | Claude Code 因 rate limit 結束 → `ccc-watch` 自動問「切帳號？(Y/n)」→ 按 Y 直接接力 |
| 撞 limit、手動接力 | `ccc` → `接力` → 選方向 → 挑對話 |
| 直接在第二帳號開新對話 | `ccc` → 選第二帳號（Claude 會先自動鏡像設定） |

切過去後，除了登入身份不同，設定/skill/hook 全一致，幾乎感覺不到換了帳號。

**Rate limit 自動偵測**：從 `ccc` 選單啟動的 Claude Code 都經過 `ccc-watch` 包裝。當 Claude Code 因 rate limit 退出時，會自動偵測並提示切換帳號，不需要手動輸入任何指令。

## Desktop App / 網頁端搭配

CLI 用環境變數切；**Desktop App 或網頁端**用 **Chrome 使用者系統（User Profile）**：User 1 登帳號1、User 2 登帳號2，切 Chrome 使用者就等於切帳號，cookie 互不干擾。兩條路線互補。

## 限制（誠實說）

- 不是「即時雙開共享同一份 live 歷史」——那會 corrupt。是**按需把一場對話搬過去**。
- macOS 的 Keychain 雜湊雷只適用 Claude on macOS；Linux／Codex 不受此影響。
- 接續的是對話內容，不是跨帳號的即時記憶同步。
- 接力只複製對話檔（`.jsonl`），不含 subagents/、file-history/ 等輔助資料。對話脈絡完整，但 `/rewind` 功能可能不完整。
- 若兩個帳號各自延伸同一場對話（不同內容），接力時會提示你選擇是否覆蓋。

## 公開分享說明

本 skill 不含任何個資或密鑰，全部用 `$HOME` 相對路徑；token 永遠留在你自己的 Keychain / `auth.json`，不會被腳本讀出或搬移（只搬「對話檔」）。可安全放上公開 GitHub。
