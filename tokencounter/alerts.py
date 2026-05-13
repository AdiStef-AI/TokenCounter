"""Context window alert thresholds."""

from dataclasses import dataclass
from enum import Enum


class AlertLevel(Enum):
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Alert:
    level: AlertLevel
    pct_used: float
    tokens_used: int
    tokens_limit: int
    message: str


WARNING_THRESHOLD = 0.75   # 75%
CRITICAL_THRESHOLD = 0.90  # 90%


def check_context_usage(used_tokens: int, limit_tokens: int) -> Alert:
    pct = used_tokens / limit_tokens if limit_tokens else 0.0
    tokens_remaining = limit_tokens - used_tokens

    if pct >= CRITICAL_THRESHOLD:
        level = AlertLevel.CRITICAL
        msg = (
            f"CRITICAL: {pct:.1%} of context window used "
            f"({tokens_remaining:,} tokens remaining). "
            "Consider starting a new conversation."
        )
    elif pct >= WARNING_THRESHOLD:
        level = AlertLevel.WARNING
        msg = (
            f"WARNING: {pct:.1%} of context window used "
            f"({tokens_remaining:,} tokens remaining). "
            "Approaching context limit."
        )
    else:
        level = AlertLevel.OK
        msg = f"{pct:.1%} of context window used ({tokens_remaining:,} tokens remaining)."

    return Alert(
        level=level,
        pct_used=pct,
        tokens_used=used_tokens,
        tokens_limit=limit_tokens,
        message=msg,
    )
