from __future__ import annotations

from typing import Any

from .pipeline import (
    business_consistency_check,
    evidence_check,
    finalize_report,
    normalize_input,
    policy_rule_check,
    rewrite_answer,
    risk_score,
    route_decision,
    validate_rewrite,
)


def build_graph() -> Any:
    """Build the LangGraph StateGraph for the QA audit workflow.

    This function requires the optional `langgraph` package. The local demo and
    tests use `pipeline.audit_qa` so the project remains runnable without network
    installation.
    """

    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:
        raise RuntimeError(
            "LangGraph is not installed. Install requirements.txt before calling build_graph()."
        ) from exc

    graph = StateGraph(dict)
    graph.add_node("normalize_input", normalize_input)
    graph.add_node("policy_rule_check", policy_rule_check)
    graph.add_node("business_consistency_check", business_consistency_check)
    graph.add_node("evidence_check", evidence_check)
    graph.add_node("risk_score", risk_score)
    graph.add_node("route_decision", route_decision)
    graph.add_node("rewrite_answer", rewrite_answer)
    graph.add_node("validate_rewrite", validate_rewrite)
    graph.add_node("finalize_report", _finalize_for_graph)

    graph.add_edge(START, "normalize_input")
    graph.add_edge("normalize_input", "policy_rule_check")
    graph.add_edge("policy_rule_check", "business_consistency_check")
    graph.add_edge("business_consistency_check", "evidence_check")
    graph.add_edge("evidence_check", "risk_score")
    graph.add_edge("risk_score", "route_decision")
    graph.add_conditional_edges(
        "route_decision",
        _route,
        {
            "approve": "finalize_report",
            "rewrite": "rewrite_answer",
            "human_review": "finalize_report",
            "reject": "finalize_report",
        },
    )
    graph.add_edge("rewrite_answer", "validate_rewrite")
    graph.add_conditional_edges(
        "validate_rewrite",
        _route_after_validation,
        {
            "approve": "finalize_report",
            "rewrite": "rewrite_answer",
            "human_review": "finalize_report",
        },
    )
    graph.add_edge("finalize_report", END)
    return graph.compile()


def _route(state: dict[str, Any]) -> str:
    return str(state.get("decision") or "human_review")


def _route_after_validation(state: dict[str, Any]) -> str:
    if state.get("rewrite_validation_passed"):
        return "approve"
    if int(state.get("rewrite_attempts") or 0) >= 3:
        state["decision"] = "human_review"
        state["safe_answer"] = None
        return "human_review"
    return "rewrite"


def _finalize_for_graph(state: dict[str, Any]) -> dict[str, Any]:
    result = finalize_report(state)
    state["result"] = result.to_dict()
    return state
