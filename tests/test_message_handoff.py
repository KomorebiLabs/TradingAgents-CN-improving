from types import SimpleNamespace

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph.message import add_messages

from tradingagents.agents.utils.tools.output_rules import (
    create_msg_delete,
    suppress_repeated_tool_calls,
)


def test_message_clear_reduces_history_to_one_stable_handoff():
    node = create_msg_delete("news")
    old = [HumanMessage(content="old", id="old-1")]
    update = node({"messages": old})
    reduced = add_messages(old, update["messages"])

    assert len(reduced) == 1
    assert reduced[0].id == "phase-handoff:news"
    assert "SYSTEM_HANDOFF" in reduced[0].content


def test_successive_message_clears_do_not_accumulate_handoffs():
    first = [HumanMessage(content="ticker", id="ticker")]
    first = add_messages(first, create_msg_delete("market")({"messages": first})["messages"])
    first = add_messages(first, [AIMessage(content="social report", id="social-result")])

    second = add_messages(
        first,
        create_msg_delete("social")({"messages": first})["messages"],
    )

    assert len(second) == 1
    assert second[0].id == "phase-handoff:social"


def test_repeated_tool_call_is_stopped_with_unavailable_report():
    repeated = {"name": "get_cn_trade_data", "args": {"months": 6, "focus": "all"}}
    prior = [SimpleNamespace(tool_calls=[repeated])]
    result = SimpleNamespace(tool_calls=[dict(repeated)], content="")

    stats = suppress_repeated_tool_calls(result, prior, "News analyst")

    assert stats == {"suppressed": 1, "remaining": 0}
    assert result.tool_calls == []
    assert "Status: unavailable" in result.content
    assert "No unsupported numeric conclusion" in result.content


def test_novel_tool_call_survives_when_duplicate_is_removed():
    prior = [SimpleNamespace(tool_calls=[
        {"name": "get_cn_trade_data", "args": {"months": 6}}
    ])]
    result = SimpleNamespace(tool_calls=[
        {"name": "get_cn_trade_data", "args": {"months": 6}},
        {"name": "get_global_news", "args": {"limit": 10}},
    ], content="")

    stats = suppress_repeated_tool_calls(result, prior, "News analyst")

    assert stats == {"suppressed": 1, "remaining": 1}
    assert result.tool_calls[0]["name"] == "get_global_news"


def test_novel_parameter_variations_stop_after_tool_round_budget():
    prior = [
        SimpleNamespace(tool_calls=[
            {"name": "get_cn_macro_data", "args": {"period": period}}
        ])
        for period in ("quarterly", "monthly", "annual")
    ]
    result = SimpleNamespace(tool_calls=[
        {"name": "get_cn_macro_data", "args": {"period": "weekly"}}
    ], content="")

    stats = suppress_repeated_tool_calls(result, prior, "News analyst")

    assert stats == {"suppressed": 1, "remaining": 0}
    assert result.tool_calls == []
    assert "retry budget" in result.content
