# 语义分拣规则 (Semantic Triage Rules)

> 2026-03-25 架构决策：正式弃用“全局画像干预 (Persona Intervention)”，转向“确定性条件 + 语义匹配”的路由规则引擎。

## 1. 为什么弃用“画像干预”？

在早期的设计中，系统试图通过 Phase 2 推断用户的“画像（Persona，如：主管、HR、开发）”，并在 Phase 4 中将画像作为全局 Prompt 注入（`owner_focus`），以此来干预邮件的分类和待办状态。

**这种设计在工程落地中暴露了致命缺陷：**
1. **黑盒脑补，破坏硬逻辑**：大模型会基于“主管”画像，强行把 `recipient_role == group_only` 的群组邮件推断为“需要我审批”，破坏了底层的确定性逻辑。
2. **牵一发而动全身**：用户修改画像中的一句话，无法预测会如何影响下游数百封邮件的判定，缺乏安全感。
3. **不可测试**：画像是全局软提示，无法对单条干预逻辑进行精准的回测（Dry Run）。

## 2. 新架构：语义规则引擎 (Routing Rules)

我们引入 `routing-rules.yaml` 作为用户干预系统走向的唯一合法途径。它结合了传统邮件客户端的**硬边界**与大模型的**软语义**。

### 2.1 核心基因
- **硬边界 (Hard Splits)**：利用结构化字段（如 `recipient_role`, `sender_domain`）进行绝对拦截，不经过大模型，保证下限。
- **软语义 (Semantic Bundles)**：利用轻量级 LLM 对邮件内容进行 Boolean 判断（如 `semantic_match: "这是一封告警邮件"`），保证泛化能力。
- **自然语言编程**：用户通过与 Agent 对话，由 Agent 负责将自然语言诉求翻译并写入 YAML 规则。

### 2.2 规则 Schema 示例

规则文件存放于 `config/routing-rules.yaml`。

```yaml
rules:
  - id: rule_group_notification_ignore
    name: "群组通知降噪"
    active: true
    description: "当我是通过邮件组收到系统通知或告警时，不要算作我的待办"
    conditions:
      match_all:
        - field: "recipient_role"
          operator: "in"
          value: ["group_only", "cc_only"]  # 硬边界：只处理非直接收件人
        - field: "semantic_intent"
          operator: "is_true"
          value: "这是一封系统自动生成的告警、监控或流水线通知" # 软语义：轻量级 LLM 判断
    actions:
      set_state: "monitor_only"
      set_waiting_on: null
      add_tags: ["system_alert"]
      skip_phase4: true # 直接跳过后续昂贵的 LLM 深度分析
```

## 3. 在流水线中的位置：Phase 3.5 Attention Gate

规则引擎作为 **Phase 3.5 (注意力闸门)** 的核心组件运行：
1. **前置拦截**：在 Phase 3 (Lifecycle 建模) 之后，Phase 4 (深度价值提取和草稿生成，最昂贵) 之前执行。
2. **降本增效**：命中 `skip_phase4: true` 或被降级为 `monitor_only` / `archived` 的邮件，将直接绕过 Phase 4 的 Token 消耗。

## 4. 交互闭环 (Agent Skill)

Openclaw Agent 将提供以下核心能力：
- **创建规则**：将用户的自然语言（“以后张三发来的周报我都只看不回”）转化为 YAML 规则。
- **本地回测 (Dry Run)**：在保存规则前，Agent 可调用 `twinbox rule test --rule-id X --recent-days 7`，向用户展示该规则在过去 7 天邮件中的命中情况。
- **应用生效**：确认无误后保存规则，并提示用户重刷队列（`twinbox-orchestrate`）。
