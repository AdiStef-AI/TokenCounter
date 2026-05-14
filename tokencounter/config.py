"""Persistent user config stored in ~/.claude/tokencounter_config.json."""

import json
from pathlib import Path

CONFIG_PATH = Path.home() / ".claude" / "tokencounter_config.json"


def load_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def get_plan_limit() -> int | None:
    return load_config().get("plan_limit_tokens")


def set_plan_limit(limit: int) -> None:
    cfg = load_config()
    cfg["plan_limit_tokens"] = limit
    save_config(cfg)
