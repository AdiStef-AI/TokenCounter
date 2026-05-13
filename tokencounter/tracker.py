"""Reads Claude Code local JSONL transcripts and extracts token usage."""

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


CLAUDE_DIR = Path.home() / ".claude" / "projects"


@dataclass
class TurnUsage:
    session_id: str
    project_path: str
    timestamp: datetime
    model: str
    input_tokens: int
    cache_creation_tokens: int
    cache_read_tokens: int
    output_tokens: int

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.cache_creation_tokens + self.cache_read_tokens + self.output_tokens

    @property
    def effective_input_tokens(self) -> int:
        """Billable input = fresh input + cache creation (not cache reads, which are cheaper)."""
        return self.input_tokens + self.cache_creation_tokens


@dataclass
class SessionSummary:
    session_id: str
    project_path: str
    file_path: Path
    turns: int = 0
    input_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    output_tokens: int = 0
    models: list[str] = field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.cache_creation_tokens + self.cache_read_tokens + self.output_tokens

    @property
    def duration_minutes(self) -> float | None:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() / 60
        return None


def _decode_project_path(encoded: str) -> str:
    """Convert encoded dir name back to a display path."""
    # Claude encodes paths as C--path-to-project (replacing : and \ with -)
    return encoded.replace("--", ":/", 1).replace("-", "/")


def _parse_jsonl(path: Path) -> Iterator[dict]:
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except (OSError, PermissionError):
        return


def iter_sessions(
    projects_dir: Path = CLAUDE_DIR,
    project_filter: str | None = None,
    include_subagents: bool = True,
) -> Iterator[SessionSummary]:
    """Yield SessionSummary for every JSONL transcript found."""
    if not projects_dir.exists():
        return

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue

        display_path = _decode_project_path(project_dir.name)
        if project_filter and project_filter.lower() not in display_path.lower():
            continue

        jsonl_files = list(project_dir.glob("*.jsonl"))
        if include_subagents:
            subagent_dir = project_dir / "subagents"
            if subagent_dir.exists():
                jsonl_files.extend(subagent_dir.glob("*.jsonl"))

        for jsonl_path in jsonl_files:
            summary = _summarize_session(jsonl_path, display_path)
            if summary.turns > 0:
                yield summary


def _summarize_session(path: Path, project_path: str) -> SessionSummary:
    session_id = path.stem
    summary = SessionSummary(
        session_id=session_id,
        project_path=project_path,
        file_path=path,
    )

    for entry in _parse_jsonl(path):
        if entry.get("type") != "assistant":
            continue

        msg = entry.get("message", {})
        usage = msg.get("usage")
        if not usage:
            continue

        summary.turns += 1
        summary.input_tokens += usage.get("input_tokens", 0)
        summary.cache_creation_tokens += usage.get("cache_creation_input_tokens", 0)
        summary.cache_read_tokens += usage.get("cache_read_input_tokens", 0)
        summary.output_tokens += usage.get("output_tokens", 0)

        model = msg.get("model", "unknown")
        if model not in summary.models:
            summary.models.append(model)

        raw_ts = entry.get("timestamp")
        if raw_ts:
            try:
                ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
                if summary.start_time is None or ts < summary.start_time:
                    summary.start_time = ts
                if summary.end_time is None or ts > summary.end_time:
                    summary.end_time = ts
            except ValueError:
                pass

    return summary


def iter_turns(path: Path, project_path: str = "") -> Iterator[TurnUsage]:
    """Yield per-turn token usage from a single JSONL file."""
    for entry in _parse_jsonl(path):
        if entry.get("type") != "assistant":
            continue

        msg = entry.get("message", {})
        usage = msg.get("usage")
        if not usage:
            continue

        raw_ts = entry.get("timestamp", "")
        try:
            ts = datetime.fromisoformat(raw_ts.replace("Z", "+00:00"))
        except ValueError:
            ts = datetime.now(timezone.utc)

        yield TurnUsage(
            session_id=path.stem,
            project_path=project_path,
            timestamp=ts,
            model=msg.get("model", "unknown"),
            input_tokens=usage.get("input_tokens", 0),
            cache_creation_tokens=usage.get("cache_creation_input_tokens", 0),
            cache_read_tokens=usage.get("cache_read_input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
        )
