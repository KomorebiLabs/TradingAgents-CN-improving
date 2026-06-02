# Debug Guardrails (Screener Project)

## Purpose
Stop runaway debugging loops, protect token budget, and keep delivery focused on A2/A4/A5/A6 milestones.

## Scope
Applies to all temporary diagnostics, encoding/display investigations, and one-off verification scripts.

## Hard Rules
1. Debug budget per issue:
- Max 3 experiments, or 30 minutes, or ~2k tokens (whichever comes first).
- If unresolved after budget is exhausted, stop and escalate with a short blocker summary.

2. Non-blocking downgrade rule:
- If issue does not break contract/schema/tests or decision quality, classify as `P2` and move to backlog.
- Do not block A2/A4/A5/A6 mainline delivery on `P2` issues.

3. Single entrypoint for diagnostics:
- Use one file only: `tools/debug_name_resolver.py` (or a clearly named file under `tools/`).
- Do not create root-level `_*.py` or `.tmp_*` scripts.

4. Artifact hygiene:
- Diagnostic outputs go to `docs/debug_artifacts/`.
- Keep only final useful notes; remove duplicates/noise after conclusion.

5. Test-first checkpoint:
- Before any additional deep debugging, run required suites:
  - `tests/test_orchestration_logic.py`
  - `tests/test_screener_report.py`
  - `tests/test_screener_deep_analyzer.py`
  - `tests/test_screener_engine.py`
- If these pass, issue is presumptively non-blocking unless user explicitly promotes priority.

## Classification Template
Use this exact format when reporting:
- Severity: `P0|P1|P2`
- User impact:
- Contract impact:
- Repro steps:
- Stop/continue decision:
- Next action:

## Current Decision For "Chinese Display/Name Resolver"
- Severity: `P2`
- Reason: does not block semantic routing contract, merger/filter/scoring correctness, or required test suites.
- Action: freeze deep diagnostics, keep a single tracked backlog task, continue mainline A2/A4/A5/A6.
