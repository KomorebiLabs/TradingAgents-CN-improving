"""Dependency-graph regression tests (import direction guards).

AST-scans module-level imports across the ``tradingagents`` package and
asserts:
  1. the module-level import graph is ACYCLIC (the historical
     interface -> rag -> cn_news_retriever -> tools -> interface cycle
     must never come back);
  2. layer-direction rules hold:
     - dataflows must not import the screener application layer;
     - dataflows.interface must not import the agents layer (RAG hook stays dead);
     - ports must stay implementation-free at module level (no screener import).

Function-level (lazy) imports are deliberately NOT counted: they are the
sanctioned escape hatch for composition-time wiring.
"""

from __future__ import annotations

import ast
import pathlib
from collections import defaultdict

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG_ROOT = REPO_ROOT / "tradingagents"


def _module_name(path: pathlib.Path) -> str:
    rel = path.relative_to(REPO_ROOT).with_suffix("")
    return ".".join(rel.parts)


def _resolve_relative(importer: str, is_init: bool, level: int, module: str | None) -> str:
    """Resolve a relative import target for a module named ``importer``."""
    base = importer if is_init else importer.rsplit(".", 1)[0]
    if level > 1:
        base = base.rsplit(".", level - 1)[0]
    return f"{base}.{module}" if module else base


def _collect_edges():
    """Return {importer_module: set(imported_project_modules)} (top-level only)."""
    paths = sorted(PKG_ROOT.rglob("*.py"))
    edges: dict[str, set[str]] = {}
    for path in paths:
        if "__pycache__" in path.parts:
            continue
        name = _module_name(path)
        is_init = path.name == "__init__.py"
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover
            continue
        deps = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("tradingagents"):
                        deps.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0:
                    if node.module and node.module.startswith("tradingagents"):
                        deps.add(node.module)
                else:
                    deps.add(_resolve_relative(name, is_init, node.level, node.module))
        edges[name] = deps
    return edges


def _module_or_prefix(dep: str, edges_keys) -> str | None:
    """Map an imported module to the best-matching project module (exact or
    package prefix, e.g. 'tradingagents.screener' -> package __init__)."""
    if dep in edges_keys:
        return dep
    for key in edges_keys:
        if dep.startswith(key + "."):
            return key
    return None


class TestImportGraphAcyclic:
    def test_module_level_import_graph_is_acyclic(self):
        edges = _collect_edges()
        resolved: dict[str, set[str]] = defaultdict(set)
        for importer, deps in edges.items():
            for dep in deps:
                target = _module_or_prefix(dep, edges.keys())
                if target and target != importer:
                    resolved[importer].add(target)

        # Kahn's algorithm — nodes are importers AND their dependency targets
        # (leaf modules that import nothing internal must seed the queue).
        all_nodes = set(resolved)
        for targets in resolved.values():
            all_nodes.update(targets)
        in_degree = {m: 0 for m in all_nodes}
        rev: dict[str, set[str]] = defaultdict(set)
        for importer, targets in resolved.items():
            for target in targets:
                rev[target].add(importer)
                in_degree[importer] += 1
        queue = [m for m, d in in_degree.items() if d == 0]
        while queue:
            node = queue.pop()
            for dependent in rev[node]:
                in_degree[dependent] -= 1
                if in_degree[dependent] == 0:
                    queue.append(dependent)
        cyclic = [m for m, d in in_degree.items() if d > 0]
        assert not cyclic, f"module-level import cycle(s) involving: {sorted(cyclic)}"


class TestLayerDirections:
    def test_dataflows_never_imports_screener(self):
        edges = _collect_edges()
        for importer, deps in edges.items():
            if importer.startswith("tradingagents.dataflows"):
                for dep in deps:
                    assert not dep.startswith("tradingagents.screener"), (
                        f"{importer} imports {dep}: dataflows -> screener inversion"
                    )

    def test_dataflows_interface_never_imports_agents(self):
        edges = _collect_edges()
        deps = edges.get("tradingagents.dataflows.interface", set())
        for dep in deps:
            assert not dep.startswith("tradingagents.agents"), (
                f"interface.py imports {dep}: the RAG-hook cycle edge is back"
            )

    def test_ports_are_implementation_free_at_module_level(self):
        edges = _collect_edges()
        for importer, deps in edges.items():
            if importer.startswith("tradingagents.ports"):
                for dep in deps:
                    assert not dep.startswith("tradingagents.screener"), (
                        f"{importer} imports {dep} at module level; "
                        "the default adapter must stay lazy inside the factory"
                    )
