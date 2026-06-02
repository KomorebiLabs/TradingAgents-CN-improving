"""Shared Bloomberg-style terminal theme constants for all TradingAgents CLI modules."""

from rich.theme import Theme

# Bloomberg Terminal inspired color palette
TRADING_THEME = Theme({
    # Primary colors
    "primary": "cyan",
    "success": "green",
    "warning": "yellow",
    "danger": "red",
    "info": "blue",

    # Panel/section colors
    "panel.header": "bold cyan",
    "panel.body": "white",
    "panel.border": "cyan",

    # Table colors
    "table.header": "bold magenta",
    "table.cell": "white",
    "table.index": "cyan",

    # Status indicators
    "status.pending": "yellow",
    "status.active": "cyan",
    "status.done": "green",
    "status.error": "red",

    # Signal badges
    "signal.buy": "bold green",
    "signal.hold": "yellow",
    "signal.sell": "bold red",

    # Accent
    "accent": "bold cyan",
    "dim": "dim",

    # Step headers and prompts
    "step.header": "bold cyan",
    "step.prompt": "green",
    "step.default": "dim",

    # Question box
    "question.box": "blue",
    "question.title": "bold",
    "question.prompt": "dim",

    # Dashboard
    "dashboard.progress": "cyan",
    "dashboard.agents": "green",
    "dashboard.events": "magenta",
    "dashboard.metrics": "yellow",
    "dashboard.stage.done": "green",
    "dashboard.stage.running": "cyan",
    "dashboard.stage.wait": "yellow",

    # Agent icons
    "agent.completed": "green",
    "agent.running": "cyan",
    "agent.pending": "yellow",
    "agent.error": "red",

    # Summary
    "summary.decision.buy": "bold green",
    "summary.decision.sell": "bold red",
    "summary.decision.hold": "bold yellow",
    "summary.confidence.high": "green",
    "summary.confidence.medium": "yellow",
    "summary.confidence.low": "red",

    # Interactive prompts (these are style references, not colors)
    "prompt.text": "green",
    "prompt.pointer": "cyan",
    "prompt.checkbox": "green",
})

# Prompt color constants (for use with Rich.Prompt styles)
PROMPT_STYLE_GREEN = [
    ("text", "fg:green"),
    ("highlighted", "noinherit"),
]

PROMPT_STYLE_YELLOW = [
    ("selected", "fg:yellow noinherit"),
    ("highlighted", "fg:yellow noinherit"),
    ("pointer", "fg:yellow noinherit"),
]

PROMPT_STYLE_MAGENTA = [
    ("selected", "fg:magenta noinherit"),
    ("highlighted", "fg:magenta noinherit"),
    ("pointer", "fg:magenta noinherit"),
]

PROMPT_STYLE_CYAN = [
    ("selected", "fg:cyan noinherit"),
    ("highlighted", "fg:cyan noinherit"),
    ("pointer", "fg:cyan noinherit"),
]

PROMPT_STYLE_GREEN_SELECTED = [
    ("checkbox-selected", "fg:green"),
    ("selected", "fg:green noinherit"),
    ("highlighted", "noinherit"),
    ("pointer", "noinherit"),
]

# Panel border styles for different sections
PANEL_BORDER_STEP = "blue"
PANEL_BORDER_WELCOME = "green"
PANEL_BORDER_PROGRESS = "cyan"
PANEL_BORDER_AGENTS = "green"
PANEL_BORDER_EVENTS = "magenta"
PANEL_BORDER_METRICS = "yellow"
PANEL_BORDER_SUMMARY = "green"

# Standard box style for tables
TERMINAL_BOX = None  # Use default box style

# Banner gradient colors (for animated headers)
BANNER_COLOR = "cyan"
BANNER_SECONDARY = "green"
