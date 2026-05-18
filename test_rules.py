import unittest

from src.qa_audit_agent.rules import decision_for, risk_level, run_all_rules, score_issues


class RuleTests(unittest.TestCase):
    def test_detects_phone_and_id_card(self):
        issues = run_all_rules(
            "帮我查用户信息",
            "手机号是 13800138000，身份证号是 110101199003071234。",
            [],
        )
        rule_ids = {issue.rule_id for issue in issues}

        self.assertIn("PII_PHONE", rule_ids)
        self.assertIn("PII_ID_CARD", rule_ids)
        self.assertEqual(risk_level(score_issues(issues)), "critical")

    def test_unsupported_absolute_promise_is_rewrite_level(self):
        issues = run_all_rules(
            "是否支持私有化部署？",
            "支持，所有客户都可以永久免费使用。",
            ["支持私有化部署，需联系销售确认方案。"],
        )
        rule_ids = {issue.rule_id for issue in issues}

        self.assertIn("BUSINESS_ABSOLUTE_PROMISE", rule_ids)
        self.assertIn("EVIDENCE_UNSUPPORTED_CLAIM", rule_ids)
        self.assertIn(decision_for(score_issues(issues)), {"rewrite", "human_review"})

    def test_safe_content_has_low_score(self):
        issues = run_all_rules(
            "如何重置密码？",
            "可以通过忘记密码入口使用绑定邮箱完成验证。",
            ["登录页支持忘记密码，可通过绑定邮箱验证。"],
        )

        self.assertEqual(issues, [])
        self.assertEqual(decision_for(score_issues(issues)), "approve")


if __name__ == "__main__":
    unittest.main()
