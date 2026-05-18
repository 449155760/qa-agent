from __future__ import annotations

import re
from collections.abc import Iterable

from .models import AuditIssue


PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
ID_CARD_RE = re.compile(r"(?<!\d)\d{6}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?!\d)")
BANK_CARD_RE = re.compile(r"(?<!\d)(?:\d[ -]?){16,19}(?!\d)")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

ILLEGAL_TERMS = [
    "伪造证件",
    "诈骗",
    "洗钱",
    "绕过监管",
    "盗取账号",
]

SELF_HARM_TERMS = [
    "自杀方法",
    "如何自杀",
    "结束生命",
]

ABSOLUTE_PROMISE_TERMS = [
    "永久免费",
    "保证成功",
    "一定赔付",
    "绝对不会",
    "所有客户都可以",
]

PROMPT_ATTACK_TERMS = [
    "忽略以上规则",
    "绕过系统提示",
    "泄露系统提示词",
    "ignore previous instructions",
]


def check_input_completeness(question: str, answer: str) -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    if not question.strip():
        issues.append(
            AuditIssue("INPUT_EMPTY_QUESTION", "input", "medium", "question", "问题为空", 30)
        )
    if not answer.strip():
        issues.append(
            AuditIssue("INPUT_EMPTY_ANSWER", "input", "medium", "answer", "答案为空", 35)
        )
    return issues


def check_privacy(text: str, field: str = "answer") -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    if ID_CARD_RE.search(text):
        issues.append(
            AuditIssue("PII_ID_CARD", "privacy", "critical", field, "内容包含疑似身份证号", 85)
        )
    if PHONE_RE.search(text):
        issues.append(
            AuditIssue("PII_PHONE", "privacy", "high", field, "内容包含疑似手机号", 70)
        )
    if EMAIL_RE.search(text):
        issues.append(
            AuditIssue("PII_EMAIL", "privacy", "medium", field, "内容包含疑似邮箱地址", 35)
        )
    bank_scan_text = ID_CARD_RE.sub(" ", PHONE_RE.sub(" ", text))
    if BANK_CARD_RE.search(bank_scan_text):
        issues.append(
            AuditIssue("PII_BANK_CARD", "privacy", "critical", field, "内容包含疑似银行卡号", 85)
        )
    return issues


def check_policy_terms(text: str, field: str = "answer") -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    issues.extend(_term_issues(text, ILLEGAL_TERMS, "POLICY_ILLEGAL", "safety", "critical", field, "内容可能涉及违法违规协助", 90))
    issues.extend(_term_issues(text, SELF_HARM_TERMS, "POLICY_SELF_HARM", "safety", "high", field, "内容可能涉及自伤风险", 75))
    issues.extend(_term_issues(text, PROMPT_ATTACK_TERMS, "PROMPT_ATTACK", "security", "high", field, "内容可能涉及提示词攻击或越权请求", 70))
    return issues


def check_business_constraints(answer: str) -> list[AuditIssue]:
    return _term_issues(
        answer,
        ABSOLUTE_PROMISE_TERMS,
        "BUSINESS_ABSOLUTE_PROMISE",
        "business",
        "medium",
        "answer",
        "答案包含绝对化或超授权承诺",
        45,
    )


def check_evidence_support(answer: str, evidence: Iterable[str]) -> list[AuditIssue]:
    evidence_text = " ".join(item.strip() for item in evidence if item and item.strip())
    if not answer.strip():
        return []
    if not evidence_text:
        return [
            AuditIssue("EVIDENCE_MISSING", "evidence", "medium", "evidence", "缺少支撑答案的证据片段", 35)
        ]

    risky_terms = [term for term in ABSOLUTE_PROMISE_TERMS if term in answer and term not in evidence_text]
    if risky_terms:
        return [
            AuditIssue(
                "EVIDENCE_UNSUPPORTED_CLAIM",
                "evidence",
                "medium",
                "answer",
                f"答案包含证据未支撑的强承诺：{', '.join(risky_terms)}",
                40,
            )
        ]

    return []


def run_all_rules(question: str, answer: str, evidence: Iterable[str]) -> list[AuditIssue]:
    issues: list[AuditIssue] = []
    issues.extend(check_input_completeness(question, answer))
    issues.extend(check_privacy(question, "question"))
    issues.extend(check_privacy(answer, "answer"))
    issues.extend(check_policy_terms(question, "question"))
    issues.extend(check_policy_terms(answer, "answer"))
    issues.extend(check_business_constraints(answer))
    issues.extend(check_evidence_support(answer, evidence))
    return dedupe_issues(issues)


def score_issues(issues: Iterable[AuditIssue]) -> int:
    issue_list = list(issues)
    if not issue_list:
        return 0

    max_score = max(issue.score for issue in issue_list)
    extra = min(15, max(0, len(issue_list) - 1) * 5)
    score = max_score + extra

    severities = {issue.severity for issue in issue_list}
    if "critical" in severities:
        return min(100, max(score, 85))
    if "high" in severities:
        return min(84, max(score, 60))
    if "medium" in severities:
        return min(59, max(score, 30))
    return min(29, score)


def risk_level(score: int) -> str:
    if score >= 85:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    return "low"


def decision_for(score: int) -> str:
    if score >= 85:
        return "reject"
    if score >= 60:
        return "human_review"
    if score >= 30:
        return "rewrite"
    return "approve"


def suggested_action(decision: str) -> str:
    return {
        "approve": "风险较低，可直接通过。",
        "rewrite": "建议安全重写，去除无依据或过强表述后再输出。",
        "human_review": "建议进入人工复核，确认授权、事实依据和业务边界。",
        "reject": "建议拒绝输出，并转人工或返回安全提示。",
    }[decision]


def build_safe_answer(answer: str, issues: Iterable[AuditIssue], attempt: int = 1) -> str | None:
    issue_list = list(issues)
    if not issue_list:
        return answer
    if any(issue.severity in {"high", "critical"} for issue in issue_list):
        return None
    if attempt == 1 and any(issue.rule_id == "BUSINESS_ABSOLUTE_PROMISE" for issue in issue_list):
        return answer.replace("永久免费", "需要进一步确认")
    return "该问题需要结合已授权资料进一步确认。建议补充依据后，以审慎、非绝对化表述回复用户。"


def dedupe_issues(issues: Iterable[AuditIssue]) -> list[AuditIssue]:
    seen: set[tuple[str, str, str]] = set()
    result: list[AuditIssue] = []
    for issue in issues:
        key = (issue.rule_id, issue.field, issue.message)
        if key in seen:
            continue
        seen.add(key)
        result.append(issue)
    return result


def _term_issues(
    text: str,
    terms: Iterable[str],
    rule_id: str,
    category: str,
    severity: str,
    field: str,
    message: str,
    score: int,
) -> list[AuditIssue]:
    return [
        AuditIssue(rule_id, category, severity, field, f"{message}：{term}", score)
        for term in terms
        if term.lower() in text.lower()
    ]
