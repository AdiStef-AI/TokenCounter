"""Simple linear trend and context-limit projection."""

from dataclasses import dataclass
from statistics import mean


@dataclass
class ForecastResult:
    avg_daily_tokens: float
    trend_slope: float          # tokens/day change
    projected_7d: float
    projected_30d: float
    days_to_limit: float | None  # None if not approaching a limit
    limit_tokens: int | None


def linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float]:
    """Returns (slope, intercept) for y = slope*x + intercept."""
    n = len(xs)
    if n < 2:
        return 0.0, ys[0] if ys else 0.0
    x_mean = mean(xs)
    y_mean = mean(ys)
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    den = sum((x - x_mean) ** 2 for x in xs)
    slope = num / den if den else 0.0
    intercept = y_mean - slope * x_mean
    return slope, intercept


def forecast_usage(
    daily_totals: list[dict],
    context_limit: int | None = None,
    current_session_tokens: int = 0,
) -> ForecastResult:
    """
    daily_totals: list of dicts with 'day' (str YYYY-MM-DD) and 'total_tokens' (int)
    context_limit: if set, projects when current session approaches limit
    """
    if not daily_totals:
        return ForecastResult(0, 0, 0, 0, None, context_limit)

    tokens = [float(d["total_tokens"]) for d in daily_totals]
    xs = list(range(len(tokens)))

    slope, intercept = linear_regression(xs, tokens)
    avg = mean(tokens)

    last_x = xs[-1]
    projected_7d = max(0, slope * (last_x + 7) + intercept)
    projected_30d = max(0, slope * (last_x + 30) + intercept)

    days_to_limit = None
    if context_limit and current_session_tokens > 0:
        remaining = context_limit - current_session_tokens
        # Estimate tokens added per day in an ongoing session
        if avg > 0:
            days_to_limit = remaining / avg
        else:
            days_to_limit = None

    return ForecastResult(
        avg_daily_tokens=avg,
        trend_slope=slope,
        projected_7d=projected_7d,
        projected_30d=projected_30d,
        days_to_limit=days_to_limit,
        limit_tokens=context_limit,
    )
