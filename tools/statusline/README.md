# Status Line Setup

The `statusline-command.sh` script powers a rich two-line Claude Code status bar.

## What it shows

**Line 1 (resources):**
```
14:32  ②  my-project  [claude-sonnet-4-5]  ctx 42%    ① 5h ████░░░░ 35% →16:00  7d ██░░░░░░ 18%    ② 5h ░░░░░░░░ 4% →23:00  7d ░░░░░░░░ 6%
```

**Line 2 (work context):**
```
⎇ main*  +12/-3    ⏱ codex: idle
```

- **①②** — current account badge (`*` marks active)  
- **5h / 7d** — quota bars with time-until-reset  
- **ctx** — context window remaining  
- **⎇ branch\*** — git branch + dirty marker  
- **+N/-N** — uncommitted diff stats

## Setup

### 1. Copy the script

```bash
cp statusline-command.sh ~/.claude/
```

### 2. Add to Claude Code settings

Edit `~/.claude/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "bash /Users/YOUR_USERNAME/.claude/statusline-command.sh"
  }
}
```

Replace `/Users/YOUR_USERNAME` with your actual home path (or use `$HOME` if your shell expands it there).

### 3. For dual-account (account 2)

Run `ccc-mirror-config` to symlink the script into account 2's config dir:

```bash
ccc-mirror-config
```

Or manually add to `~/.claude-2/settings.json`:

```json
{
  "statusLine": {
    "type": "command",
    "command": "bash /Users/YOUR_USERNAME/.claude/statusline-command.sh"
  }
}
```

Both accounts share the same script. The script auto-detects which account is active from `$CLAUDE_CONFIG_DIR`.

## Requirements

- `jq` — JSON parsing
- `bash` ≥ 4 (macOS ships bash 3; install via `brew install bash` and use `/opt/homebrew/bin/bash`)
- A terminal with ANSI truecolor support (Ghostty, iTerm2, Kitty, WezTerm all work)

## Optional: Codex status integration

The script calls `${CLAUDE_CONFIG_DIR:-~/.claude}/scripts/codex-statusline.sh` if it exists.
This is a separate script you can write to show Codex job status in line 2.
If the file doesn't exist, that segment is simply omitted.

## Quota cache

The script writes quota data to `~/.claude-quota-cache/1.json` and `~/.claude-quota-cache/2.json` so both account status lines can show the other account's quota without being active.
