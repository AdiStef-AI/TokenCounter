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
# Background detection + per-hue colour palettes
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
    label: str       # general text / labels


# Windows console colour indices 0-15:
#   0=Black  1=DarkBlue  2=DarkGreen  3=DarkCyan  4=DarkRed  5=DarkMagenta
#   6=DarkYellow(Brown)  7=Gray  8=DarkGray  9=Blue  10=Green  11=Cyan
#  12=Red  13=Magenta  14=Yellow  15=White

_PALETTES: dict[str, Palette] = {
    # dark/black/dark-gray backgrounds — vivid colours are safe
    "dark": Palette(
        cache_read="bright_green", cache_create="bright_yellow",
        output="bright_cyan", total="bold bright_white",
        ok="bright_green", warning="bright_yellow", critical="bright_red",
        sparkline="bright_cyan", label="bright_white",
    ),
    # blue background — avoid blue; use yellow/green/red
    "blue": Palette(
        cache_read="bright_green", cache_create="bright_yellow",
        output="bright_white", total="bold bright_yellow",
        ok="bright_green", warning="bright_yellow", critical="bright_red",
        sparkline="bright_white", label="bright_white",
    ),
    # green background — avoid green/cyan; use yellow/magenta/white/red
    "green": Palette(
        cache_read="bright_yellow", cache_create="bright_magenta",
        output="white", total="bold white",
        ok="white", warning="bright_yellow", critical="bright_red",
        sparkline="bright_yellow", label="white",
    ),
    # cyan background — avoid cyan/green; use yellow/magenta/white/red
    "cyan": Palette(
        cache_read="bright_yellow", cache_create="bright_magenta",
        output="white", total="bold white",
        ok="white", warning="bright_yellow", critical="bright_red",
        sparkline="bright_yellow", label="white",
    ),
    # red background — avoid red; use green/cyan/yellow/white
    "red": Palette(
        cache_read="bright_green", cache_create="bright_yellow",
        output="bright_cyan", total="bold bright_white",
        ok="bright_green", warning="bright_yellow", critical="bright_white",
        sparkline="bright_cyan", label="bright_white",
    ),
    # magenta background — avoid magenta; use green/cyan/yellow
    "magenta": Palette(
        cache_read="bright_green", cache_create="bright_yellow",
        output="bright_cyan", total="bold bright_white",
        ok="bright_green", warning="bright_yellow", critical="bright_white",
        sparkline="bright_cyan", label="bright_white",
    ),
    # yellow/brown background — avoid yellow; use cyan/magenta/blue/white
    "yellow": Palette(
        cache_read="bright_cyan", cache_create="bright_magenta",
        output="bright_blue", total="bold white",
        ok="bright_cyan", warning="bright_magenta", critical="bright_red",
        sparkline="bright_blue", label="white",
    ),
    # light gray (7=Gray) — bold dark colours for strong contrast
    "light": Palette(
        cache_read="green4", cache_create="dark_orange",
        output="blue", total="bold black",
        ok="green4", warning="dark_orange", critical="red",
        sparkline="blue", label="bold black",
    ),
    # white (15=White) — deepest colours needed for max contrast
    "white": Palette(
        cache_read="dark_green", cache_create="orange4",
        output="navy_blue", total="bold black",
        ok="dark_green", warning="orange4", critical="dark_red",
        sparkline="navy_blue", label="bold black",
    ),
}

# Map Windows console bg index → palette key
_BG_TO_PALETTE = {
    0: "dark",    # Black
    1: "blue",    # DarkBlue
    2: "green",   # DarkGreen
    3: "cyan",    # DarkCyan
    4: "red",     # DarkRed
    5: "magenta", # DarkMagenta
    6: "yellow",  # DarkYellow/Brown
    7: "light",   # Gray  (medium grey → bold dark colours)

    8: "dark",    # DarkGray
    9: "blue",    # Blue
    10: "green",  # Green
    11: "cyan",   # Cyan
    12: "red",    # Red
    13: "magenta",# Magenta
    14: "yellow", # Yellow
    15: "white",  # White
}


def _detect_bg_index() -> int:
    """Return the Windows console background colour index (0-15), or -1 on failure."""
    try:
        import ctypes
        handle = ctypes.windll.kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
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
        return _PALETTES[_BG_TO_PALETTE[bg]]

    # Unix fallback: COLORFGBG=<fg>;<bg>
    colorfgbg = os.environ.get("COLORFGBG", "")
    if colorfgbg:
        try:
            bg = int(colorfgbg.split(";")[-1])
            return _PALETTES["light" if bg >= 8 else "dark"]
        except ValueError:
            pass

    return _PALETTES["dark"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fmt(n: int | float) -> str:
    return f"{int(n):,}"


# ---------------------------------------------------------------------------
# Output functions
# ---------------------------------------------------------------------------

def print_session_table(sessions: list[SessionSummary], title: str = "Sessions") -> None:
    p = _palette()
    t = Table(title=title, box=box.MARKDOWN, show_lines=False, expand=False)
    t.add_column("Project", max_width=28, no_wrap=False)
    t.add_column("Turns", justify="right", min_width=5)
    t.add_column("Input", justify="right", min_width=8)
    t.add_column("Cache rd", justify="right", min_width=11, style=p.cache_read)
    t.add_column("Output", justify="right", min_width=9, style=p.output)
    t.add_column("Total", justify="right", min_width=11, style=p.total)
    t.add_column("Model", style="dim", max_width=18, no_wrap=True)

    for s in sessions:
        project_short = s.project_path.split("/")[-1] or s.project_path
        model_short = (s.models[-1].replace("claude-", "") if s.models else "?")
        t.add_row(
            project_short,
            str(s.turns),
            _fmt(s.input_tokens),
            _fmt(s.cache_read_tokens),
            _fmt(s.output_tokens),
            _fmt(s.total_tokens),
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
        totals.get("input_tokens", 0)
        + totals.get("cache_read_tokens", 0)
        + totals.get("cache_creation_tokens", 0)
        + totals.get("output_tokens", 0)
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
    bar_chars = []
    for v in vals:
        idx = min(int(v / max_val * (len(bars) - 1)), len(bars) - 1)
        bar_chars.append(bars[idx])

    spark = "".join(bar_chars)
    console.print(f"\n[bold {p.label}]{title}[/bold {p.label}]")
    console.print(f"  [{p.sparkline}]{spark}[/{p.sparkline}]")
    first_day = daily_totals[0]["day"]
    last_day = daily_totals[-1]["day"]
    console.print(f"  [{p.label}]{first_day} -> {last_day}  (peak: {_fmt(max_val)})[/{p.label}]\n")


def print_plotext_chart(daily_totals: list[dict], title: str = "Daily Token Usage") -> None:
    try:
        import plotext as plt

        days = [d["day"] for d in daily_totals]
        totals = [d["total_tokens"] for d in daily_totals]
        bg = _detect_bg_index()
        theme = "clear" if bg >= 7 else "dark"

        plt.clear_figure()
        plt.bar(days, totals, orientation="v", width=0.5)
        plt.title(title)
        plt.ylabel("Tokens")
        plt.theme(theme)
        plt.show()
    except Exception:
        print_sparkline(daily_totals, title)


def print_forecast(fc: ForecastResult) -> None:
    p = _palette()
    sign = "+" if fc.trend_slope >= 0 else ""
    lines = [
        f"[{p.label}]Avg daily usage:    [bold]{_fmt(fc.avg_daily_tokens)}[/bold] tokens[/{p.label}]",
        f"[{p.label}]Trend:              {sign}{int(fc.trend_slope):,} tokens/day[/{p.label}]",
        f"[{p.label}]Projected 7 days:   [bold]{_fmt(fc.projected_7d)}[/bold][/{p.label}]",
        f"[{p.label}]Projected 30 days:  [bold]{_fmt(fc.projected_30d)}[/bold][/{p.label}]",
    ]
    if fc.days_to_limit is not None:
        lines.append(
            f"Est. context full:  [{p.critical}]{fc.days_to_limit:.1f}[/{p.critical}] days at current rate"
        )
    console.print(Panel("\n".join(lines), title="[bold]Forecast[/bold]", expand=False, box=box.ASCII))


def print_alert(alert: Alert) -> None:
    p = _palette()
    pct = alert.pct_used
    bar_width = 40
    filled = int(pct * bar_width)
    empty = bar_width - filled

    if alert.level == AlertLevel.CRITICAL:
        color = p.critical
        label = "!!!"
    elif alert.level == AlertLevel.WARNING:
        color = p.warning
        label = " ! "
    else:
        color = p.ok
        label = " OK"

    bar = f"[{color}]{'#' * filled}[/{color}][{p.label}]{'.' * empty}[/{p.label}]"
    console.print(
        f"\n[{color}]{label}[/{color}] [{p.label}]Context:[/{p.label}] {bar} "
        f"[bold {color}]{pct:.1%}[/bold {color}] "
        f"[{p.label}]({_fmt(alert.tokens_used)} / {_fmt(alert.tokens_limit)})[/{p.label}]"
    )
    if alert.level != AlertLevel.OK:
        console.print(f"  [{color}]{alert.message}[/{color}]")


def print_watch_status(project: str, session_name: str, turns: int, model: str, limit: int, interval: float) -> None:
    p = _palette()
    console.print(
        f"[{p.label}][bold]Project:[/bold] {project}  |  "
        f"[bold]Session:[/bold] {session_name}  |  "
        f"Turns: {turns}[/{p.label}]"
    )
    console.print(
        f"[{p.label}]model={model}  limit={limit:,}  every {interval}s  "
        f"(Ctrl+C to stop)[/{p.label}]"
    )


def print_count_result(result: dict, model: str) -> None:
    tokens = result.get("input_token_count", 0)
    from .counter import get_context_limit
    limit = get_context_limit(model)
    pct = tokens / limit * 100
    console.print(
        f"\n[bold]Token count:[/bold] {_fmt(tokens)} "
        f"[dim]({pct:.1f}% of {model} context window)[/dim]"
    )
