from __future__ import annotations

from typing import Any

from .models import AuditResult, AuditState
from .rules import (
    build_safe_answer,
    decision_for,
    risk_level,
    run_all_rules,
    score_issues,
    suggested_action,
)

MAX_REWRITE_ATTEMPTS = 3


def audit_qa(payload: dict[str, Any]) -> AuditResult:
    state = normalize_input(payload)
    state = policy_rule_check(state)
    state = business_consistency_check(state)
    state = evidence_check(state)
    state = risk_score(state)
    state = route_decision(state)
    while state.get("decision") == "rewrite":
        state = rewrite_answer(state)
        state = validate_rewrite(state)
        if state.get("rewrite_validation_passed"):
            break
        if state.get("rewrite_attempts", 0) >= MAX_REWRITE_ATTEMPTS:
            state["decision"] = "human_review"
            state["safe_answer"] = None
            state["suggested_action"] = suggested_action("human_review")
            _trace(state, "rewrite_loop", "max rewrite attempts reached; route to human_review")
            break
    return finalize_report(state)


def normalize_input(payload: dict[str, Any]) -> AuditState:
    state: AuditState = {
        "case_id": str(payload.get("case_id") or "unknown"),
        "question": str(payload.get("question") or "").strip(),
        "answer": str(payload.get("answer") or "").strip(),
        "evidence": _normalize_evidence(payload.get("evidence")),
        "business": str(payload.get("business") or "default").strip(),
        "issues": [],
        "safe_answer": None,
        "rewrite_attempts": 0,
        "rewrite_validation_passed": False,
        "audit_trace": [],
    }
    _trace(state, "normalize_input", "normalized QA input")
    return state


def policy_rule_check(state: AuditState) -> AuditState:
    issues = run_all_rules(state["question"], state["answer"], state["evidence"])
    state["issues"] = issues
    _trace(state, "policy_rule_check", f"matched {len(issues)} issues")
    return state


def business_consistency_check(state: AuditState) -> AuditState:
    _trace(state, "business_consistency_check", f"business={state['business']}")
    return state


def evidence_check(state: AuditState) -> AuditState:
    evidence_count = len(state["evidence"])
    _trace(state, "evidence_check", f"evidence_count={evidence_count}")
    return state


def risk_score(state: AuditState) -> AuditState:
    score = score_issues(state["issues"])
    state["score"] = score
    state["risk_level"] = risk_level(score)
    _trace(state, "risk_score", f"score={score}, risk_level={state['risk_level']}")
    return state


def route_decision(state: AuditState) -> AuditState:
    decision = decision_for(state["score"])
    state["decision"] = decision
    state["suggested_action"] = suggested_action(decision)
    _trace(state, "route_decision", f"decision={decision}")
    return state


def rewrite_answer(state: AuditState) -> AuditState:
    if state["decision"] == "rewrite":
        state["rewrite_attempts"] = int(state.get("rewrite_attempts") or 0) + 1
        state["safe_answer"] = build_safe_answer(
            state["answer"],
            state["issues"],
            attempt=state["rewrite_attempts"],
        )
        _trace(state, "rewrite_answer", f"created safe rewrite candidate attempt={state['rewrite_attempts']}")
    else:
        state["safe_answer"] = None
        _trace(state, "rewrite_answer", "skip")
    return state


def validate_rewrite(state: AuditState) -> AuditState:
    candidate = state.get("safe_answer")
    if not candidate:
        state["rewrite_validation_passed"] = False
        _trace(state, "validate_rewrite", "failed: empty candidate")
        return state

    issues = run_all_rules(state["question"], candidate, state["evidence"])
    blocking = [
        issue
        for issue in issues
        if issue.rule_id != "EVIDENCE_MISSING" and issue.severity in {"medium", "high", "critical"}
    ]
    state["rewrite_validation_issues"] = blocking
    state["rewrite_validation_passed"] = len(blocking) == 0
    if state["rewrite_validation_passed"]:
        state["decision"] = "approve"
        state["risk_level"] = "low"
        state["score"] = 0
        state["suggested_action"] = "安全重写已通过二次审核，可输出重写答案。"
        _trace(state, "validate_rewrite", "passed")
    else:
        state["decision"] = "rewrite"
        _trace(state, "validate_rewrite", f"failed: {len(blocking)} blocking issues")
    return state


def finalize_report(state: AuditState) -> AuditResult:
    _trace(state, "finalize_report", "created audit report")
    return AuditResult(
        case_id=state["case_id"],
        decision=state["decision"],
        risk_level=state["risk_level"],
        score=state["score"],
        issues=state["issues"],
        suggested_action=state["suggested_action"],
        safe_answer=state["safe_answer"],
        audit_trace=state["audit_trace"],
    )


def _normalize_evidence(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _trace(state: AuditState, node: str, message: str) -> None:
    state.setdefault("audit_trace", []).append({"node": node, "message": message})
