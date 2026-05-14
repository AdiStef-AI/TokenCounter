"""Token Counter CLI — transparency for Claude token usage."""

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

app = typer.Typer(
    name="tc",
    help="Token Counter - visibility into your Claude token usage.",
    no_args_is_help=True,
)
console = Console()
err_console = Console(stderr=True)


# ---------------------------------------------------------------------------
# tc logs  — scan Claude Code transcripts
# ---------------------------------------------------------------------------

@app.command()
def logs(
    project: Optional[str] = typer.Option(None, "--project", "-p", help="Filter by project name"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max sessions to show"),
    sync: bool = typer.Option(True, "--sync/--no-sync", help="Save results to local DB"),
    chart: bool = typer.Option(False, "--chart", "-c", help="Show daily usage chart"),
):
    """Scan local Claude Code transcripts and show token usage."""
    from .tracker import CLAUDE_DIR, iter_sessions, iter_turns
    from .storage import upsert_session, upsert_turns, query_daily_totals
    from .display import print_session_table, print_summary_panel, print_plotext_chart, _palette

    p = _palette()
    console.print(f"[{p.label}]Scanning {CLAUDE_DIR}...[/{p.label}]")

    sessions = list(iter_sessions(project_filter=project))
    if not sessions:
        console.print("[yellow]No sessions found.[/yellow]")
        raise typer.Exit()

    sessions.sort(key=lambda s: s.end_time or s.start_time or __import__('datetime').datetime.min, reverse=True)

    if sync:
        for s in sessions:
            upsert_session(s)
            turns = list(iter_turns(s.file_path, s.project_path))
            if turns:
                upsert_turns(turns)

    totals = {
        "sessions": len(sessions),
        "turns": sum(s.turns for s in sessions),
        "input_tokens": sum(s.input_tokens for s in sessions),
        "cache_read_tokens": sum(s.cache_read_tokens for s in sessions),
        "cache_creation_tokens": sum(s.cache_creation_tokens for s in sessions),
        "output_tokens": sum(s.output_tokens for s in sessions),
    }

    print_session_table(sessions[:limit])
    print_summary_panel(totals)

    if chart:
        daily = query_daily_totals(days=30)
        if daily:
            print_plotext_chart(daily)
        else:
            console.print("[dim]No daily data yet — run with --sync first.[/dim]")


# ---------------------------------------------------------------------------
# tc count  — count tokens in a prompt
# ---------------------------------------------------------------------------

@app.command()
def count(
    text: Optional[str] = typer.Argument(None, help="Text to count (or pipe via stdin)"),
    system: Optional[str] = typer.Option(None, "--system", "-s", help="System prompt"),
    model: str = typer.Option("claude-opus-4-7", "--model", "-m", help="Model to use"),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="Read prompt from file"),
    alert: bool = typer.Option(True, "--alert/--no-alert", help="Show context window alert"),
):
    """Count tokens in a prompt without sending it to Claude."""
    from .counter import count_tokens
    from .display import print_count_result, print_alert
    from .alerts import check_context_usage
    from .counter import get_context_limit

    if file:
        prompt = file.read_text(encoding="utf-8")
    elif text:
        prompt = text
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read()
    else:
        console.print("[red]Provide text, --file, or pipe input via stdin.[/red]")
        raise typer.Exit(1)

    try:
        result = count_tokens(prompt, system=system, model=model)
        print_count_result(result, model)

        if alert:
            used = result["input_token_count"]
            limit = get_context_limit(model)
            a = check_context_usage(used, limit)
            print_alert(a)
    except Exception as e:
        err_console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# tc forecast  — project future usage from history
# ---------------------------------------------------------------------------

@app.command()
def forecast(
    days: int = typer.Option(30, "--days", "-d", help="Historical days to analyse"),
    model: str = typer.Option("claude-opus-4-7", "--model", "-m", help="Model for context limit"),
    session_tokens: int = typer.Option(0, "--session", help="Current session token count for limit projection"),
):
    """Forecast future token usage based on historical patterns."""
    from .storage import query_daily_totals
    from .forecast import forecast_usage
    from .counter import get_context_limit
    from .display import print_sparkline, print_forecast

    daily = query_daily_totals(days=days)
    if not daily:
        console.print("[yellow]No historical data. Run 'tc logs' first to sync transcripts.[/yellow]")
        raise typer.Exit()

    print_sparkline(daily)

    limit = get_context_limit(model) if session_tokens > 0 else None
    fc = forecast_usage(daily, context_limit=limit, current_session_tokens=session_tokens)
    print_forecast(fc)


# ---------------------------------------------------------------------------
# tc usage  — fetch Anthropic Admin API usage (org accounts only)
# ---------------------------------------------------------------------------

@app.command()
def usage(
    days: int = typer.Option(7, "--days", "-d", help="Days of history to fetch"),
    group: Optional[str] = typer.Option("model", "--group", "-g", help="Group by: model, workspace_id"),
    admin_key: Optional[str] = typer.Option(None, "--key", envvar="ANTHROPIC_ADMIN_KEY", help="Admin API key"),
):
    """Fetch usage report from Anthropic Admin API (requires Admin key + org account)."""
    from .api_usage import fetch_usage_report, AdminAPIUnavailable

    try:
        data = fetch_usage_report(
            days=days,
            group_by=[group] if group else None,
            admin_key=admin_key,
        )
    except AdminAPIUnavailable as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        err_console.print(f"[red]API error:[/red] {e}")
        raise typer.Exit(1)

    results = data.get("results", [])
    if not results:
        console.print("[yellow]No usage data returned.[/yellow]")
        return

    from rich.table import Table
    from rich import box

    t = Table(title=f"Usage Report (last {days} days)", box=box.ROUNDED)
    t.add_column("Bucket Start")
    if group:
        t.add_column(group.replace("_id", "").title())
    t.add_column("Input", justify="right")
    t.add_column("Cache✓", justify="right", style="green")
    t.add_column("Cache+", justify="right", style="yellow")
    t.add_column("Output", justify="right", style="cyan")

    for row in results:
        cols = [row.get("start_time", "")[:10]]
        if group:
            cols.append(str(row.get(group, "—")))
        cols += [
            f"{row.get('input_tokens', 0):,}",
            f"{row.get('cache_read_input_tokens', 0):,}",
            f"{row.get('cache_creation_input_tokens', 0):,}",
            f"{row.get('output_tokens', 0):,}",
        ]
        t.add_row(*cols)

    console.print(t)


# ---------------------------------------------------------------------------
# tc watch  — monitor a session file in real-time
# ---------------------------------------------------------------------------

@app.command()
def watch(
    session_file: Optional[Path] = typer.Argument(None, help="Path to .jsonl session file"),
    model: str = typer.Option("claude-opus-4-7", "--model", "-m"),
    interval: float = typer.Option(5.0, "--interval", "-i", help="Refresh interval in seconds"),
):
    """Watch a session file and alert when context usage is high."""
    import time
    from .tracker import CLAUDE_DIR, iter_sessions, _summarize_session
    from .counter import get_context_limit
    from .alerts import check_context_usage
    from .display import print_alert, print_watch_status

    if session_file is None:
        all_jsonl = sorted(CLAUDE_DIR.rglob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not all_jsonl:
            console.print("[red]No session files found.[/red]")
            raise typer.Exit(1)
        session_file = all_jsonl[0]

    # Derive project name from the parent directory name
    from .tracker import _decode_project_path
    parent = session_file.parent
    if parent.name == "subagents":
        parent = parent.parent
    project_name = _decode_project_path(parent.name).split("/")[-1]

    limit = get_context_limit(model)

    try:
        while True:
            summary = _summarize_session(session_file, "")
            alert = check_context_usage(summary.last_turn_context_tokens, limit)
            console.clear()
            print_watch_status(project_name, session_file.name, summary.turns, model, limit, interval)
            print_alert(alert)
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/dim]")


if __name__ == "__main__":
    app()
