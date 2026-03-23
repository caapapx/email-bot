# Task-Facing CLI Specification

日期：2026-03-23
状态：Draft

## 执行摘要

本规范定义 twinbox 的任务导向命令面（task-facing CLI），作为现有编排契约（orchestration contract）之上的稳定交互层。

**核心原则**：

- task-facing 命令是 phase artifacts 的投影视图，不是第二套推理管线
- 命令围绕任务和产品对象，不围绕内部阶段
- 每个命令默认支持 `--json` 结构化输出
- explainability 是默认能力，不是可选附加

**目标用户**：

- skill 和 agent runtime
- listener/action 服务
- 人工交互和调试
- 未来 review surface

## 命令树

```text
twinbox
  orchestrate          # 现有编排层命令（保留）
    roots
    contract
    run

  context              # 用户上下文管理（焦点 2）
    import-material
    upsert-fact
    profile-set
    refresh

  queue                # 队列视图（优先落地）
    list
    show
    explain

  thread               # 线程检视
    inspect
    summarize
    explain

  digest               # 摘要视图
    daily
    weekly

  action               # 动作建议（后续）
    suggest
    materialize
    apply

  review               # 审核面（后续）
    list
    show
    approve
    reject
```

## 分层语义

### 编排层（orchestrate）

- 面向实现层和 phase 驱动
- 保留给开发、调试、批处理和兼容旧脚本
- 直接操作 phase contract 和 step execution

### 任务层（context/queue/thread/digest/action/review）

- 面向产品层和任务调用
- skill、listener、review runtime 优先消费这层
- 不暴露 phase 内部细节

## 核心对象模型

### ThreadCard

线程状态的轻量投影。

```yaml
thread_id: string
state: string  # waiting_on_me | waiting_on_them | monitor_only | cc_only | closed
waiting_on: string | null
last_activity_at: string  # ISO 8601
confidence: float  # 0.0-1.0
evidence_refs: list[string]
context_refs: list[string]
why: string  # 简短解释
```

### QueueView

队列的稳定视图。

```yaml
queue_type: string  # urgent | pending | sla_risk | stale
items: list[ThreadCard]
rank_reason: dict[thread_id, string]
review_required: bool
generated_at: string  # ISO 8601
stale: bool
```

### DigestView

摘要的结构化视图。

```yaml
digest_type: string  # daily | weekly
sections: dict[string, object]
generated_at: string  # ISO 8601
stale: bool
```

对于 `weekly` digest，`sections` 应至少包含：

```yaml
action_now: list[ThreadCard]  # 必须今天/下周一前处理
backlog: list[ThreadCard]     # 仍待处理但不紧急
important_changes: string     # 本周重要变化摘要
```

### ActionCard

动作建议（后续实现）。

```yaml
action_id: string
thread_id: string
action_type: string  # reply | forward | archive | flag
why_now: string
risk_level: string  # low | medium | high
required_review_fields: list[string]
suggested_draft_mode: string | null
```

## 命令规范

### queue list

列出指定类型的队列。

**用法**：

```bash
twinbox queue list [--type TYPE] [--json]
```

**参数**：

- `--type TYPE`：队列类型，可选值：`urgent`、`pending`、`sla_risk`、`stale`、`all`（默认：`all`）
- `--json`：输出 JSON 格式

**输出**（文本模式）：

```text
Queue: urgent (3 items, generated 2026-03-23T09:00:00Z)
  - thread-abc123: Waiting on me, last activity 2 days ago
  - thread-def456: Waiting on me, last activity 1 day ago
  - thread-ghi789: Monitor only, high risk

Queue: pending (5 items, generated 2026-03-23T09:00:00Z)
  ...
```

**输出**（JSON 模式）：

```json
{
  "queues": [
    {
      "queue_type": "urgent",
      "items": [...],
      "rank_reason": {...},
      "review_required": false,
      "generated_at": "2026-03-23T09:00:00Z",
      "stale": false
    },
    ...
  ]
}
```

**实现映射**：

- 读取 `runtime/validation/phase-4/daily-urgent.yaml`
- 读取 `runtime/validation/phase-4/pending-replies.yaml`
- 读取 `runtime/validation/phase-4/sla-risks.yaml`
- 投影为 `QueueView` 对象

### queue show

显示指定队列的详细信息。

**用法**：

```bash
twinbox queue show TYPE [--json]
```

**参数**：

- `TYPE`：队列类型，必选，可选值：`urgent`、`pending`、`sla_risk`
- `--json`：输出 JSON 格式

**输出**（文本模式）：

```text
Queue: urgent
Generated: 2026-03-23T09:00:00Z
Status: fresh
Items: 3

1. thread-abc123
   State: waiting_on_me
   Last activity: 2 days ago
   Confidence: 0.85
   Why: Customer escalation, no response in 48h

2. thread-def456
   ...
```

**输出**（JSON 模式）：

```json
{
  "queue_type": "urgent",
  "items": [
    {
      "thread_id": "thread-abc123",
      "state": "waiting_on_me",
      "waiting_on": "me",
      "last_activity_at": "2026-03-21T10:30:00Z",
      "confidence": 0.85,
      "evidence_refs": ["envelope-5", "envelope-8"],
      "context_refs": ["escalation-policy"],
      "why": "Customer escalation, no response in 48h"
    },
    ...
  ],
  "rank_reason": {
    "thread-abc123": "High priority: customer escalation + SLA risk"
  },
  "review_required": false,
  "generated_at": "2026-03-23T09:00:00Z",
  "stale": false
}
```

### queue explain

解释为什么某个线程在队列中。

**用法**：

```bash
twinbox queue explain TYPE THREAD_ID [--json]
```

**参数**：

- `TYPE`：队列类型
- `THREAD_ID`：线程 ID
- `--json`：输出 JSON 格式

**输出**（文本模式）：

```text
Thread: thread-abc123
Queue: urgent
Rank: #1

Why in this queue:
- State: waiting_on_me (confidence: 0.85)
- Last activity: 2 days ago (2026-03-21T10:30:00Z)
- Evidence: envelope-5 (customer escalation), envelope-8 (follow-up)
- Context: escalation-policy (response within 24h)

Ranking reason:
High priority: customer escalation + SLA risk
```

**输出**（JSON 模式）：

```json
{
  "thread_id": "thread-abc123",
  "queue_type": "urgent",
  "rank": 1,
  "card": {
    "thread_id": "thread-abc123",
    "state": "waiting_on_me",
    ...
  },
  "rank_reason": "High priority: customer escalation + SLA risk",
  "explainability": {
    "state_evidence": ["envelope-5", "envelope-8"],
    "context_refs": ["escalation-policy"],
    "confidence": 0.85
  }
}
```

### thread inspect

检视线程的当前状态。

**用法**：

```bash
twinbox thread inspect THREAD_ID [--json]
```

**参数**：

- `THREAD_ID`：线程 ID
- `--json`：输出 JSON 格式

**输出**（文本模式）：

```text
Thread: thread-abc123
State: waiting_on_me
Waiting on: me
Last activity: 2 days ago (2026-03-21T10:30:00Z)
Confidence: 0.85

Evidence:
- envelope-5: customer escalation
- envelope-8: follow-up reminder

Context:
- escalation-policy: response within 24h
- customer-tier: premium

Why: Customer escalation, no response in 48h
```

**输出**（JSON 模式）：

```json
{
  "thread_id": "thread-abc123",
  "state": "waiting_on_me",
  "waiting_on": "me",
  "last_activity_at": "2026-03-21T10:30:00Z",
  "confidence": 0.85,
  "evidence_refs": ["envelope-5", "envelope-8"],
  "context_refs": ["escalation-policy", "customer-tier"],
  "why": "Customer escalation, no response in 48h",
  "explainability": {
    "state_reasoning": "Last message from customer with escalation keywords",
    "confidence_factors": [
      "Clear action request in last message",
      "No response from me in 48h",
      "Escalation policy triggered"
    ]
  }
}
```

### thread explain

解释线程状态的推断依据。

**用法**：

```bash
twinbox thread explain THREAD_ID [--json]
```

**参数**：

- `THREAD_ID`：线程 ID
- `--json`：输出 JSON 格式

**输出**（文本模式）：

```text
Thread: thread-abc123
Current state: waiting_on_me

Why this state:
1. Last message from customer (envelope-8, 2026-03-21T10:30:00Z)
2. Message contains action request: "Please confirm by EOD"
3. No response from me in 48h
4. Escalation policy triggered (customer-tier: premium)

Confidence: 0.85
- Clear action request: +0.3
- Recent activity: +0.2
- Context match: +0.35

Alternative interpretations:
- Could be "monitor_only" if customer is just FYI (confidence: 0.15)
```

**输出**（JSON 模式）：

```json
{
  "thread_id": "thread-abc123",
  "state": "waiting_on_me",
  "explainability": {
    "reasoning_steps": [
      "Last message from customer (envelope-8, 2026-03-21T10:30:00Z)",
      "Message contains action request: \"Please confirm by EOD\"",
      "No response from me in 48h",
      "Escalation policy triggered (customer-tier: premium)"
    ],
    "confidence": 0.85,
    "confidence_breakdown": {
      "clear_action_request": 0.3,
      "recent_activity": 0.2,
      "context_match": 0.35
    },
    "alternative_states": [
      {
        "state": "monitor_only",
        "confidence": 0.15,
        "reason": "Could be just FYI if no explicit action required"
      }
    ]
  }
}
```

### digest daily

显示每日摘要。

**用法**：

```bash
twinbox digest daily [--json]
```

**参数**：

- `--json`：输出 JSON 格式

**输出**（文本模式）：

```text
Daily Digest (2026-03-23T09:00:00Z)

Urgent (3 items):
- thread-abc123: Customer escalation, no response in 48h
- thread-def456: ...
- thread-ghi789: ...

Pending replies (5 items):
- thread-jkl012: ...
- ...

SLA risks (2 items):
- thread-mno345: ...
- ...
```

**输出**（JSON 模式）：

```json
{
  "digest_type": "daily",
  "sections": {
    "urgent": {
      "items": [...]
    },
    "pending": {
      "items": [...]
    },
    "sla_risks": {
      "items": [...]
    }
  },
  "generated_at": "2026-03-23T09:00:00Z",
  "stale": false
}
```

### digest weekly

显示每周摘要。

**用法**：

```bash
twinbox digest weekly [--json]
```

**参数**：

- `--json`：输出 JSON 格式

**输出**（文本模式）：

```text
Weekly Brief (2026-03-23T09:00:00Z)

Action now (必须今天/下周一前处理):
- thread-abc123: Customer escalation, no response in 48h
- thread-def456: ...

Backlog (仍待处理但不紧急):
- thread-ghi789: ...
- ...

Important changes this week:
- 3 new escalations
- 5 threads closed
- 2 threads moved to monitor_only
```

**输出**（JSON 模式）：

```json
{
  "digest_type": "weekly",
  "sections": {
    "action_now": [
      {
        "thread_id": "thread-abc123",
        "state": "waiting_on_me",
        ...
      },
      ...
    ],
    "backlog": [
      {
        "thread_id": "thread-ghi789",
        ...
      },
      ...
    ],
    "important_changes": "3 new escalations, 5 threads closed, 2 threads moved to monitor_only"
  },
  "generated_at": "2026-03-23T09:00:00Z",
  "stale": false
}
```

## context 命令（焦点 2）

### context import-material

导入用户材料（文件、文本）。

**用法**：

```bash
twinbox context import-material --file PATH [--label LABEL] [--json]
twinbox context import-material --text TEXT [--label LABEL] [--json]
```

**参数**：

- `--file PATH`：材料文件路径
- `--text TEXT`：材料文本内容
- `--label LABEL`：材料标签（可选）
- `--json`：输出 JSON 格式

**输出**（文本模式）：

```text
Material imported: material-abc123
Label: escalation-policy
Source: /path/to/policy.md
Indexed: 2026-03-23T09:00:00Z
```

**输出**（JSON 模式）：

```json
{
  "material_id": "material-abc123",
  "label": "escalation-policy",
  "source": "/path/to/policy.md",
  "indexed_at": "2026-03-23T09:00:00Z"
}
```

### context upsert-fact

更新或插入用户确认的事实。

**用法**：

```bash
twinbox context upsert-fact --key KEY --value VALUE [--json]
```

**参数**：

- `--key KEY`：事实键
- `--value VALUE`：事实值
- `--json`：输出 JSON 格式

**输出**（文本模式）：

```text
Fact upserted: customer-tier
Value: premium
Updated: 2026-03-23T09:00:00Z
```

**输出**（JSON 模式）：

```json
{
  "key": "customer-tier",
  "value": "premium",
  "updated_at": "2026-03-23T09:00:00Z"
}
```

### context profile-set

设置用户画像配置。

**用法**：

```bash
twinbox context profile-set --key KEY --value VALUE [--json]
```

**参数**：

- `--key KEY`：画像键
- `--value VALUE`：画像值
- `--json`：输出 JSON 格式

**输出**（文本模式）：

```text
Profile updated: response-style
Value: formal
Updated: 2026-03-23T09:00:00Z
```

**输出**（JSON 模式）：

```json
{
  "key": "response-style",
  "value": "formal",
  "updated_at": "2026-03-23T09:00:00Z"
}
```

### context refresh

触发 context 更新后的局部重算。

**用法**：

```bash
twinbox context refresh [--full] [--json]
```

**参数**：

- `--full`：全量刷新（默认：局部刷新）
- `--json`：输出 JSON 格式

**输出**（文本模式）：

```text
Context refresh triggered
Mode: partial
Affected threads: 3
Affected queues: urgent, pending
Started: 2026-03-23T09:00:00Z
```

**输出**（JSON 模式）：

```json
{
  "mode": "partial",
  "affected_threads": ["thread-abc123", "thread-def456", "thread-ghi789"],
  "affected_queues": ["urgent", "pending"],
  "started_at": "2026-03-23T09:00:00Z"
}
```

## 实现策略

### 阶段 1：queue 命令（优先落地）

1. 创建 `python/src/twinbox_core/task_cli.py`
2. 实现 `queue list`、`queue show`、`queue explain`
3. 从现有 Phase 4 artifacts 投影出 `QueueView`
4. 添加 `scripts/twinbox` 作为统一入口

### 阶段 2：thread 命令

1. 实现 `thread inspect`、`thread explain`
2. 从 Phase 3/4 artifacts 投影出 `ThreadCard`
3. 补充 explainability 支持

### 阶段 3：digest 命令

1. 实现 `digest daily`、`digest weekly`
2. 从 Phase 4 artifacts 投影出 `DigestView`
3. 支持 weekly 的分层结构

### 阶段 4：context 命令

1. 实现 `context import-material`、`context upsert-fact`、`context profile-set`
2. 实现 `context refresh` 触发局部重算
3. 定义 context 存储格式和更新协议

### 阶段 5：action 和 review 命令（后续）

1. 实现 `action suggest`、`action materialize`
2. 实现 `review list`、`review show`
3. 定义 action 和 review 的存储格式

## 非目标

本规范不涉及：

- listener/action 常驻服务的实现
- 远程 runtime 的部署
- UI 或 web 界面
- 多邮箱并行支持
- 自动发送邮件（仍在 Phase Gate 控制下）

## 与现有架构的关系

- `orchestration.py`：编排层，保留不变
- `task_cli.py`：任务层，新增
- Phase 1-4 artifacts：真相源，不变
- `renderer.py`：视图层，可能需要扩展以支持 task-facing 输出

## 参考文档

- [core-refactor-plan.md](../plans/core-refactor-plan.md)
- [architecture.md](../architecture.md)
- [pipeline-orchestration-contract.md](./pipeline-orchestration-contract.md)
