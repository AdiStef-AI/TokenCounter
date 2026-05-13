"""Rich terminal output: tables, charts, alerts."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box

from .alerts import Alert, AlertLevel
from .forecast import ForecastResult
from .tracker import SessionSummary

# Default Console — uses Windows native console API on Windows (no raw ANSI codes)
console = Console()


def _fmt(n: int | float) -> str:
    return f"{int(n):,}"


def print_session_table(sessions: list[SessionSummary], title: str = "Sessions") -> None:
    t = Table(title=title, box=box.MARKDOWN, show_lines=False, expand=False)
    t.add_column("Project", max_width=28, no_wrap=False)
    t.add_column("Turns", justify="right", min_width=5)
    t.add_column("Input", justify="right", min_width=8)
    t.add_column("Cache rd", justify="right", min_width=11, style="green")
    t.add_column("Output", justify="right", min_width=9, style="cyan")
    t.add_column("Total", justify="right", min_width=11, style="bold")
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
    lines = [
        f"Sessions scanned:   [bold]{_fmt(totals.get('sessions', 0))}[/bold]",
        f"Total turns:        [bold]{_fmt(totals.get('turns', 0))}[/bold]",
        f"Input tokens:       {_fmt(totals.get('input_tokens', 0))}",
        f"Cache reads:        [green]{_fmt(totals.get('cache_read_tokens', 0))}[/green]",
        f"Cache created:      [yellow]{_fmt(totals.get('cache_creation_tokens', 0))}[/yellow]",
        f"Output tokens:      [cyan]{_fmt(totals.get('output_tokens', 0))}[/cyan]",
    ]
    total = (
        totals.get("input_tokens", 0)
        + totals.get("cache_read_tokens", 0)
        + totals.get("cache_creation_tokens", 0)
        + totals.get("output_tokens", 0)
    )
    lines.append("-" * 32)
    lines.append(f"Grand total:        [bold white]{_fmt(total)}[/bold white]")
    console.print(Panel("\n".join(lines), title="[bold]Token Usage Summary[/bold]", expand=False, box=box.ASCII))


def print_sparkline(daily_totals: list[dict], title: str = "Daily Token Usage") -> None:
    """ASCII sparkline."""
    if not daily_totals:
        console.print("[dim]No daily data available.[/dim]")
        return

    vals = [d["total_tokens"] for d in daily_totals]
    max_val = max(vals) if vals else 1
    bars = " ._-:=+*#@"
    bar_chars = []
    for v in vals:
        idx = min(int(v / max_val * (len(bars) - 1)), len(bars) - 1)
        bar_chars.append(bars[idx])

    spark = "".join(bar_chars)
    console.print(f"\n[bold]{title}[/bold]")
    console.print(f"  [cyan]{spark}[/cyan]")
    if daily_totals:
        first_day = daily_totals[0]["day"]
        last_day = daily_totals[-1]["day"]
        console.print(f"  [dim]{first_day} -> {last_day}  (peak: {_fmt(max_val)})[/dim]\n")


def print_plotext_chart(daily_totals: list[dict], title: str = "Daily Token Usage") -> None:
    """Attempt a richer chart with plotext; fall back to sparkline."""
    try:
        import plotext as plt

        days = [d["day"] for d in daily_totals]
        totals = [d["total_tokens"] for d in daily_totals]

        plt.clear_figure()
        plt.bar(days, totals, orientation="v", width=0.5)
        plt.title(title)
        plt.ylabel("Tokens")
        plt.theme("dark")
        plt.show()
    except Exception:
        print_sparkline(daily_totals, title)


def print_forecast(fc: ForecastResult) -> None:
    sign = "+" if fc.trend_slope >= 0 else ""
    lines = [
        f"Avg daily usage:    [bold]{_fmt(fc.avg_daily_tokens)}[/bold] tokens",
        f"Trend:              {sign}{int(fc.trend_slope):,} tokens/day",
        f"Projected 7 days:   [bold]{_fmt(fc.projected_7d)}[/bold]",
        f"Projected 30 days:  [bold]{_fmt(fc.projected_30d)}[/bold]",
    ]
    if fc.days_to_limit is not None:
        lines.append(
            f"Est. context full:  [bold red]{fc.days_to_limit:.1f}[/bold red] days at current rate"
        )
    console.print(Panel("\n".join(lines), title="[bold]Forecast[/bold]", expand=False, box=box.ASCII))


def print_alert(alert: Alert) -> None:
    pct = alert.pct_used
    bar_width = 40
    filled = int(pct * bar_width)
    empty = bar_width - filled

    if alert.level == AlertLevel.CRITICAL:
        color = "red"
        label = "!!!"
    elif alert.level == AlertLevel.WARNING:
        color = "yellow"
        label = " ! "
    else:
        color = "green"
        label = " OK"

    bar = f"[{color}]{'#' * filled}[/{color}]{'.' * empty}"
    console.print(
        f"\n[{color}]{label}[/{color}] Context: {bar} [bold]{pct:.1%}[/bold] "
        f"({_fmt(alert.tokens_used)} / {_fmt(alert.tokens_limit)})"
    )
    if alert.level != AlertLevel.OK:
        console.print(f"  [{color}]{alert.message}[/{color}]")


def print_count_result(result: dict, model: str) -> None:
    tokens = result.get("input_token_count", 0)
    from .counter import get_context_limit
    limit = get_context_limit(model)
    pct = tokens / limit * 100
    console.print(
        f"\n[bold]Token count:[/bold] {_fmt(tokens)} "
        f"[dim]({pct:.1f}% of {model} context window)[/dim]"
    )
