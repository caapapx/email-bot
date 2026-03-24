# Cadence Runtime Strategy

日期：2026-03-23
状态：Draft

## 执行摘要

本规范定义 twinbox 的 cadence 运行策略，包括预计算刷新、局部重算、stale 标记和 background refresh 的行为。

**核心原则**：

- thread state 是 cadence-independent truth
- daily/weekly 视图是 cadence-specific projections
- 默认体验是预计算，而不是临时现算
- 失败时展示 stale 结果，后台补算

## 核心概念

### 1. Cadence Truth vs Projection

**Truth（真相）**：
- Thread state（线程状态）
- Context facts（上下文事实）
- User profile（用户画像）

**Projection（投影）**：
- daily-urgent（每日紧急事项）
- pending-replies（待回复）
- weekly-brief（每周简报）

**关键规则**：

- Projection 必须从 truth 派生，不能独立维护
- 不同 cadence 的 projection 可以不同，但必须可解释
- Weekly 不是"更短的 daily"，而是不同的视角

### 2. Weekly Brief 分层结构

Weekly brief 不是 prose-only summary，而是默认三层结构：

```yaml
action_now:
  - 必须今天/下周一前处理的线程
  - 高优先级、有明确 deadline 的事项

backlog:
  - 仍待处理但不紧急的线程
  - 可以延后但不应遗忘的事项

important_changes:
  - 本周重要变化摘要（prose）
  - 新增、关闭、状态变化的统计
```

**实现位置**：`src/twinbox_core/task_cli.py::cmd_digest_weekly()`

---

## 预计算刷新策略

### 1. 定时刷新

**目标**：默认体验是预计算，而不是临时现算。

**刷新频率**：

| Cadence | 刷新频率 | 触发时间 | 目标延迟 |
|---------|---------|---------|---------|
| daily | 每天 1 次 | 早上 8:30 | < 5 分钟 |
| weekly | 每周 1 次 | 周五下午 17:30 | < 10 分钟 |

**实现方式**：

- 使用 cron 或类似调度器
- 调用 `twinbox orchestrate run phase4`
- 生成新的 Phase 4 artifacts

**失败处理**：

- 如果刷新失败，保留上次成功的结果
- 标记为 `stale`（超过 24 小时）
- 后台继续尝试补算

### 2. 手动刷新

**触发方式**：

```bash
twinbox orchestrate run phase4
```

**使用场景**：

- 用户主动请求最新结果
- 定时任务失败后的手动补救
- 开发调试

---

## Context Updated 触发的局部重算

### 1. Context Updated 事件

**触发条件**：

- 用户导入新材料：`twinbox context import-material`
- 用户更新事实：`twinbox context upsert-fact`
- 用户修改画像：`twinbox context profile-set`
- 用户触发刷新：`twinbox context refresh`

**事件内容**：

```yaml
event_type: context_updated
timestamp: 2026-03-23T10:00:00Z
affected_scope:
  - material_ids: [material-abc123]
  - fact_ids: [customer-tier]
  - profile_keys: [response-style]
```

### 2. 局部重算策略

**目标**：只重算受影响的对象，避免全量刷新。

**重算范围**：

| 更新类型 | 受影响对象 | 重算范围 |
|---------|-----------|---------|
| 导入材料 | 所有线程 | 全量重算（材料可能影响所有线程） |
| 更新事实 | 相关线程 | 局部重算（只重算引用该事实的线程） |
| 修改画像 | 所有线程 | 影响 ranking 和 queue membership，不重标 thread state |

**实现方式**：

```bash
# 用户触发
twinbox context refresh

# 或者自动触发（未来）
# 当 context 命令执行后，自动触发局部重算
```

**重算步骤**：

1. 识别受影响的线程（通过 context_refs）
2. 重新运行 Phase 3（thread state inference）
3. 重新运行 Phase 4（queue projection）
4. 更新 generated_at 时间戳
5. 清除 stale 标记

### 3. 重算 vs 全量刷新

**局部重算**：
- 触发：context_updated 事件
- 范围：受影响的线程和队列
- 时间：< 1 分钟
- 适用：用户主动更新 context

**全量刷新**：
- 触发：定时任务或手动命令
- 范围：所有线程和队列
- 时间：< 5 分钟
- 适用：夜间校正、漂移修正

---

## Stale 标记和 Background Refresh

### 1. Stale 检测

**定义**：如果 artifact 的 `generated_at` 超过 24 小时，标记为 stale。

**实现位置**：`src/twinbox_core/task_cli.py::_is_stale()`

**检测逻辑**：

```python
def _is_stale(generated_at_str: str, max_age_hours: int = 24) -> bool:
    """Check if artifact is stale based on generated_at timestamp."""
    try:
        generated = datetime.fromisoformat(generated_at_str)
        now = datetime.now(generated.tzinfo)
        age_hours = (now - generated).total_seconds() / 3600
        return age_hours > max_age_hours
    except (ValueError, TypeError):
        return True
```

**Stale 阈值**：

| Cadence | Stale 阈值 | 说明 |
|---------|-----------|------|
| daily | 24 小时 | 超过 1 天未刷新 |
| weekly | 7 天 | 超过 1 周未刷新 |

### 2. Stale 展示行为

**原则**：失败时展示 stale 结果，而不是空白或错误。

**展示规则**：

- 如果 artifact 存在但 stale，展示内容并标记 `[STALE]`
- 如果 artifact 不存在，返回错误提示
- Stale 标记应该明显但不阻断使用

**示例输出**：

```text
队列类型: urgent
生成时间: 2026-03-22T06:00:00Z
状态: 过期 [STALE]
线程数: 3

提示: 运行 'twinbox orchestrate run phase4' 刷新队列
```

### 3. Background Refresh

**目标**：当检测到 stale 时，后台自动补算。

**触发条件**：

- 用户查询 stale 队列时
- 定时任务失败后的重试
- 系统空闲时的主动刷新

**实现方式**（未来）：

```bash
# 后台刷新（不阻塞用户）
twinbox orchestrate run phase4 --background

# 或者通过 listener 自动触发
# 当检测到 stale 时，自动提交刷新任务到队列
```

**重试策略**：

- 首次失败：立即重试 1 次
- 再次失败：等待 5 分钟后重试
- 持续失败：等待 30 分钟后重试
- 最多重试 3 次，然后放弃

---

## 夜间全量校正

### 1. 目标

**问题**：局部重算可能导致漂移和不一致。

**解决方案**：夜间全量刷新，修正漂移、补齐漏算、回收过期 context。

### 2. 校正策略

**频率**：每天凌晨 2:00

**范围**：

- 重新运行 Phase 1-4
- 清理过期 context
- 回收 stale ranking
- 重建所有队列和摘要

**实现方式**：

```bash
# Cron 任务
0 2 * * * cd /path/to/twinbox && twinbox orchestrate run phase1 phase2 phase3 phase4
```

### 3. 校正 vs 局部重算

| 维度 | 局部重算 | 夜间校正 |
|------|---------|---------|
| 触发 | context_updated | 定时任务 |
| 范围 | 受影响对象 | 全部对象 |
| 时间 | < 1 分钟 | < 10 分钟 |
| 目的 | 快速响应 | 修正漂移 |

---

## 实现检查清单

- [x] DigestView 对象定义
- [x] _is_stale() 函数实现
- [x] digest daily/weekly 命令实现
- [x] weekly brief 分层结构支持
- [ ] 定时刷新 cron 任务配置
- [ ] context_updated 事件触发机制
- [ ] 局部重算实现
- [ ] background refresh 实现
- [ ] 夜间全量校正 cron 任务配置

---

## 参考文档

- [core-refactor-plan.md](../plans/core-refactor-plan.md) - 焦点 3：cadence 运行策略
- [architecture.md](../architecture.md) - cadence truth/projection 部分
- [object-contract.md](./object-contract.md) - DigestView 定义
- [task-facing-cli.md](./task-facing-cli.md) - digest 命令规范

