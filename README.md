# 智能 QA 内容审核 Agent

本项目用于设计并实现一个依托 LangGraph 的智能 QA 内容审核 Agent 方案，面向企业问答、客服问答、知识库问答、RAG 输出审核等场景。

当前交付内容：

- 完整需求分析文档。
- 项目整体架构设计。
- LangGraph 多节点编排方案。
- 问答内容校验规则与风险识别流程。
- 可运行的本地规则审核 demo。
- 单元测试，验证风险识别与路由逻辑。

## 快速运行

```powershell
python demo.py
python -m unittest discover -s tests
```

如使用 Codex bundled Python：

```powershell
& 'C:\Users\刘佳煜\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' demo.py
& 'C:\Users\刘佳煜\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests
```

## 目录结构

```text
QA审核/
  README.md
  demo.py
  requirements.txt
  docs/
    01_需求分析.md
    02_业务流程梳理.md
    03_整体架构设计.md
    04_LangGraph节点编排设计.md
    05_审核规则与风险识别.md
  src/
    qa_audit_agent/
      __init__.py
      models.py
      rules.py
      pipeline.py
      graph.py
  tests/
    test_rules.py
    test_pipeline.py
```

## 审核分层

1. 输入完整性校验：问题、答案、来源、业务线、用户类型。
2. 基础安全校验：违法违规、敏感个人信息、仇恨辱骂、色情暴力、自伤等。
3. 业务一致性校验：是否答非所问、是否超出知识库、是否缺少依据。
4. 事实与引用校验：答案是否能被证据支撑，是否存在幻觉风险。
5. 风险分级与路由：通过、人工复核、拒绝、重写。
6. 审计记录：输出问题、命中规则、风险等级、处理建议。

## LangGraph 节点

核心节点设计：

- `normalize_input`
- `policy_rule_check`
- `evidence_check`
- `business_consistency_check`
- `risk_score`
- `route_decision`
- `rewrite_answer`
- `validate_rewrite`
- `human_review`
- `finalize_report`

当前本地版本不依赖外部模型，先用规则引擎跑通审核链路；`src/qa_audit_agent/graph.py` 已预留 LangGraph `StateGraph` 编排实现。

## 循环验证机制

当初次审核决策为 `rewrite` 时，系统会进入循环：

1. 生成候选安全答案。
2. 对候选答案再次执行规则审核。
3. 如果候选答案仍命中中高风险规则，则重新生成。
4. 最多重写 3 次；仍不通过则转人工复核。
5. 只有候选答案通过二次审核后，最终输出才会标记为可通过。
