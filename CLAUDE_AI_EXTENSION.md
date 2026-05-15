# Claude.ai Token Tracking — Browser Extension Plan

## Problem

The `tc` token counter reads Claude Code CLI session transcripts from
`~/.claude/projects/`. Sessions on **claude.ai** (including Claude Designer,
Projects, and standard chat) are never written to disk — they exist only inside
the browser. There is no local file, no Admin API access for individual accounts,
and no data export that includes token counts. As a result, claude.ai usage is
invisible to `tc`.

## Goal

Capture per-turn token usage from claude.ai sessions and feed it into the
existing `tc` pipeline so that `tc logs`, `tc window`, `tc watch`, and
`tc forecast` all reflect the full picture of Claude usage across both
Claude Code CLI and claude.ai.

---

## How claude.ai Delivers Token Data

When claude.ai sends a response, it streams Server-Sent Events (SSE) from
`https://api.claude.ai/`. The final event in each turn contains a
`message_delta` or `message_stop` payload that includes a `usage` object:

```json
{
  "type": "message_delta",
  "usage": {
    "input_tokens": 4821,
    "output_tokens": 312,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 3950
  }
}
```

This is structurally identical to what the Anthropic Messages API returns and
what the Claude Code CLI already writes to its JSONL transcripts.

---

## Proposed Architecture

```
 Browser (chrome.ai / Firefox)
 ┌─────────────────────────────────────────┐
 │  Content script / Background service   │
 │  - Intercepts fetch/XHR to api.claude.ai│
 │  - Parses SSE stream                   │
 │  - Extracts usage block per turn       │
 │  - Sends turn record via Native MSG    │
 └──────────────────┬──────────────────────┘
                    │ Native Messaging
 ┌──────────────────▼──────────────────────┐
 │  Local companion (Python or Node)      │
 │  - Receives turn records               │
 │  - Appends to                          │
 │    ~/.claude/claude-ai/sessions.jsonl  │
 └──────────────────┬──────────────────────┘
                    │ file read (existing infra)
 ┌──────────────────▼──────────────────────┐
 │  tc (TokenCounter CLI)                 │
 │  - iter_sessions / iter_recent_turns   │
 │    already scan ~/.claude/ directories │
 └─────────────────────────────────────────┘
```

### Components to build

#### 1. Browser Extension

- **Manifest V3** (Chrome) or equivalent (Firefox)
- Background service worker intercepts all requests to `https://api.claude.ai/`
- Reads the SSE response stream, looks for `usage` objects
- Assembles a turn record per response:

```jsonc
{
  "type": "assistant",
  "timestamp": "2026-05-15T10:34:21.000Z",
  "source": "claude.ai",
  "project": "Claude Designer",   // from page URL / document title
  "session_id": "<uuid>",         // from the conversation ID in the URL
  "message": {
    "model": "claude-opus-4-7",
    "usage": {
      "input_tokens": 4821,
      "output_tokens": 312,
      "cache_creation_input_tokens": 0,
      "cache_read_input_tokens": 3950
    }
  }
}
```

- Sends each completed turn record to the local companion via
  [Chrome Native Messaging](https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging)

#### 2. Local Companion Process

- Small always-on process (Python script or Node) registered as a Native
  Messaging host
- Receives turn records from the extension
- Appends each record as a JSONL line to:
  `~/.claude/claude-ai/<session-id>.jsonl`
- Directory structure mirrors the Claude Code layout so `tc` can read it with
  zero changes

#### 3. TokenCounter (`tc`) changes needed

The `tracker.py` functions `iter_sessions` and `iter_recent_turns` already
accept a `projects_dir` parameter. The only change needed is to scan an
additional directory:

```python
CLAUDE_AI_DIR = Path.home() / ".claude" / "claude-ai"
```

Or pass both dirs to the existing functions. The JSONL record format above is
compatible with what `_summarize_session` and `iter_turns` already parse.

---

## Scope of Work

| Component | Language | Effort estimate |
|-----------|----------|-----------------|
| Browser extension (MV3) | JavaScript | Medium |
| SSE stream parser in extension | JavaScript | Small |
| Native Messaging host | Python | Small |
| JSONL writer + session grouping | Python | Small |
| `tc` multi-directory support | Python | Trivial |

---

## Key Open Questions

1. **Conversation ID** — does the claude.ai URL reliably expose a stable
   conversation/session UUID that can be used as the JSONL filename?
2. **Project name** — how to extract the project or space name from the page
   context (URL path, page title, or DOM element)?
3. **Model name** — is the model identifier present in the SSE stream, or does
   it need to be read from the page UI?
4. **Firefox support** — Native Messaging works on Firefox too; worth targeting
   both from the start.
5. **Companion process startup** — should the companion be a persistent daemon
   (registered as a Windows Service / launchd agent) or started on-demand by
   the extension?

---

## Integration Test Plan

1. Open a claude.ai conversation, send a few messages
2. Confirm `~/.claude/claude-ai/<session-id>.jsonl` is being written
3. Run `tc logs` — session should appear in the table alongside Claude Code sessions
4. Run `tc window` — claude.ai turns should be included in the 5h rolling count
5. Run `tc watch` — 5h window line should reflect claude.ai activity
