# 接續包（換新對話用）

> **為什麼需要這個**：對話太長會被自動「壓縮」（compact），早期細節會被摘要掉。
> 與其在舊對話硬撐，不如**開新對話**、貼下面的「開場白」，把脈絡一次帶過去。
> **這份檔案放在 repo 裡**（不是 `/tmp`），所以換電腦、換對話、容器重開都還在。

---

## 🟢 開場白（複製貼到新對話第一句）

> 我是 wgz5138。接續 union-guide 專案，分支 `claude/can-you-open-it-o6mb8d`。
> 請先讀 `tools/HANDOFF.md` 和 `tools/README.md` 了解現況，再等我給新任務。

就這樣。新對話的 Claude 會自己讀這兩個檔，不用你再解釋一長串。

---

## 📌 目前狀態（2026-06）

| 項目 | 狀態 |
|---|---|
| **ccc 多帳號切換**（①②③…N 動態） | ✅ 完成，三台機器都裝好 |
| **statusline 狀態列**（額度條+context+git） | ✅ 完成 |
| **setup.sh 一鍵安裝器** | ✅ 完成（偵測 OS、可重複跑） |
| **healthcheck.sh 體檢** | ✅ 三台機器都 18/18 全過 |
| **CI（`.github/workflows/tools-ci.yml`）** | ✅ 綠燈 |
| **三台機器**：Mac mini / Win 和平 / Win 左營 | ✅ 全裝好（左營已升 WSL2） |

→ **工會這邊的工具任務都收尾了。** 沒待辦就是純維護。

---

## 🟡 唯一在追的外部任務：job104 爬蟲 CI

- 在**另一個 Claude Code session**（左營電腦）做，不是這個對話。
- 進度：MySQL 密碼 `root1234` 已從程式碼搬到 `.env`（讀環境變數）。
- 待做：建 `.github/workflows/ci.yml` → 開分支/PR → 綠燈才合併。
- 細節交接包在那個 session；本 repo 不放 job104 的東西。
- ⚠️ 鐵則：repo 設 **Private**、`.env` 進 `.gitignore`、**絕不 commit 帳密**。

---

## 🧠 常用速查（免得又問一次）

- **切模型**：`/model` → Opus（最強最耗）/ Sonnet（主力高CP）/ Haiku（最省、簡單事用）。
- **額度**：Pro 是 5 小時滾動重置 + 每週重置；狀態列會顯示重置時間與百分比。
- **免費帳號**（wcj0727、nc6813）**不能用 Claude Code**，只有付費 Pro/Max 能用。
- **新增第 N 個帳號槽**：`mkdir ~/.claude-N && ccc-mirror-config ~/.claude-N`，再用該帳號登入一次。
- **對話被壓縮**＝正常，超過 200k 視窗就會發生；長任務建議分段開新對話。

---

## 📂 重點檔案位置

- `tools/README.md` — 工具總說明
- `tools/cccswitch/scripts/ccc*` — 多帳號切換腳本
- `tools/statusline/statusline-command.sh` — 狀態列
- `tools/setup.sh` — 一鍵安裝
- `tools/healthcheck.sh` — 體檢
- `tools/ci-check.sh` — CI 本地版
