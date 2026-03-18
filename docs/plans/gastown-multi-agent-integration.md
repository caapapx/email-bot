# Gastown 多 Agent 集成方案

日期：2026-03-18
项目：twinbox

## 背景

twinbox 当前是线性单 agent 执行（6 个 shell 脚本串行跑 Phase 1-4）。分析 gastown 后发现阶段内子任务可以并发（Phase 1 的 3 个统计、Phase 4 的 3 个输出），且 gastown 已经在工作目录里。

本方案定义如何将 twinbox 作为 rig 运行，使用 gastown 的 polecat/refinery/witness 实现多 agent 协作。

### 当前脚本的核心问题

现有 phase 脚本是纯 loading 管线——数据搬运 + regex 模式匹配，零 LLM 介入：

| 脚本 | "推断"方式 | 问题 |
|------|-----------|------|
| phase1: intent 分类 | 8 条 regex，fallback 到 `human` | 未覆盖模式全部丢失 |
| phase2: persona 推断 | 硬编码 3 个假设 + 固定置信度 0.88/0.85/0.8 | 不是推断，是填空 |
| phase4: 紧急度评估 | `urgencyScore += 30` 加权打分 + thread_key 硬编码 why | 无法泛化到新线程 |

这违背了 agent 设计的核心——应该是 loading → thinking 的转变，而不是 loading → template filling。

### LLM 配置

gastown 不需要单独配 API key。polecat 通过 `CLAUDE_CONFIG_DIR` 继承宿主的 Claude Code session，直接复用当前账户认证。支持 `--agent` 切换后端（claude/codex/gemini），默认 claude。

## Gastown 核心概念对照

| gastown 概念 | 说明 | twinbox 映射 |
|-------------|------|-------------|
| Rig | 项目容器，包裹 git 仓库 | twinbox 仓库本身 |
| Polecat | 工作 agent，持久身份 + 临时 session | Phase 子任务执行器 |
| Refinery | 合并队列处理器，串行化合并到 main | 合并子任务输出为 attention-budget.yaml |
| Witness | 监控 polecat 健康，检测 stall/zombie | 监控子任务执行状态 |
| Bead | Git-backed issue，任务单元 | 每个子任务对应一个 bead |
| Formula | 可复用工作流模板（TOML/JSON） | 子任务配置定义 |
| Convoy | 捆绑多个 bead 的工作追踪单元 | 一个 Phase 的所有子任务 |
| Sling | 统一工作分发命令 | 分发子任务给 polecat |
| Hook | 持久化原语，工作挂载点 | 子任务状态持久化 |

## Agent 角色定义

### Analyst（Phase 1-3 子任务执行）

- **映射**：Polecat × N
- **分发方式**：`gt sling <formula> <polecat>`
- **并发子任务**：
  - Phase 1: sender-stats / intent-classify / time-dist
  - Phase 2: persona-inference / business-inference
  - Phase 3: lifecycle-modeling / thread-sampling

### Value（Phase 4 子任务执行）

- **映射**：Polecat × N
- **分发方式**：`gt sling <formula> <polecat>`
- **并发子任务**：
  - daily-urgent
  - pending-replies
  - sla-risks

### Merger（合并输出）

- **映射**：Refinery
- **职责**：收集所有 polecat 输出，合并为 `attention-budget.yaml`
- **触发**：所有子任务 polecat 完成后自动触发

### Monitor（健康监控）

- **映射**：Witness
- **职责**：检测 stalled/zombie polecat，nudge 无响应 session，清理完成的 sandbox

## 并发场景

### 场景 1：Phase 1 阶段内并发

```
gt sling phase1-sender-stats polecat-a
gt sling phase1-intent-classify polecat-b
gt sling phase1-time-dist polecat-c
```

三个 polecat 并行执行，各自产出写入 `runtime/validation/phase-1/`。
全部完成后 refinery 合并为 `phase-1-report.md`。

### 场景 2：Phase 4 阶段内并发

```
gt sling phase4-daily-urgent polecat-d
gt sling phase4-pending-replies polecat-e
gt sling phase4-sla-risks polecat-f
```

三个 polecat 并行执行，各自产出写入 `runtime/validation/phase-4/`。
全部完成后 refinery 合并为 `attention-budget.yaml`。

### 场景 3：增量更新时的读写分离

- 读：polecat 从 `runtime/context/` 读取上下文
- 写：polecat 只写入自己的输出目录
- 合并：refinery 串行化合并，避免写冲突

## Gastown 命令映射

| 操作 | 命令 | 说明 |
|------|------|------|
| 分发子任务 | `gt sling <formula> [polecat]` | 自动 spawn polecat 或分配给已有 polecat |
| 发送即时消息 | `gt nudge <polecat> "message"` | 向 polecat 活跃 session 发送指令 |
| 发送持久消息 | `gt mail send <target> -s "Subject"` | 跨 session 持久消息 |
| 查看状态 | `gt status` | 查看 rig 内所有 agent 状态 |
| 标记完成 | `gt done` | polecat 自行标记任务完成 |
| 捆绑追踪 | `gt convoy` | 将一个 Phase 的子任务捆绑追踪 |
| 健康检查 | `gt health` | 检查 polecat 健康状态 |
| 活动流 | `gt feed` | 实时查看 gt 事件流 |

## 数据流

```
scripts/phase1_*.sh ──→ polecat-a ──→ runtime/validation/phase-1/sender-stats.json
scripts/phase1_*.sh ──→ polecat-b ──→ runtime/validation/phase-1/intent-classify.json
scripts/phase1_*.sh ──→ polecat-c ──→ runtime/validation/phase-1/time-dist.json
                                          │
                                          ▼
                                     refinery ──→ docs/validation/phase-1-report.md
                                                  runtime/validation/phase-1/mailbox-census.json
```

Phase 4 同理，最终合并为 `attention-budget.yaml`。

## Loading → Thinking 分层架构

每个 Phase 拆为两层，解决邮件量浮动下的效率与准确性平衡：

```
┌─────────────────────────────────────────────┐
│  Loading 层（shell/node，确定性，快）         │
│  - himalaya 拉取 envelope/body              │
│  - 结构化提取（日期、发件人、附件）            │
│  - 采样策略（控制送入 LLM 的量）              │
│  产出：structured context JSON               │
├─────────────────────────────────────────────┤
│  Thinking 层（polecat = Claude session）     │
│  - 读取 context JSON                        │
│  - LLM 推断 intent / persona / risk         │
│  - 输出带证据链的结论                         │
│  产出：YAML/report with real confidence      │
└─────────────────────────────────────────────┘
```

### 邮件量自适应采样策略

| 邮件量 | 策略 | Loading 层 | Thinking 层 |
|--------|------|-----------|-------------|
| < 100 | 全量 | 全部结构化 | 逐条分析 |
| 100-500 | 分层采样 | 全量 envelope，body 采样 top 50 | 先批量分类，再对 focus 集深入 |
| 500-2000 | 渐进漏斗 | envelope 全量统计，body 按 attention-budget 采样 | 两轮：粗筛 → 精分析 |
| > 2000 | 时间窗 + 漏斗 | 按时间/文件夹切片，每片独立采样 | 多 polecat 并行处理切片 |

### 各 Phase 改造要点

**Phase 1 — intent 分类**
- Loading：himalaya 拉 envelope + body 采样（保留）
- Thinking：polecat 读 envelope batch → LLM 输出 `{intent, confidence, evidence}`
- 并发：按 batch 分配多 polecat，每个处理 ~50 封

**Phase 2 — persona 推断**
- Loading：读 Phase 1 统计结果（保留）
- Thinking：polecat 读全量统计 + 采样正文 → LLM 生成画像假设 + 真实置信度
- 不再硬编码假设和置信度

**Phase 4 — 价值输出**
- Loading：fetch recent bodies（保留）
- Thinking：polecat 读 thread context → LLM 判断紧急度/风险/action + 理由
- 并发：urgent / pending / risk 三个 polecat 并行

### Gastown 编排示例

```
Phase 1 (gt convoy)
├── polecat-loader    : shell 脚本拉 envelope（loading，快）
├── polecat-intent-a  : batch 1-50 intent 分类（thinking）
├── polecat-intent-b  : batch 51-100 intent 分类（thinking）
└── refinery          : 合并 intent 结果 → census + attention-budget

Phase 4 (gt convoy)
├── polecat-loader    : fetch recent bodies（loading）
├── polecat-urgent    : 评估紧急度（thinking）
├── polecat-pending   : 评估待回复（thinking）
├── polecat-risk      : 评估风险（thinking）
└── refinery          : 合并 → daily-urgent + sla-risks + weekly-brief
```

## 迁移路径

### 阶段 1：Loading/Thinking 分离 ✅

已完成。将 phase1_mailbox_census.sh 拆为：
- `scripts/phase1_loading.sh` — 确定性数据拉取 + 结构化
- `scripts/phase1_thinking.sh` — 调用 LLM 做 intent 分类（OpenAI-compatible API, kimi-k2.5）

实测结果：30 封样本 regex vs LLM 不一致率 93%，LLM 新增 3 个关键 intent 类别。
详见 [`docs/reports/phase1-intent-llm-migration.md`](../reports/phase1-intent-llm-migration.md)。

### 阶段 1.5：Phase 2 Persona LLM 改造 ✅

已完成。将 phase2_profile_inference.sh 拆为：
- `scripts/phase2_loading.sh` — 读 Phase 1 产出 + 构建 enriched context pack
- `scripts/phase2_thinking.sh` — 单次 LLM 调用生成 persona + business 假设

实测结果：旧脚本 3 条硬编码假设 → LLM 输出 5 条 persona + 4 条 business，含具体证据链。
详见 [`docs/reports/phase2-persona-llm-migration.md`](../reports/phase2-persona-llm-migration.md)。

### 阶段 1.6：Phase 3 Lifecycle LLM 改造 ✅

已完成。新增：
- `scripts/phase3_loading.sh` — 线程分组 + Phase 1/2 产出 + 人工上下文 → context-pack
- `scripts/phase3_thinking.sh` — LLM 推断生命周期流、阶段、线程归类

实测结果：5 条生命周期流，20 条线程全部归类，每条带证据链。
详见 [`docs/reports/phase3-lifecycle-llm-migration.md`](../reports/phase3-lifecycle-llm-migration.md)。

### 阶段 1.7：Phase 4 Value LLM 改造 ✅

已完成。新增：
- `scripts/phase4_loading.sh` — fetch recent bodies + lifecycle context + 人工上下文 → context-pack
- `scripts/phase4_thinking.sh` — LLM 生成 daily-urgent / pending-replies / sla-risks / weekly-brief

实测结果：5 urgent + 3 pending + 4 risks，替代硬编码 urgencyScore 和 classifyFlow。
详见 [`docs/reports/phase4-value-llm-migration.md`](../reports/phase4-value-llm-migration.md)。

### 阶段 2：单 Phase gastown 试跑

选一个 Phase（建议 Phase 4，子任务最独立）用 gastown 跑：
1. 定义 3 个 formula
2. `gt sling` 分发给 3 个 polecat
3. 验证并发输出正确性
4. 配置 refinery 合并规则

### 阶段 3：全 Phase 迁移

Phase 1-3 逐步迁移，保留原始 shell 脚本作为 fallback。

### 阶段 4：Witness 集成

配置 witness 监控所有 polecat，处理 stall/crash 场景。

## 待确认问题

1. **优先并发场景**：Phase 1 的 3 个统计 vs Phase 4 的 3 个输出，哪个对当前阶段最有价值？
2. **崩溃恢复策略**：是否需要 Witness 做自动崩溃恢复，还是手动重跑就够？
3. **多邮箱并行**：多邮箱并行是否在近期规划内？如果是，每个邮箱一个 rig 还是一个 convoy？
4. **Formula 格式**：gastown formula 支持 TOML/JSON，twinbox 偏好哪种？
5. **Refinery 合并逻辑**：attention-budget.yaml 的合并是简单拼接还是需要冲突解决？
