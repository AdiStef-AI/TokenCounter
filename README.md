# TokenCounter

CLI tool for Claude token usage transparency.

## Sample output

```
$ tc logs --limit 6

                                      Sessions
| Project      | Turns |    Input |    Cache rd |    Output |       Total | Model   |
|--------------|-------|----------|-------------|-----------|-------------|---------|
| TokenCounter |   157 |      227 |   9,360,674 |    81,799 |  10,176,342 | sonnet- |
| Adi          |    80 |      268 |   2,710,053 |    36,569 |   3,007,602 | sonnet- |
| Bank         |    50 |       84 |   1,842,030 |    59,203 |   2,123,723 | sonnet- |
| Adi          |    25 |    7,941 |     725,842 |    13,603 |     815,031 | sonnet- |
| CardDispute  |    76 |    7,265 |   4,994,759 |    69,520 |   5,316,859 | sonnet- |
| SequenceDiag |    62 |      122 |   2,717,726 |    77,343 |   2,861,428 | sonnet- |

+------ Token Usage Summary -------+
| Sessions scanned:   11           |
| Total turns:        1,137        |
| Input tokens:       16,811       |
| Cache reads:        72,388,315   |
| Cache created:      3,755,002    |
| Output tokens:      822,992      |
| -------------------------------- |
| Grand total:        76,983,120   |
+----------------------------------+
```

```
$ tc forecast --days 14

Daily Token Usage
  + ..-@.
  2026-04-29 -> 2026-05-13  (peak: 6,931,442)

+--------------- Forecast ----------------+
| Avg daily usage:    2,565,849 tokens    |
| Trend:              +108,760 tokens/day |
| Projected 7 days:   3,653,451           |
| Projected 30 days:  6,154,937           |
+-----------------------------------------+
```

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

Use `--project` to narrow results to a single project:

```
$ tc logs --project TokenCounter

                                      Sessions
| Project      | Turns |    Input |   Cache rd |   Output |      Total | Model   |
|--------------|-------|----------|------------|----------|------------|---------|
| TokenCounter |   162 |      232 |  9,845,070 |   82,828 | 10,664,768 | sonnet- |

+------ Token Usage Summary -------+
| Sessions scanned:   1            |
| Total turns:        162          |
| Input tokens:       232          |
| Cache reads:        9,845,070    |
| Cache created:      736,638      |
| Output tokens:      82,828       |
| -------------------------------- |
| Grand total:        10,664,768   |
+----------------------------------+
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

### `tc window` — Rolling 5-hour usage window

Shows how many tokens you've used across all sessions in the last 5 hours — the same window that drives Claude Code's built-in `/usage` rate-limit display.

```bash
tc window                          # show rolling 5h stats
tc window --set-limit 10000000     # save your plan's token limit (enables % bar)
tc window --plan-limit 5000000     # one-time override, not saved
tc window --hours 3                # use a 3h window instead
```

```
$ tc window --set-limit 10000000

Plan limit saved: 10,000,000 tokens per 5h window
+--------------------------- Rolling 5h Window ---------------------------+
| ##############.......................... 36.4% (3,643,109 / 10,000,000) |
| Window opened:  09:45 AM  (27m ago)                                     |
| Pressure drops: 02:45 PM  (in 4h 32m)                                   |
+-------------------------------------------------------------------------+
```

The plan limit is saved to `~/.claude/tokencounter_config.json` and reused by all subsequent calls. Run `tc window` without `--set-limit` any time after that to get a fresh snapshot.

### `tc watch` — Live context monitor

Watches a session file and alerts when approaching the context limit. Also shows the rolling 5h window usage inline.

```bash
tc watch                               # watches most recent session
tc watch path/to/session.jsonl
tc watch --model claude-haiku-4-5 --interval 10
tc watch --plan-limit 10000000         # include 5h window % bar
tc watch --no-window                   # hide the 5h window line
```

```
$ tc watch

Project: TokenCounter  |  Session: 04db72be-1edc-43c6-a8ae-ba905e0d4682.jsonl  |  Turns: 335
model=claude-sonnet-4-6  limit=1,000,000  every 5.0s  (Ctrl+C to stop)

 OK Context: ######.................................. 15.9% (158,992 / 1,000,000)
 5h  window: ###############......................... 37.8% (3,777,569 / 10,000,000)  resets 02:45 PM
```

The model and context limit are auto-detected from the transcript on every refresh. The 5h window line uses the saved plan limit from `tc window --set-limit`.

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
