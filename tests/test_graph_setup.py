"""Structure tests for the decomposed GraphSetup (Phase-4 B-group item #4).

The wiring equivalence (nodes/edges/conditional edges identical to the
pre-split version) was verified by AST comparison during the split; these
tests pin the decomposition so it cannot silently regress into a monolith.
"""

from __future__ import annotations

import ast
import pathlib

PHASE_BUILDERS = [
    "_create_analyst_nodes",
    "_create_agent_nodes",
    "_add_orchestration_nodes",
    "_add_nodes_to_graph",
    "_wire_analyst_chain",
    "_wire_research_debate",
    "_wire_orchestration_routing",
    "_wire_risk_debate",
]


def _source() -> str:
    return pathlib.Path("tradingagents/graph/setup.py").read_text(encoding="utf-8")


def _setup_graph_tree() -> ast.FunctionDef:
    tree = ast.parse(_source())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "GraphSetup":
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == "setup_graph":
                    return item
    raise AssertionError("GraphSetup.setup_graph not found")


class TestGraphSetupDecomposed:
    def test_phase_builder_methods_exist(self):
        from tradingagents.graph.setup import GraphSetup

        for name in PHASE_BUILDERS:
            assert callable(getattr(GraphSetup, name, None)), f"missing {name}"

    def test_setup_graph_is_a_thin_orchestrator(self):
        """setup_graph must delegate to the phase builders, not inline wiring."""
        func = _setup_graph_tree()
        called = {
            n.func.attr
            for n in ast.walk(func)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        }
        for name in PHASE_BUILDERS:
            assert name in called, f"setup_graph no longer calls {name}"
        # and it must not wire edges directly anymore
        wired = called & {"add_edge", "add_conditional_edges", "add_node"}
        assert not wired, f"setup_graph inlines graph wiring: {wired}"

    def test_setup_graph_fits_one_screen(self):
        lines = _source().splitlines()
        func = _setup_graph_tree()
        length = func.end_lineno - func.lineno + 1
        assert length <= 40, f"setup_graph grew to {length} lines (target <=40)"

    def test_routing_targets_constant_deduplicated(self):
        """The 4x-duplicated routing map must stay a single module constant."""
        source = _source()
        assert "ORCHESTRATION_ROUTE_TARGETS" in source
        # the dict literal should appear exactly twice: definition + no inline copies
        inline_copies = source.count('"Route Research Phase": "Route Research Phase"')
        assert inline_copies == 1, f"routing map duplicated {inline_copies}x again"


class TestGraphCompiles:
    """Regression: compile the real graph, not just AST-check the source.

    _add_orchestration_nodes once shadowed its ``workflow`` parameter with a
    fresh local ``StateGraph``, so the 9 orchestration nodes landed on a
    throwaway graph and workflow.compile() raised
    ``ValueError: Found edge starting at unknown node 'Finalize Risk Debate'``.
    The AST structure tests above cannot catch that class of bug.
    """

    def _build_setup(self):
        from unittest.mock import MagicMock

        from tradingagents.graph.setup import GraphSetup

        return GraphSetup(
            quick_thinking_llm=MagicMock(),
            deep_thinking_llm=MagicMock(),
            tool_nodes={"market": MagicMock()},
            bull_memory=MagicMock(),
            bear_memory=MagicMock(),
            trader_memory=MagicMock(),
            invest_judge_memory=MagicMock(),
            portfolio_manager_memory=MagicMock(),
            conditional_logic=MagicMock(),
        )

    def test_setup_graph_compiles(self):
        compiled = self._build_setup().setup_graph(["market"])
        node_names = set(compiled.get_graph().nodes)
        for expected in (
            "Market Analyst",
            "Bull Researcher",
            "Trader",
            "Portfolio Manager",
            "Finalize Risk Debate",
            "Route Research Phase",
            "Route Portfolio Phase",
        ):
            assert expected in node_names, f"node {expected!r} missing from compiled graph"
