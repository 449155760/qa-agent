import unittest

from src.qa_audit_agent.pipeline import audit_qa


class PipelineTests(unittest.TestCase):
    def test_approve_safe_answer(self):
        result = audit_qa(
            {
                "case_id": "safe-001",
                "question": "如何重置密码？",
                "answer": "可以通过忘记密码入口使用绑定邮箱完成验证。",
                "evidence": ["登录页支持忘记密码，可通过绑定邮箱验证。"],
            }
        )

        self.assertEqual(result.decision, "approve")
        self.assertEqual(result.risk_level, "low")
        self.assertGreaterEqual(len(result.audit_trace), 6)

    def test_reject_critical_privacy_answer(self):
        result = audit_qa(
            {
                "case_id": "privacy-001",
                "question": "查一下用户身份证。",
                "answer": "身份证号是 110101199003071234。",
                "evidence": [],
            }
        )

        self.assertEqual(result.decision, "reject")
        self.assertEqual(result.risk_level, "critical")
        self.assertTrue(result.issues)

    def test_rewrite_when_evidence_missing(self):
        result = audit_qa(
            {
                "case_id": "missing-evidence-001",
                "question": "是否支持某功能？",
                "answer": "支持该功能。",
                "evidence": [],
            }
        )

        self.assertEqual(result.decision, "approve")
        self.assertIsNotNone(result.safe_answer)
        self.assertTrue(any(item["node"] == "validate_rewrite" for item in result.audit_trace))

    def test_rewrite_loop_regenerates_until_candidate_is_safe(self):
        result = audit_qa(
            {
                "case_id": "loop-001",
                "question": "是否支持私有化部署？",
                "answer": "支持，并且所有客户都可以永久免费使用私有化部署版本。",
                "evidence": ["产品支持私有化部署，需联系销售确认方案。"],
            }
        )

        rewrite_attempts = [
            item for item in result.audit_trace if item["node"] == "rewrite_answer"
        ]

        self.assertEqual(result.decision, "approve")
        self.assertIsNotNone(result.safe_answer)
        self.assertGreaterEqual(len(rewrite_attempts), 2)
        self.assertNotIn("永久免费", result.safe_answer)


if __name__ == "__main__":
    unittest.main()
