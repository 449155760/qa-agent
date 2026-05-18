from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal


Severity = Literal["low", "medium", "high", "critical"]
Decision = Literal["approve", "rewrite", "human_review", "reject"]


@dataclass(frozen=True)
class AuditIssue:
    rule_id: str
    category: str
    severity: Severity
    field: str
    message: str
    score: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "severity": self.severity,
            "field": self.field,
            "message": self.message,
            "score": self.score,
        }


@dataclass
class AuditResult:
    case_id: str
    decision: Decision
    risk_level: Severity
    score: int
    issues: list[AuditIssue] = field(default_factory=list)
    suggested_action: str = ""
    safe_answer: str | None = None
    audit_trace: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "decision": self.decision,
            "risk_level": self.risk_level,
            "score": self.score,
            "issues": [issue.to_dict() for issue in self.issues],
            "suggested_action": self.suggested_action,
            "safe_answer": self.safe_answer,
            "audit_trace": self.audit_trace,
        }

    def to_pretty_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


AuditState = dict[str, Any]
