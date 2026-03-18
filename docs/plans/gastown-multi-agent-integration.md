# Gastown 多 Agent 集成方案

日期：2026-03-18
项目：twinbox

## 背景

twinbox 当前是线性单 agent 执行（6 个 shell 脚本串行跑 Phase 1-4）。分析 gastown 后发现阶段内子任务可以并发（Phase 1 的 3 个统计、Phase 4 的 3 个输出），且 gastown 已经在工作目录里。

本方案定义如何将 twinbox 作为 rig 运行，使用 gastown 的 polecat/refinery/witness 实现多 agent 协作。

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

## 迁移路径

### 阶段 1：Formula 定义

将现有 shell 脚本封装为 gastown formula：

```toml
# formulas/phase1-sender-stats.toml
[formula]
name = "phase1-sender-stats"
description = "Phase 1: 发件人统计分析"

[input]
mailbox_census = "runtime/validation/phase-1/mailbox-census.json"

[output]
sender_stats = "runtime/validation/phase-1/sender-stats.json"

[steps]
command = "scripts/phase1_mailbox_census.sh"
```

### 阶段 2：单 Phase 试跑

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
