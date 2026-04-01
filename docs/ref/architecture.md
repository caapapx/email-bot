# 以价值优先、线程为中心的邮件 Copilot 架构

## 目标

构建一个稳定的邮件协作 Copilot 核心，在不分叉实现的前提下，服务不同公司、岗位与个人用户。

经过早期验证后，架构目标已经不再是“优先做通用邮件自动化（generic email automation）”，而是：

- 减少高优先级跟进被遗漏
- 把长线程压缩成用户可见的队列
- 先证明只读输出有价值，再生成草稿
- 始终把发送动作放在明确的人类审批之后

## 来自早期验证的现实校验

早期验证通常会改变架构优先级：

- 有些邮箱主要由重复性的工作流线程组成，而不是彼此独立的单封邮件
- 用户最直接感受到的价值通常是“我今天该跟进什么”，而不是“机器人能不能发邮件”
- 线程状态、证据和置信度，往往比大而全的分类覆盖更重要

一次运行特有的证据，应放在 **`runtime/validation/`**（或 state root 下本地验证输出目录）中，而不是写进这份架构文档。

## 设计原则

应该保持通用、稳定的“硬问题”：

- 邮箱连通性（mailbox connectivity）
- 邮件标准化（message normalization）
- 线程重建（thread reconstruction）
- 工作流状态推断（workflow state inference）
- 证据链接（evidence linking）
- 幂等同步（idempotent sync）
- 日志、审计与复核流程

应该保持可定制的部分：

- 组织领域映射（org domain map）
- 工作流词典（workflow dictionaries）
- 发件人与团队优先级
- 面向角色的风险阈值
- digest 格式
- 草稿风格与语气
- 升级路由（escalation routing）
- 重复性任务习惯
- 用户确认过的归属与术语事实

## 价值优先规则

- Thread over message：决策应基于线程上下文，而不是单封邮件快照。
- Outputs before automation：系统必须先证明只读输出有价值，再进入草稿和自动化。
- Evidence before confidence：每个重要结论都应指向支持它的消息或线程证据。
- Dominant workflow before minority workflow：先优化邮箱中占主导的工作流。
- Learn only from validated useful behavior：不要把每一次编辑都直接学成规则。
- 人工提供的上下文（human-supplied context）是一等输入，但必须有类型、来源标签和有效期。

## 支持的初始化模式

架构应支持三种等价的入口模式：

- 仅 agent 初始化（agent-only initialization）
- 引导式聊天或手工粘贴初始化
- 邮箱同步与用户材料共同参与的混合初始化

这三种模式最终都应收敛到同一套标准化上下文工件（normalized context artifacts）和同一条下游推断流水线。

当前已验证的实践边界：

- 用户态初始化（邮箱地址探测、画像、材料、路由规则、推送订阅）可以通过对话式渐进流程完成
- 宿主态部署（OpenClaw skill 文件同步、Gateway reload、`skills.entries.twinbox.env` 注入、bridge/poller/systemd 安装）仍属于外部运行时接线，不能假设只靠渠道消息框就能自动闭环
- 因此“对话式初始化”与“宿主级部署”应在架构上明确分层：前者写入 Twinbox 的标准化 context / profile / rule / subscription 状态，后者负责把这些能力接到 OpenClaw 宿主执行面

## 共享状态根（Shared State Root）

系统将可执行代码与实例本地状态分离。

定义：

- `code root`：当前 checkout，提供受版本管理的脚本、公式文件和实现逻辑
- `state root`：规范 checkout，提供 **`twinbox.json`**（邮箱/LLM/集成主配置）、`runtime/context/`、`runtime/validation/`；可选在本地生成验证报告目录（默认不入库）；历史 **`state root/.env`** 仅在迁移期被兼容读取

解析顺序：

- `code root`
  - `TWINBOX_CODE_ROOT`
  - `~/.config/twinbox/code-root`
  - 当前 checkout
- `state root`
  - `TWINBOX_STATE_ROOT`
  - `~/.config/twinbox/state-root`
  - 兼容层：`TWINBOX_CANONICAL_ROOT`
  - 兼容层：`~/.config/twinbox/canonical-root`
  - 默认回退到 `code root`

运行规则：

- linked worktree 在未配置共享 `state root` 时必须快速失败
- 并行 worker 可以从不同的 `code root` 路径执行，但必须读写同一个 `state root`
- 实例本地工件保留在 state root 中，不复制到每个 worker checkout
- 这一模式适用于 Phase 1-5；在 Phase 4-5 中尤其明显，因为 `loading`、`urgent/pending`、`sla-risks`、`weekly-brief`、`merge` 与 draft gating 都需要共享同一份 context pack 和原始输出
- 当前自托管默认布局仍允许 `code root == state root`，但这只是兼容的默认值，不是唯一部署形态

## 人类上下文平面（Human Context Plane）

这是一个横切输入平面，不是面向某个租户的临时 hack。

用途：

- 导入工作材料，例如 spreadsheet、文档、PDF、截图和笔记
- 导入用户声明的重复性习惯与类日历义务
- 导入用户确认的事实，用于修正低置信度推断
- 保留来源信息（provenance），让系统能解释某条结论来自邮件、材料还是用户声明

典型输入：

- 项目台账与执行追踪表
- 周报或月报义务
- 组织角色说明与术语映射
- 类似“这个线程通常只是 CC-only”或“这个发件人是系统机器人”这样的修正

读取器策略：

- 优先使用可插拔文档读取器（pluggable document readers），例如 spreadsheet parser、OCR pipeline 或基于 MCP 的 office 文档服务
- 如果某份材料无法被可靠解析，应保留文件清单（file manifest）和用户摘要，而不是直接丢弃

标准化上下文事实字段（normalized context fact fields）：

- `context_id`
- `source_type`
- `source_ref`
- `fact_type`
- `scope`
- `applies_to`
- `value`
- `valid_from`
- `valid_to`
- `freshness`
- `confidence`
- `confirmed_by_user`
- `merge_policy`
- `evidence_refs`

合并规则：

- 原始邮箱事实不能被静默覆盖
- 用户确认过的事实可以覆盖低置信度推断，但覆盖关系必须可见
- 重复性习惯和外部材料可以补充 due window、owner hint、glossary mapping 和 reporting obligation，即使单靠邮件无法推断
- 过期或陈旧的上下文应自动降低置信度

绑定规则：

- 用户文本、导入材料和长期 profile 更新，应通过标准化上下文事实或 profile config 进入系统，而不是直接改写线程
- `context_updated` 应触发针对受影响线程快照、队列和 digest 的定向重算
- 通用 profile config 可以影响排序、队列成员资格与呈现方式，但不应静默改写邮箱事实
- 只有显式的用户确认事实，才可以重标记 `cc_only`、`waiting_on_me`、`monitor_only` 这类 thread-state 结论，而且这种 override 必须保持可见
- recipient routing 必须区分 `direct`、`cc_only`、`group_only`：`cc_only` 只表示邮箱 owner 显式出现在 `Cc` 且不在 `To`；`group_only` 表示 owner 不在 `To/Cc`，但邮件通过邮件组或别名送达。默认只对 `cc_only` 做“仅抄送”降权，不能把 `group_only` 静默当成 `cc_only`
- phase 级上下文构建在解析 recipient routing 时，必须与 mailbox/preflight 使用同一 owner 解析顺序：process env 优先，缺失时回退到 **`state_root/twinbox.json`**（或兼容层 **`state_root/.env`**）中的邮箱 owner，避免脚本刷新与前台 OpenClaw 会话看到不同的收件角色

## 七层模型（Seven-Layer Model）

### 1. 传输层（Transport Layer）

用途：

- 连接 IMAP/SMTP
- 拉取 folder、envelope 和 message 数据
- 仅通过受控 gate 保存草稿或发送邮件

实现：

- 基于 `.env` 渲染 `himalaya` 配置
- 这一层不承载工作流或业务逻辑

### 2. 规范事件与线程层（Canonical Event and Thread Layer）

用途：

- 把 provider-specific 的邮件数据转换成稳定的 message 和 thread 模型

规范消息字段（canonical message fields）：

- `message_id`
- `folder`
- `from`
- `to`
- `cc`
- `subject`
- `received_at`
- `body_text`
- `attachments`
- `flags`

规范线程字段（canonical thread fields）：

- `thread_key`
- `participants`
- `last_activity_at`
- `message_count`
- `has_attachments`
- 组织域与外部域比例统计（thread 级摘要；具体 JSON 键名以 `context_builder` / 规范线程 schema 为准）
- `workflow_type`
- `state`
- `state_confidence`
- `evidence_refs`

为什么重要：

- 后续流水线应建立在稳定的线程事实之上，而不是 provider 的怪异行为之上
- 人类上下文应通过引用来增强这一层，而不是绕过 canonical model 直接写入

### 3. 工作流状态层（Workflow State Layer）

用途：

- 推断一个线程属于哪类工作流
- 推断线程当前所处阶段
- 推断系统当前在等待什么

输出：

- `workflow_type`
- `state`
- `owner_guess`
- `waiting_on`
- `due_hint`
- `risk_flags`
- `state_confidence`
- `evidence_refs`
- `context_refs`

当大量重复线程本身具有流程形状时，这一层往往就是系统真正的中心。

### 3.5. 注意力闸门（Attention Gate）与语义规则 (Routing Rules)

用途：

- 在各个 phase 之间渐进式过滤线程，让下游层只把 token 花在真正重要的线程上
- **执行用户定义的语义分拣规则 (`routing-rules.yaml`)**，结合硬边界与软语义，强制干预邮件流向（如：将群组告警邮件强制降级为 `monitor_only`）
- 每个 phase 都进一步收窄注意力窗口：全量 envelope 集合 → intent 过滤 → profile 过滤 → lifecycle 建模 → 规则拦截 → actionable 集合

工作方式：

- 每个 validation phase 输出一份 `attention-budget.yaml`，其中包含三类线程集合：`focus`、`deprioritize`、`skip`
- 下一个 phase 读取前一份 budget，仅对 `focus` 集合执行深度工作，如 body sampling、draft generation
- `skip` 线程不会被删除，它们仍保留在原始数据中，供审计和回溯
- 用户通过 `user_confirmed_fact` 做出的修正，可以随时把线程从 `skip` 提升回 `focus`

按 phase 的收窄方式：

| Phase | Gate action | Typical reduction |
|---|---|---|
| Phase 1 | 标记噪声候选（bot 通知、空线程、重复订阅） | 约 15-25% 的 envelope 被标记为 skip |
| Phase 2 | 基于 persona 增加排除规则（无关域名、无关 intent 类型） | 额外约 10-15% 被标记为 deprioritize |
| Phase 3 | 标记未建模线程（无法落入任何 lifecycle flow） | 约 20-30% 被降级 |
| Phase 4 | 标记低信号线程（已建模但 body 中无 actionable 信号） | focus 通常收窄到原始集合的约 30-40% |
| Phase 5 | 标记不应生成草稿的线程（风险过高、上下文不足） | draft candidate 通常少于原始集合的 10% |

为什么重要：

- 没有 attention gate，Phase 4 的 body sampling 会在全量 envelope 集合上消耗 token
- 有了 gate，Phase 4 只在更小的 focus 集合上做深度采样，能显著降低 token 成本并提升 review 质量
- gate 还会改善精度：噪声线程更少，`urgent/pending` 队列里的误报也会更少

重要规则：

- gate 是建议性的，不是破坏性的，原始数据永远不被修改
- 每个 skip 决策都必须记录原因
- attention budget 是累积的：每个 phase 都继承并细化上一阶段的 budget

### 4. 价值呈现层（Value Surface Layer）

用途：

- 把推断出的线程状态转换成能立刻为用户节省时间的可见输出

典型 surface：

- `daily-urgent`
- `pending-replies`
- `blocked-threads`
- `weekly-brief`
- `project-watchlist`

这些 surface 中可能出现两类紧急性：

- 从邮件活动中推断出来的实时线程紧急性
- 从标准化用户上下文中推断出来的计划义务紧急性

紧急性的来源必须始终明确。

投影规则（projection rules）：

- thread state 是与 cadence 无关的底层事实；`daily-urgent`、`pending-replies`、`weekly-brief` 是与 cadence 相关的投影
- 日视图和周视图不必输出完全相同，但必须能从相同的底层 thread state 与 context fact 推导出来
- `weekly-brief` 不应退化成纯 prose summary；默认应同时包含 `action-now`、`unresolved-but-not-urgent backlog` 和 `important weekly changes`
- `urgent` 和 `pending` 是正交维度：一个线程可以同时属于两者、只属于其中之一，或两者都不属于
- 条目不应仅因时间流逝而被自动降级；相反，应累积 `carry_over` 或 `stuck` 之类的 aging signal
- 高风险 FYI 线程在当下重要时，即使不需要直接回复，也可以作为 `monitor_only` 项出现

重要规则：

- 如果这一层本身对用户没有用，系统就不应该进入更激进的自动化阶段

### 4.5. 托管任务路由层（Hosted Task Routing Layer）

用途：

- 为 skill / agent runtime 提供稳定、可预测的任务入口
- 把自然语言高频请求路由到现有只读投影视图
- 降低“模型只读 `SKILL.md` 但没有继续执行命令”的概率

这一层的定位：

- 它是**适配层**，不是新的领域模型
- 它不应替代 `mailbox` / `queue` / `thread` / `digest` / `action` / `review` 这些底层能力
- 它只负责把宿主侧最常见的用户意图，压到已经存在的稳定投影和 JSON 契约上

选择 task 路由时，优先满足五个标准：

1. **通用意图**：不绑定某个公司、岗位或组织流程
2. **薄包装**：必须直接映射到现有 artifact、投影或诊断命令，不新增第二套推理链路
3. **只读高可靠**：适合作为 hosted skill 的首批 smoke 和默认入口
4. **宿主可验证**：能明显验证“命令是否真的执行了”，而不只是 prompt 看起来合理
5. **覆盖核心面**：合起来能覆盖“总览 / 待办 / drill-down / 健康检查”四类基本问题

按当前仓库实现，优先保留的 task 路由是：

- `latest-mail`：总览“今天发生了什么”
- `todo`：汇总“我现在要处理什么”
- `progress`：下钻“某件事到哪了”
- `mailbox-status`：确认“系统能不能工作”

补充规则：

- `weekly` 是合理补充，但不属于 hosted smoke 的第一优先级
- 若未来新增 task 路由，应该先证明它满足以上五个标准，而不是因为某个 prompt 很常见就直接升格
- 若某个 task 路由需要新的状态机、独立推理逻辑或强组织定制，它更可能属于底层能力扩展，而不是 task 适配层

### 5. 策略与画像层（Policy and Profile Layer）

用途：

- 让通用工作流引擎适配特定角色、团队或组织

示例：

- org domain allowlist
- workflow keyword dictionary
- 发件人或团队优先级
- 风险阈值
- digest section
- 审批规则
- 重复性 cadence 规则
- glossary 与 alias 映射

重要规则：

- profile config 可以塑造解释方式、排序、队列成员资格与表现形式，但不应分叉核心 lifecycle engine
- 通用 profile 更新不应直接重标记 lifecycle state；只有显式的用户确认事实才可以

### 6. 草稿与动作层（Draft and Action Layer）

用途：

- 在价值呈现层稳定之后，生成结构化的助手动作

第一波动作：

- `summarize`
- `classify`
- `remind`
- `draft_reply`

后续阶段动作：

- `send`
- `archive`
- `notify_external_system`

重要规则：

- 在只读价值尚未证明之前，发送不应成为一等优化目标

### 7. 复核与运维层（Review and Ops Layer）

用途：

- 保证系统安全、可观测、可恢复

包含：

- approval gate
- audit log
- retry rule
- dead-letter handling
- evidence snapshot
- fallback model routing
- 输出与草稿质量指标

## 运行时扩展面（Runtime Extension Surface）

第一版公开运行时（public runtime）应暴露一套小而明确的扩展模型，而不是把行为隐藏在 prompt 中。

### Listener Layer

用途：

- 响应标准化线程状态事件
- 刷新价值 surface 和低风险提醒
- 在早期 phase 中保持以读取为主（read-oriented）

推荐事件类型：

- `thread_entered_state`
- `thread_sla_risk`
- `daily_digest_time`
- `weekly_digest_time`
- `context_updated`
- `confidence_below_threshold`

节奏规则（cadence rules）：

- 日和周的 value surface 默认应按计划任务预计算
- 临时用户动作可以触发局部重算，但计划任务生成的 surface 仍应是默认体验
- 如果计划生成的 surface 已过期或失败，运行时可以先返回上一次成功投影并标记为 `stale`，同时把刷新任务放到后台队列

### Action Template Layer

用途：

- 定义可复用能力，而不是把能力绑定到单个线程
- 保持高风险行为可复核，并受 phase gating 约束

示例：

- `summarize_thread`
- `build_daily_digest`
- `build_weekly_digest`
- `remind_owner`
- `draft_reply`

### Action Instance Layer

用途：

- 用模板加线程/上下文状态，实例化出一个具体动作提案
- 生成带 evidence、confidence 和 due hint 的可复核 payload

重要规则：

- instance 属于运行时数据与 review flow，而不是静态配置文件

### Execution Audit Layer

用途：

- 记录每一次 listener emission、草稿提案、审批、拒绝与发送尝试
- 让自动化在获得信任之前始终可审查

重要规则：

- 每个有意义的动作都必须留下 machine-readable 的审计轨迹

## 用户能立刻感知的价值面

评价这套架构，应看它能否稳定产出下面几种结果：

- 我今天必须跟进什么
- 哪些事情在等我
- 哪个重要线程被卡住了
- 这一周发生了什么变化，而我无需重新通读整个邮箱

对最终用户来说，这些结果比抽象分类或泛化自动化叙事更容易感知。

## 推荐的仓库形态（Repository Shape）

```text
twinbox/
├── AGENTS.md
├── ROADMAP.md
├── .env
├── docs/
│   ├── README.md
│   ├── ref/
│   │   ├── architecture.md
│   │   ├── orchestration.md
│   │   ├── runtime.md
│   │   └── validation.md
│   ├── assets/
│   └── validation/
│       └── README.md
├── src/
│   └── twinbox_core/
├── scripts/
│   ├── check_env.sh
│   ├── run_pipeline.sh
│   ├── twinbox
│   ├── twinbox_orchestrate.sh
│   └── render_himalaya_config.sh
├── config/
│   ├── action-templates/
│   ├── context/
│   ├── profiles/
│   └── policy.default.yaml
└── runtime/
    ├── context/
    │   ├── material-manifest.json
    │   ├── material-extracts/
    │   ├── human-context.yaml
    │   └── context-pack.json
    ├── himalaya/
    ├── validation/
    ├── state/
    └── drafts/
```

## 决策流（Decision Flow）

```text
mail sync
-> normalize message event
-> ingest human and material context
-> normalize context facts with provenance
-> reconstruct thread
-> infer workflow and state
-> apply attention gate & routing rules (read previous budget, evaluate routing-rules.yaml, classify focus/deprioritize/skip)
-> attach evidence and confidence (focus set only for deep analysis)
-> generate user-visible queues
-> output updated attention-budget.yaml
-> optionally build a draft plan (focus set only)
-> check review threshold
-> execute allowed action
-> log outcome and learn from validated edits
```

## 通用核心与可定制面的分界

通用核心（universal core）：

- sync engine
- canonical message and thread schema
- canonical context fact schema
- thread reconstruction
- workflow inference engine
- attention gate and progressive budget
- context merge and provenance model
- evidence and confidence model
- value-surface generator
- draft runner
- audit and review gate

可定制面（customizable surface）：

- org domain map
- workflow dictionary
- priority 和 SLA 规则
- profile YAML
- manual habits 与 confirmed facts
- prompt fragment
- digest template
- escalation routing

## 用户真正能感知到的成功指标

- 更少错过高优先级跟进
- 更快完成早晨分拣（morning triage）
- 更清晰的 waiting-on-me 列表
- 更低的周报汇总成本
- 更低的草稿编辑负担

这些指标比“支持多少标签、动作或画像”更重要。

## 暂时不该优化的方向

- 大范围的外部自动发送
- 在价值被证明之前就做 CRM 或 ticket 同步
- 在缺少工作流证据的前提下做过细的 persona 分支
- 绕过线程模型的一次性租户 hack

## 实践落地规则

如果一个需求改变的是某个人如何看到输出，把它放进 profile config。

如果一个需求改变的是某个团队如何命名或排序工作流，把它放进 workflow 或 policy config。

如果一个需求本质上是用户提供的重复性任务、上传材料或显式事实修正，把它放进带 provenance 与 validity metadata 的标准化上下文工件。

如果一个需求能提升所有人的 thread reconstruction、state inference、evidence quality 或 review safety，把它放进通用核心。
