"""Reflection package (split from reflection.py — refactor/merger-pipeline style).

Public entry: `Reflector` (same contract as the old single-file class).

    extraction      pure state-extraction helpers (no LLM)
    route_analytics pure route efficiency/pattern/summary functions (no LLM)
    conclusion      conclusion-summary generation (takes LLM explicitly)
    reflector       Reflector facade: LLM reflection + delegation

Dependency direction (imports only point right):
    extraction -> route_analytics -> reflector
    conclusion -> reflector
"""

from .reflector import Reflector

__all__ = ["Reflector"]
