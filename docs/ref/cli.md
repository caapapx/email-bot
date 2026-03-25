# Task-Facing CLI Specification

日期：2026-03-26
状态：Implemented (mailbox, queue, context, thread, digest, action, review 命令已完成)

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

> **注意**：`twinbox` 和 `twinbox-orchestrate` 是两个独立入口。
> `twinbox` = task-facing CLI（`twinbox_core.task_cli:main`）
> `twinbox-orchestrate` = 编排 CLI（`twinbox_core.orchestration:main`）

```text
twinbox                      # task-facing CLI 入口
  context                    # 用户上下文管理
    import-material
    upsert-fact
    profile-set
    refresh

  mailbox                    # 邮箱登录与只读预检
    preflight

  queue                      # 队列视图
    list
    show
    explain

  thread                     # 线程检视
    inspect
    progress
    summarize                # 🚧 未实现
    explain

  digest                     # 摘要视图
    daily
    pulse
    weekly

  task                       # OpenClaw-facing thin task routes
    latest-mail
    todo
    progress
    weekly
    mailbox-status

  rule                       # 语义分拣规则管理
    list
    add
    remove
    test

  action                     # 动作建议
    suggest
    materialize
    apply                    # 🚧 未实现

  review                     # 审核面
    list
    show
    approve                  # 🚧 未实现
    reject                   # 🚧 未实现

twinbox-orchestrate          # 编排 CLI 入口（独立二进制）
  roots
  contract
  run [--phase N]            # 省略 --phase = 跑满 Phase 1–4
  schedule --job NAME        # 直接执行一个已解析的宿主调度作业
  bridge --event-text TEXT   # 解析 OpenClaw/system-event 文本并转发到 schedule
  bridge-poll                # 轮询 OpenClaw cron runs，并消费新的 Twinbox bridge 事件
```

## 分层语义

### 编排层（twinbox-orchestrate，独立入口）

- 独立二进制入口：`twinbox-orchestrate`（非 `twinbox` 的子命令）
- 面向实现层和 phase 驱动
- 保留给开发、调试、批处理和兼容旧脚本
- 直接操作 phase contract 和 step execution
- **`run` 子命令**：`twinbox-orchestrate run [--phase N]`，`N` 为 `1`–`4`。省略 `--phase` 时按契约顺序执行 Phase 1→4 全部步骤。示例：仅刷新 Phase 4 投影用 `twinbox-orchestrate run --phase 4`。
- **`schedule` 子命令**：执行已经确定好的宿主作业，例如 `twinbox-orchestrate schedule --job daytime-sync --format json`。
- **`bridge` 子命令**：解析 `system-event` 文本协议，再转发到 `schedule`。适合宿主 bridge/service 在拿到事件文本后调用，例如 `twinbox-orchestrate bridge --event-text '{"kind":"twinbox.schedule","job":"daytime-sync"}' --format json`。
- **`bridge-poll` 子命令**：轮询 OpenClaw Gateway 的 `cron.list` / `cron.runs`，识别新产生的 Twinbox `systemEvent` 运行记录，再转发到 `bridge`。适合用户态 systemd/service 定时调用，例如 `twinbox-orchestrate bridge-poll --format json`。

### 任务层（mailbox/context/queue/thread/digest/action/review）

- 面向产品层和任务调用
- skill、listener、review runtime 优先消费这层
- 不暴露 phase 内部细节

## 核心对象模型

### ThreadCard

线程状态的轻量投影。

```yaml
thread_id: string
state: string  # direct | cc_only | group_only | indirect | unknown
waiting_on: string | null
last_activity_at: string  # ISO 8601
confidence: float  # 0.0-1.0
evidence_refs: list[string]
context_refs: list[string]
why: string  # 简短解释，若为非 direct 则包含警告文案
```

说明：
- `thread_id` 在 `task todo --json` 这类薄路由里，可能带有 `[CC]` 或 `[GRP]` 前缀，用来显式暴露 recipient routing 信号
- `[CC]` 表示邮箱 owner 在 `Cc` 列表中（含 `cc_only` 和 `indirect` 角色）
- `[GRP]` 表示邮箱 owner 不在 `To/Cc`，而是通过邮件组或别名收到该线程（`group_only` 角色）
- **recipient_role 降权策略**：
  - `direct`：1.0 (不降权)
  - `cc_only` / `indirect`：0.6 (默认乘数)
  - `group_only`：0.4 (大幅降权)
  - `unknown`：1.0 (样本不足，不降权)
- 所有非 `direct` 线程在 `why` 字段中会自动追加统一警告：`⚠️ 你不是主要收件人，请确认是否真的需要你处理`

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
digest_type: string  # daily | pulse | weekly
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

### MailboxPreflightResult

OpenClaw 和 skill runtime 消费的邮箱登录/预检结果。

```yaml
login_mode: string  # password-env
login_stage: string  # unconfigured | validated | mailbox-connected
status: string  # success | warn | fail
error_code: string | null
exit_code: int
code_root: string
state_root: string
env_file: string | null
missing_env: list[string]
defaults_applied: dict[string, string]
effective_account: string
env_sources:
  mode: string
  state_root_env_file: string | null
  state_root_env_present: string
checks:
  env:
    status: string
    missing_env: list[string]
    fix_commands: list[string]
  config_render:
    status: string
    config_file: string | null
  imap:
    status: string
    error_code: string | null
    detail: string | null
  smtp:
    status: string
    error_code: string | null
    detail: string | null
actionable_hint: string
next_action: string
```

## 命令规范

### mailbox preflight

执行 password-env 模式下的邮箱登录预检。该命令优先服务 OpenClaw 和 skill adapter，也可用于本地只读诊断。

**用法**：

```bash
twinbox mailbox preflight [--json] [--account NAME] [--folder INBOX] [--page-size 5] [--state-root PATH]
```

**参数**：

- `--json`：输出稳定 JSON 契约，供 OpenClaw 消费
- `--account NAME`：覆盖 `MAIL_ACCOUNT_NAME`
- `--folder INBOX`：用于只读 envelope list 的文件夹（默认 `INBOX`）
- `--page-size 5`：只读拉取条数（默认 `5`）
- `--state-root PATH`：覆盖 twinbox state root
- 默认 state root 解析顺序：`TWINBOX_STATE_ROOT` / `~/.config/twinbox/state-root` / legacy `TWINBOX_CANONICAL_ROOT` / `~/.config/twinbox/canonical-root` / 当前 code root

**状态语义**：

- `unconfigured`：缺少运行所需邮箱配置；不会尝试渲染 config 或连接 IMAP
- `validated`：env 已齐全且 himalaya config 已生成，但 IMAP 仍未通过
- `mailbox-connected`：IMAP 只读验证成功

**配置来源语义**：

- process env 优先，其次才是 `state root/.env`
- OpenClaw-native 部署推荐把邮箱配置注入 skill process env
- repo `.env` / `state root/.env` 主要作为本地开发或自托管 fallback

**只读边界**：

- 只读预检只用 IMAP envelope list 作为连接证据
- SMTP 在只读模式下不阻塞 Phase 1-4，统一返回 `warn` + `smtp_skipped_read_only`

**退出码**：

- `0`：成功，或只存在只读模式下的 SMTP warn
- `2`：配置缺失或 config render 失败
- `3`：IMAP 网络/TLS/命令级失败
- `4`：IMAP 认证失败
- `5`：内部错误（例如 `himalaya` 缺失）

**输出字段**：

- `status`：`success | warn | fail`
- `missing_env`：缺失 env 列表
- `actionable_hint`：可直接显示给用户的修复提示
- `next_action`：下一步建议，例如重新预检或运行 Phase 1

**实现映射**：

- 解析 `.env` 与进程环境变量
- 应用默认值：`MAIL_ACCOUNT_NAME=myTwinbox`、`MAIL_DISPLAY_NAME={MAIL_ACCOUNT_NAME}`、`IMAP_ENCRYPTION=tls`、`SMTP_ENCRYPTION=tls`
- 渲染 `runtime/himalaya/config.toml`
- 执行 `himalaya envelope list --output json`
- 写入 `runtime/validation/preflight/mailbox-smoke.json`

### queue list

列出所有队列概览。

**用法**：

```bash
twinbox queue list [--json]
```

**参数**：

- `--json`：输出 JSON 格式

> 注：当前实现固定返回 urgent、pending、sla_risk 三个队列，无 `--type` 过滤。

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

输出队列投影机制的静态说明。

**用法**：

```bash
twinbox queue explain
```

> 注：当前实现为静态文本输出，不接受参数，不支持 `--json`。
> 未来可扩展为按 `TYPE THREAD_ID` 解释具体排名。

**输出**（文本模式）：

```text
队列投影说明
============

twinbox 的队列视图从 Phase 4 artifacts 投影而来，不是独立的数据管道。

数据源映射：
- urgent 队列 <- runtime/validation/phase-4/daily-urgent.yaml
- pending 队列 <- runtime/validation/phase-4/pending-replies.yaml
- sla_risk 队列 <- runtime/validation/phase-4/sla-risks.yaml
...
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

### thread progress

从 `activity-pulse` 中按线程 key、主题片段或业务关键词查询当前进展。

**用法**：

```bash
twinbox thread progress QUERY [--limit 5] [--json]
```

**参数**：

- `QUERY`：线程 key、主题片段或业务关键词
- `--limit 5`：最多返回 5 条匹配
- `--json`：输出 JSON 格式

**实现映射**：

- 读取 `runtime/validation/phase-4/activity-pulse.json`
- 在 `thread_index` 中做轻量规则匹配，不依赖额外语义检索

### digest daily

显示每日摘要。

**用法**：

```bash
twinbox digest daily [--json]
```

### digest pulse

显示小时级日内脉冲，用于“今天发生了什么 / 哪些线程有推进 / 哪些待我跟进”的最小推送载荷。

**用法**：

```bash
twinbox digest pulse [--json]
```

**参数**：

- `--json`：输出 JSON 格式

**实现映射**：

- 读取 `runtime/validation/phase-4/activity-pulse.json`
- 返回 `notifiable`、`recent_activity`、`needs_attention` 三段视图
- 同时带上最小推送载荷 `notify_payload`

> 注：`activity-pulse.json` 不会由 `digest pulse` 现算；需先运行 `twinbox-orchestrate schedule --job daytime-sync`。

## Task 路由选型标准

`task ...` 子命令不是第二套 CLI 领域模型，而是面向 hosted skill / agent runtime 的薄路由层。

设计约束：

- 必须薄包装现有只读能力，不能引入新的推理链路
- 必须服务通用用户意图，而不是某个团队特有术语
- 必须适合作为 prompt smoke 和默认 skill 入口
- 必须能清晰暴露“命令是否真的执行”这一事实

按当前实现，核心 task 维度分为：

- `latest-mail`：总览型问题，“今天发生了什么 / 最新邮件情况”
- `todo`：待办型问题，“我现在要处理什么”
- `progress`：下钻型问题，“某件事现在进展如何”
- `mailbox-status`：健康检查型问题，“邮箱配好没 / skill 能不能跑”

补充说明：

- `weekly` 保留为时间尺度更长的补充入口，但不是 hosted smoke 的第一优先级
- 如果未来想新增 task 路由，应先证明它仍然是“薄包装 + 通用意图 + 只读高可靠”，否则应考虑扩到底层命令组，而不是继续堆 `task`

### task latest-mail

为 OpenClaw / skill 场景提供的稳定任务入口，对“帮我看下最新邮件情况 / 今天发生了什么”这类提问返回统一投影。

**用法**：

```bash
twinbox task latest-mail [--json]
```

**实现语义**：

- 薄包装 `digest pulse`
- 返回 `summary`、`urgent_top_k`、`recent_activity`、`needs_attention`
- 不新增推理链路，不直接访问邮箱

### task todo

为“我有哪些待办 / 待回复 / 最值得关注的线程”提供统一任务入口。

**用法**：

```bash
twinbox task todo [--json]
```

**实现语义**：

- 薄包装 `queue urgent` + `queue pending`
- 同时附带现有 `action suggest` 与 `review list` 投影
- 不新增动作生成能力

### task progress

为“某个事情进展如何”提供统一任务入口。

**用法**：

```bash
twinbox task progress QUERY [--limit 5] [--json]
```

**实现语义**：

- 薄包装 `thread progress`
- 按 thread key、主题片段或业务关键词匹配
- JSON 输出会额外补 `recipient_role` 与 `thread_key_display`
- 当线程在 Phase 3 已被识别为 `cc_only` / `group_only` / `indirect` 时，`thread_key_display` 会带 `[CC]` 或 `[GRP]` 前缀，避免 hosted skill 在“查进展”问法下丢失收件角色信号

### task weekly

为“看当前周报/周简报”提供统一任务入口。

**用法**：

```bash
twinbox task weekly [--json]
```

**实现语义**：

- 薄包装 `digest weekly`
- 不新增周报推理逻辑

### task mailbox-status

为“邮箱配好没 / preflight 状态如何”提供统一任务入口。

**用法**：

```bash
twinbox task mailbox-status [--json]
```

**实现语义**：

- 薄包装 `mailbox preflight`
- 保留原有 `login_stage` / `status` / `missing_env` 语义

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

导入用户材料（文件）。

**用法**：

```bash
twinbox context import-material SOURCE
```

**参数**：

- `SOURCE`：材料文件路径（位置参数）

**输出**：

```text
已导入材料: policy.md -> runtime/context/material-extracts/policy.md
更新清单: runtime/context/material-manifest.json
已生成抽取 Markdown（供 Phase 4 引用）: runtime/context/material-extracts/policy_md.extracted.md
```

对 `.csv`、`.xlsx` / `.xlsm`、`.docx`、`.pptx`、`.md`、`.txt` 会额外生成同目录下的 `*.extracted.md`（表格转 Markdown 表，Office 为 OOXML 内文本抽取）。`twinbox-orchestrate run --phase 4` 的 context-pack 会将这些抽取合并进 `human_context.material_extracts_notes`。旧版 `.doc` / `.ppt` 需先另存为 `.docx` / `.pptx`；`.xlsx` 需安装 `openpyxl`。

> 注：当前不支持 `--json` 输出。

### context upsert-fact

更新或插入用户确认的事实。

**用法**：

```bash
twinbox context upsert-fact --id ID --type TYPE --content CONTENT [--source SRC]
```

**参数**：

- `--id ID`：事实 ID（必选）
- `--type TYPE`：事实类型（必选）
- `--content CONTENT`：事实内容（必选）
- `--source SRC`：来源（默认 `user_confirmed_fact`）

**输出**：

```text
已添加事实: customer-tier
保存到: runtime/context/manual-facts.yaml
```

> 注：当前不支持 `--json` 输出。

### context profile-set

设置用户画像配置。

**用法**：

```bash
twinbox context profile-set PROFILE [--key KEY --value VALUE]
```

**参数**：

- `PROFILE`：画像名称（位置参数，必选）
- `--key KEY`：配置键（支持嵌套如 `style.language`）
- `--value VALUE`：配置值
- 不带 `--key`/`--value` 时显示当前画像内容

**输出**：

```text
已更新配置: default.style.language = formal
```

> 注：当前不支持 `--json` 输出。

### context refresh

触发 context 更新后的局部重算。

**用法**：

```bash
twinbox context refresh
```

> 注：当前实现不接受 `--full` 或 `--json` 参数。仅打印提示文本建议用户手动运行 `twinbox-orchestrate run --phase 1`。

**输出**：

```text
刷新 Phase 1 context-pack...
提示: 使用 'twinbox-orchestrate run --phase 1' 重新生成 Phase 1 artifacts
```

## 实现状态

### ✅ 阶段 1：queue 命令（已完成）

- ✅ 创建 `src/twinbox_core/task_cli.py`
- ✅ 实现 `queue list`、`queue show`、`queue explain`
- ✅ 从现有 Phase 4 artifacts 投影出 `QueueView`
- ✅ 添加 `scripts/twinbox` 作为统一入口

### ✅ 阶段 2：context 命令（已完成）

- ✅ 实现 `context import-material`、`context upsert-fact`、`context profile-set`
- ✅ 实现 `context refresh` 触发局部重算
- ✅ 定义 context 存储格式和更新协议

### ✅ 阶段 3：thread 命令（已完成）

- ✅ 实现 `thread inspect`、`thread explain`
- ✅ 从 Phase 3/4 artifacts 投影出 `ThreadCard`
- ✅ 补充 explainability 支持

### ✅ 阶段 4：digest 命令（已完成）

- ✅ 实现 `digest daily`、`digest weekly`
- ✅ 从 Phase 4 artifacts 投影出 `DigestView`
- ✅ 支持 weekly 的分层结构

### ✅ 阶段 5：action 和 review 命令（已完成）

1. ✅ 实现 `action suggest`、`action materialize`
2. ✅ 实现 `review list`、`review show`
3. ✅ 实现 `ActionCard`、`ReviewItem` 数据对象（含 `to_dict()`）
4. ✅ 添加完整单元测试覆盖（27 个测试全部通过）

### ✅ 阶段 6：rule 命令（已完成）

- ✅ 实现 `rule list`、`rule add`、`rule remove`、`rule test`
- ✅ 支持 `config/routing-rules.yaml` 的读写与回测

### 🚧 未实现命令

以下命令在命令树中声明但尚未实现，Skill 和模板不应引用：

- `thread summarize` — 线程摘要
- `action apply` — 执行行动
- `review approve` — 批准审核项
- `review reject` — 拒绝审核项

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

- [core-refactor-plan.md](../core-refactor.md)
- [architecture.md](./architecture.md)
- [pipeline-orchestration-contract.md](./orchestration.md)
