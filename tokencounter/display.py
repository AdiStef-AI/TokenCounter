"""Rich terminal output: tables, charts, alerts."""

import os
from dataclasses import dataclass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from .alerts import Alert, AlertLevel
from .forecast import ForecastResult
from .tracker import SessionSummary

console = Console()


# ---------------------------------------------------------------------------
# Background detection — only used to pick DATA colours, never label colours.
# Plain text always inherits the terminal default (already contrasts with bg).
# ---------------------------------------------------------------------------

@dataclass
class Palette:
    cache_read: str
    cache_create: str
    output: str
    total: str
    ok: str
    warning: str
    critical: str
    sparkline: str


_DARK = Palette(
    cache_read="bright_green", cache_create="bright_yellow",
    output="bright_cyan",     total="bold",
    ok="bright_green",        warning="bright_yellow",
    critical="bright_red",    sparkline="bright_cyan",
)

_LIGHT = Palette(
    cache_read="green4",       cache_create="dark_orange",
    output="blue",             total="bold",
    ok="green4",               warning="dark_orange",
    critical="red",            sparkline="blue",
)


def _detect_bg_index() -> int:
    try:
        import ctypes
        handle = ctypes.windll.kernel32.GetStdHandle(-11)
        csbi = ctypes.create_string_buffer(22)
        if ctypes.windll.kernel32.GetConsoleScreenBufferInfo(handle, csbi):
            attrs = int.from_bytes(csbi[8:10], "little")
            return (attrs >> 4) & 0xF
    except Exception:
        pass
    return -1


def _palette() -> Palette:
    bg = _detect_bg_index()
    if bg >= 0:
        # indices 7,15 = light; everything else treated as dark
        return _LIGHT if bg in (7, 15) else _DARK

    colorfgbg = os.environ.get("COLORFGBG", "")
    if colorfgbg:
        try:
            return _LIGHT if int(colorfgbg.split(";")[-1]) >= 8 else _DARK
        except ValueError:
            pass

    return _DARK


def _fmt(n: int | float) -> str:
    return f"{int(n):,}"


# ---------------------------------------------------------------------------
# Output functions — plain text uses NO explicit colour (terminal default)
# ---------------------------------------------------------------------------

def print_session_table(sessions: list[SessionSummary], title: str = "Sessions") -> None:
    p = _palette()
    t = Table(title=title, box=box.MARKDOWN, show_lines=False, expand=False)
    t.add_column("Project",  max_width=28, no_wrap=False)
    t.add_column("Turns",    justify="right", min_width=5)
    t.add_column("Input",    justify="right", min_width=8)
    t.add_column("Cache rd", justify="right", min_width=11, style=p.cache_read)
    t.add_column("Output",   justify="right", min_width=9,  style=p.output)
    t.add_column("Total",    justify="right", min_width=11, style=p.total)
    t.add_column("Model",    style="dim", max_width=18, no_wrap=True)

    for s in sessions:
        project_short = s.project_path.split("/")[-1] or s.project_path
        model_short = s.models[-1].replace("claude-", "") if s.models else "?"
        t.add_row(
            project_short, str(s.turns),
            _fmt(s.input_tokens), _fmt(s.cache_read_tokens),
            _fmt(s.output_tokens), _fmt(s.total_tokens),
            model_short,
        )
    console.print(t)


def print_summary_panel(totals: dict) -> None:
    p = _palette()
    lines = [
        f"Sessions scanned:   [bold]{_fmt(totals.get('sessions', 0))}[/bold]",
        f"Total turns:        [bold]{_fmt(totals.get('turns', 0))}[/bold]",
        f"Input tokens:       {_fmt(totals.get('input_tokens', 0))}",
        f"Cache reads:        [{p.cache_read}]{_fmt(totals.get('cache_read_tokens', 0))}[/{p.cache_read}]",
        f"Cache created:      [{p.cache_create}]{_fmt(totals.get('cache_creation_tokens', 0))}[/{p.cache_create}]",
        f"Output tokens:      [{p.output}]{_fmt(totals.get('output_tokens', 0))}[/{p.output}]",
    ]
    total = (
        totals.get("input_tokens", 0) + totals.get("cache_read_tokens", 0)
        + totals.get("cache_creation_tokens", 0) + totals.get("output_tokens", 0)
    )
    lines.append("-" * 32)
    lines.append(f"Grand total:        [{p.total}]{_fmt(total)}[/{p.total}]")
    console.print(Panel("\n".join(lines), title="[bold]Token Usage Summary[/bold]", expand=False, box=box.ASCII))


def print_sparkline(daily_totals: list[dict], title: str = "Daily Token Usage") -> None:
    if not daily_totals:
        console.print("[dim]No daily data available.[/dim]")
        return

    p = _palette()
    vals = [d["total_tokens"] for d in daily_totals]
    max_val = max(vals) if vals else 1
    bars = " ._-:=+*#@"
    spark = "".join(bars[min(int(v / max_val * (len(bars) - 1)), len(bars) - 1)] for v in vals)

    console.print(f"\n[bold]Daily Token Usage[/bold]")
    console.print(f"  [{p.sparkline}]{spark}[/{p.sparkline}]")
    console.print(f"  [dim]{daily_totals[0]['day']} -> {daily_totals[-1]['day']}  (peak: {_fmt(max_val)})[/dim]\n")


def print_plotext_chart(daily_totals: list[dict], title: str = "Daily Token Usage") -> None:
    try:
        import plotext as plt
        bg = _detect_bg_index()
        days   = [d["day"] for d in daily_totals]
        totals = [d["total_tokens"] for d in daily_totals]
        plt.clear_figure()
        plt.bar(days, totals, orientation="v", width=0.5)
        plt.title(title)
        plt.ylabel("Tokens")
        plt.theme("clear" if bg in (7, 15) else "dark")
        plt.show()
    except Exception:
        print_sparkline(daily_totals, title)


def print_forecast(fc: ForecastResult) -> None:
    p = _palette()
    sign = "+" if fc.trend_slope >= 0 else ""
    lines = [
        f"Avg daily usage:    [bold]{_fmt(fc.avg_daily_tokens)}[/bold] tokens",
        f"Trend:              {sign}{int(fc.trend_slope):,} tokens/day",
        f"Projected 7 days:   [bold]{_fmt(fc.projected_7d)}[/bold]",
        f"Projected 30 days:  [bold]{_fmt(fc.projected_30d)}[/bold]",
    ]
    if fc.days_to_limit is not None:
        lines.append(f"Est. context full:  [{p.critical}]{fc.days_to_limit:.1f}[/{p.critical}] days at current rate")
    console.print(Panel("\n".join(lines), title="[bold]Forecast[/bold]", expand=False, box=box.ASCII))


def print_alert(alert: Alert) -> None:
    p = _palette()
    pct    = alert.pct_used
    filled = int(pct * 40)
    empty  = 40 - filled

    if alert.level == AlertLevel.CRITICAL:
        color, label = p.critical, "!!!"
    elif alert.level == AlertLevel.WARNING:
        color, label = p.warning,  " ! "
    else:
        color, label = p.ok,       " OK"

    bar = f"[{color}]{'#' * filled}[/{color}]{'.' * empty}"
    console.print(f"\n[{color}]{label}[/{color}] Context: {bar} [{color}]{pct:.1%}[/{color}] ({_fmt(alert.tokens_used)} / {_fmt(alert.tokens_limit)})")
    if alert.level != AlertLevel.OK:
        console.print(f"  [{color}]{alert.message}[/{color}]")


def print_watch_status(project: str, session_name: str, turns: int, model: str, limit: int, interval: float) -> None:
    console.print(f"[bold]Project:[/bold] {project}  |  [bold]Session:[/bold] {session_name}  |  Turns: {turns}")
    console.print(f"model={model}  limit={limit:,}  every {interval}s  (Ctrl+C to stop)")


def print_count_result(result: dict, model: str) -> None:
    from .counter import get_context_limit
    tokens = result.get("input_token_count", 0)
    limit  = get_context_limit(model)
    pct    = tokens / limit * 100
    console.print(f"\n[bold]Token count:[/bold] {_fmt(tokens)} [dim]({pct:.1f}% of {model} context window)[/dim]")
