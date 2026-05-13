# TokenCounter

CLI tool for Claude token usage transparency.

## Install

```bash
pip install -e .
```

The `tc` command will be available after adding Python's Scripts directory to PATH, or run via `python -m tokencounter.cli`.

## Commands

### `tc logs` — Scan Claude Code transcripts

Reads all JSONL session files from `~/.claude/projects/` and shows token usage per session.

```bash
tc logs                        # all sessions
tc logs --project TokenCounter # filter by project name
tc logs --limit 5              # top 5 sessions
tc logs --chart                # include daily usage chart
tc logs --no-sync              # don't save to local DB
```

Token columns:
- **Input** — fresh input tokens (not cached)
- **Cache rd** — cache read tokens (cheaper)
- **Output** — response tokens

### `tc count` — Count tokens in a prompt

Uses the Anthropic `count_tokens` endpoint (requires `ANTHROPIC_API_KEY`).

```bash
echo "My prompt here" | tc count
tc count "My prompt"
tc count --file prompt.txt
tc count --file prompt.txt --system "You are a helpful assistant"
tc count --model claude-haiku-4-5 --file prompt.txt
```

### `tc forecast` — Project future usage

Uses historical data from the local DB (populated by `tc logs`).

```bash
tc forecast                  # last 30 days
tc forecast --days 14        # last 14 days
tc forecast --session 50000  # also show how many days until context full
```

### `tc watch` — Live context monitor

Watches a session file and alerts when approaching the context limit.

```bash
tc watch                     # watches most recent session
tc watch path/to/session.jsonl
tc watch --model claude-haiku-4-5 --interval 10
```

### `tc usage` — Admin API usage report

Requires an Admin API key (`sk-ant-admin...`) and an organization account.

```bash
export ANTHROPIC_ADMIN_KEY=sk-ant-admin-...
tc usage --days 7 --group model
tc usage --days 30 --group workspace_id
```

## Token types explained

| Type | What it is | Billed at |
|------|-----------|-----------|
| Input | Fresh context tokens | Full rate |
| Cache creation | Tokens written to prompt cache | ~1.25x |
| Cache read | Tokens retrieved from cache | ~0.1x |
| Output | Tokens generated | Full rate |

## Data storage

Usage history is saved to `~/.claude/tokencounter.db` (SQLite). Run `tc logs` to populate it, then `tc forecast` to analyze trends.
