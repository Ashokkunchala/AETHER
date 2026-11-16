"""Cinematic JARVIS command centre for an interactive terminal session.

The dashboard is intentionally a terminal UI: it keeps the user's normal shell
available, uses the existing brain/tool approval flow, and does not open audio
devices until the user explicitly requests a voice call.
"""
from __future__ import annotations

import asyncio
import os
import platform
from datetime import datetime

from rich import box
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

console = Console()


def _system_panel() -> Panel:
    rows = Table.grid(padding=(0, 1))
    rows.add_column(style="cyan", width=9)
    rows.add_column(ratio=1)
    rows.add_column(width=4, justify="right")
    try:
        import psutil

        cpu = float(psutil.cpu_percent(interval=0.05))
        mem = psutil.virtual_memory()
        battery = psutil.sensors_battery()
        rows.add_row("CPU", ProgressBar(total=100, completed=cpu, width=24) , f"{cpu:3.0f}%")
        rows.add_row("MEM", ProgressBar(total=100, completed=mem.percent, width=24), f"{mem.percent:3.0f}%")
        if battery:
            power = float(battery.percent)
            rows.add_row("PWR", ProgressBar(total=100, completed=power, width=24), f"{power:3.0f}%")
        else:
            rows.add_row("PWR", Text("AC / unavailable", style="dim"), "")
    except Exception:
        rows.add_row("CPU", Text("telemetry unavailable", style="dim"), "")
        rows.add_row("MEM", Text("telemetry unavailable", style="dim"), "")
        rows.add_row("PWR", Text("telemetry unavailable", style="dim"), "")
    rows.add_row("TIME", datetime.now().astimezone().strftime("%H:%M:%S  %d %b %Y"), "")
    rows.add_row("HOST", platform.node() or platform.system(), "")
    return Panel(rows, title="[bold cyan]SYSTEM[/]", border_style="cyan", box=box.ROUNDED)


def render_dashboard(transcript: str = "Good day. All systems are ready. How may I help?",
                     activity: str = "JARVIS core online") -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body", ratio=1),
        Layout(name="prompt", size=3),
    )
    layout["body"].split_row(
        Layout(name="left", ratio=3),
        Layout(name="core", ratio=5),
        Layout(name="right", ratio=4),
    )
    layout["left"].split_column(
        Layout(_system_panel(), name="system", ratio=3),
        Layout(Panel("Local assistant ready\n\nUse /help to see commands.\nVoice stays off until requested.",
                     title="[bold cyan]INBOX[/]", border_style="cyan"), name="inbox", ratio=2),
        Layout(Panel("Branch-aware development assistant\nApproval required for sensitive actions.",
                     title="[bold cyan]GITHUB / SECURITY[/]", border_style="cyan"), name="github", ratio=2),
    )
    core = Text()
    core.append("             ╭──────────────╮\n", style="bright_cyan")
    core.append("          ╭──┤   J A R V I S  ├──╮\n", style="bright_cyan bold")
    core.append("          │  ╰──────┬───────╯  │\n", style="cyan")
    core.append("             ╲   ◉ CORE ◉   ╱\n", style="bright_cyan bold")
    core.append("                ╲  ✦  ╱\n\n", style="cyan")
    core.append("                 ONLINE\n", style="bold bright_cyan")
    core.append("\n  Personal AI  ·  Voice + Interface\n", style="dim")
    layout["core"].update(Panel(core, title="[bold cyan]J.A.R.V.I.S[/]", border_style="cyan",
                                box=box.DOUBLE, subtitle="JUST A RATHER VERY INTELLIGENT SYSTEM"))
    right = Layout()
    right.split_column(
        Layout(Panel(transcript, title="[bold cyan]TRANSCRIPT[/]", border_style="cyan"), ratio=3),
        Layout(Panel(f"[yellow]ϟ[/]  {activity}\n[green]$[/] Ready for command",
                     title="[bold cyan]jarvis://activity[/]", border_style="cyan"), ratio=3),
    )
    layout["right"].update(right)
    layout["header"].update(Panel(Text("J  ·  A  ·  R  ·  V  ·  I  ·  S", justify="center",
                                      style="bold bright_cyan"), border_style="bright_cyan"))
    layout["prompt"].update(Panel("[bright_cyan]>[/] Type a request, /help, /status or /quit",
                                  border_style="bright_cyan"))
    return layout


async def _confirm(tool, args) -> bool:
    console.print(Panel(f"[yellow]JARVIS requests approval[/]\n[bold]{tool.name}[/] · {tool.risk.name}\n{args}",
                        title="Sensitive action", border_style="yellow"))
    return console.input("Approve? [y/N] ").strip().lower() in {"y", "yes"}


async def _run_turn(brain, prompt: str) -> str:
    parts: list[str] = []
    async for event in brain.ask(prompt, confirm=_confirm):
        kind = event.get("type")
        if kind == "text_delta":
            parts.append(str(event.get("text", "")))
            console.print(str(event.get("text", "")), end="", markup=False, soft_wrap=True)
        elif kind == "tool_start":
            console.print(f"\n[cyan]ϟ Running {event.get('tool', 'tool')}[/]")
        elif kind == "tool_end":
            state = "green" if event.get("ok") else "red"
            console.print(f"[{state}]• {event.get('tool')} completed[/]")
        elif kind == "error":
            console.print(f"\n[red]Error: {event.get('error')}[/]")
    console.print()
    return "".join(parts)


def run() -> int:
    """Run the cinematic terminal dashboard and interactive assistant."""
    from jarvis.core.brain import JarvisBrain

    brain = JarvisBrain()
    if not brain.configured:
        console.print("[yellow]No AI provider configured. Add a provider key to .env first.[/]")
    transcript = "Good day. All systems are online. How may I help?"
    activity = "JARVIS core online"
    console.clear()
    console.print(render_dashboard(transcript, activity))
    console.print("[dim]Commands: /help  /status  /clear  /quit · Ctrl+C to exit[/]")
    try:
        while True:
            prompt = console.input("[bold bright_cyan]JARVIS › [/]").strip()
            if not prompt:
                continue
            command = prompt.lower()
            if command in {"/quit", "/exit", "/q"}:
                return 0
            if command == "/help":
                console.print("Ask naturally. /status shows provider and tool readiness. /clear resets conversation. /quit exits.")
                continue
            if command == "/status":
                console.print(f"Provider: {'ready' if brain.configured else 'not configured'} · "
                              f"Model: {brain.active_model} · Tools: {len(brain.registry)}")
                continue
            if command == "/clear":
                brain.reset()
                transcript = "Conversation cleared."
                console.clear()
                console.print(render_dashboard(transcript, "Conversation reset"))
                continue
            if not brain.configured:
                console.print("[red]Configure GEMINI_API_KEY, OPENROUTER_API_KEY or GROQ_API_KEY in .env.[/]")
                continue
            activity = "Processing request"
            console.print(f"\n[bold cyan]YOU[/]  {prompt}")
            try:
                reply = asyncio.run(_run_turn(brain, prompt))
                transcript = f"You: {prompt}\n\nJARVIS: {reply[-1200:]}"
                activity = "Request completed"
            except KeyboardInterrupt:
                activity = "Request cancelled"
                console.print("\n[yellow]Turn cancelled.[/]")
            console.clear()
            console.print(render_dashboard(transcript, activity))
            console.print("[dim]Commands: /help  /status  /clear  /quit · Sensitive actions require approval[/]")
    except (KeyboardInterrupt, EOFError):
        console.print("\n[dim]JARVIS session closed.[/]")
        return 0
