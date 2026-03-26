# 增量邮件处理与用户队列状态管理设计

> 设计日期：2026-03-26
> 方案：C1（渐进式增量）
> 状态：设计中

---

## 1. 背景与目标

### 当前问题

1. **Phase 1 全量同步慢**：每次 daytime-sync 都拉取 lookback_days=7 的所有邮件
2. **无用户干预机制**：用户无法标记"已完成"或"忽略"
3. **重复推送**：已处理的线程仍会出现在队列中

### 目标

1. **增量同步**：daytime-sync 只拉取新邮件（10-100 倍性能提升）
2. **用户状态管理**：支持标记 dismissed/completed
3. **智能重新激活**：线程有新回复时自动恢复到队列
4. **保持稳定性**：nightly-full 保留全量作为对账机制

---

## 2. 架构概览

### 核心组件

```
用户交互层
  ↓ twinbox queue dismiss/complete/restore
用户状态管理层
  ↓ runtime/context/user-queue-state.yaml
增量同步层 (新增)
  ↓ runtime/context/uid-watermarks.json
  ↓ Python imaplib 增量拉取
Phase 1-4 处理层
  ↓ Phase 1: 增量模式 vs 全量模式
  ↓ Phase 4: 合并用户状态过滤
推送层
  ↓ 过滤 dismissed + 检测重新激活
```

### 两种运行模式

**增量模式（daytime-sync）**：
- Python imaplib 按 UID 水位拉新邮件
- 合并到现有 phase1-context.json
- Phase 2-4 只处理新增/变化的线程

**全量模式（nightly-full）**：
- 保持现有 phase1_loading.sh
- 作为对账机制，捕获移动/删除/标记变化

---

## 3. 数据结构

### 3.1 UID 水位文件

**路径**：`runtime/context/uid-watermarks.json`

```json
{
  "INBOX": {
    "uidvalidity": 42,
    "last_uid": 12345,
    "last_sync_at": "2026-03-26T10:00:00+08:00"
  },
  "Sent": {
    "uidvalidity": 17,
    "last_uid": 6789,
    "last_sync_at": "2026-03-26T10:00:00+08:00"
  }
}
```

**关键规则**：
- `uidvalidity` + `last_uid` 配对使用，UIDVALIDITY 变化时丢弃旧水位
- 原子写入：temp file + `os.replace()`
- 每次增量同步成功后更新

### 3.2 用户队列状态文件

**路径**：`runtime/context/user-queue-state.yaml`

```yaml
dismissed:
  - thread_id: "thread-123"
    dismissed_at: "2026-03-26T10:00:00+08:00"
    reason: "已回复"
    dismissed_from_queue: "urgent"
    snapshot:
      last_message_id: "msg-456"
      message_count: 5
      fingerprint: "msg-456|urgent"
      last_activity_at: "2026-03-26T09:30:00+08:00"

completed:
  - thread_id: "thread-789"
    completed_at: "2026-03-26T11:00:00+08:00"
    action_taken: "已归档"
    snapshot:
      last_message_id: "msg-999"
      message_count: 3
      fingerprint: "msg-999|pending"
      last_activity_at: "2026-03-26T10:00:00+08:00"
```

**区别**：
- `dismissed`：暂时忽略，有新回复时智能重新激活
- `completed`：已完成，不自动恢复（需手动 restore）

### 3.3 Schedule 覆盖文件

**路径**：`runtime/context/schedule-overrides.yaml`

```yaml
timezone: "Asia/Shanghai"
overrides:
  daily-refresh: "30 9 * * *"
  weekly-refresh: "30 18 * * 5"
  nightly-full-refresh: "0 3 * * *"
```

**规则**：
- SKILL.md 的 `metadata.openclaw.schedules` 保持不变（默认值）
- 此文件为用户级覆盖，优先级高于默认值
- 修改后需通知 OpenClaw 重新注册 cron

---

## 4. 增量同步核心逻辑

### 4.1 新增模块：`src/twinbox_core/imap_incremental.py`

**核心函数**：

```python
def fetch_incremental_envelopes(
    state_root: Path,
    folders: list[str],
    imap_config: dict
) -> dict:
    """
    按 UID 水位增量拉取邮件。

    Returns:
        {
            "new_envelopes": [...],
            "updated_watermarks": {...},
            "uidvalidity_changed": ["INBOX", ...]
        }
    """
```

**关键步骤**：

1. 读取 `uid-watermarks.json`
2. 用 `imaplib` 连接 IMAP（复用 `.env` 中的 IMAP_HOST/PORT/LOGIN/PASS）
3. 对每个 folder：
   - `SELECT folder` → 获取当前 UIDVALIDITY
   - 如果 UIDVALIDITY 变化 → 标记需要全量重扫
   - 如果不变 → `UID SEARCH last_uid+1:*`
   - `UID FETCH (ENVELOPE FLAGS)` 批量获取
4. 返回新 envelope + 更新后的水位

### 4.2 UIDVALIDITY 变化处理

```
UIDVALIDITY 变化
  → 丢弃该 folder 的旧水位
  → 回退到 lookback_days 窗口重扫（调用现有 phase1_loading.sh）
  → 重建水位
```

### 4.3 Phase 1 增量脚本：`scripts/phase1_incremental.sh`

```
1. 调用 Python 增量同步
2. 检查 uidvalidity_changed
   → 非空：回退全量 phase1_loading.sh
3. 合并新 envelope 到 phase1-context.json
4. 原子更新 uid-watermarks.json
5. 用 himalaya 采样新邮件的 body（保持现有逻辑）
```

### 4.4 orchestration.py 改造

`daytime-sync` job 改为调用增量脚本：

```python
# daytime-sync: 增量
("phase1-incremental", ["bash", "scripts/phase1_incremental.sh"])

# nightly-full: 保持全量
("phase1-full", ["bash", "scripts/phase1_loading.sh"])
```

---

## 5. 用户状态管理

### 5.1 新增模块：`src/twinbox_core/user_queue_state.py`

**核心函数**：

```python
def dismiss_thread(state_root, thread_id, reason, queue, snapshot) -> None
def complete_thread(state_root, thread_id, action_taken, snapshot) -> None
def restore_thread(state_root, thread_id) -> None
def check_reactivation(dismissed, current_thread) -> bool
def filter_dismissed(snapshots, user_state) -> (filtered, reactivated)
```

### 5.2 智能重新激活逻辑

```python
def check_reactivation(dismissed: dict, current_thread: dict) -> bool:
    """
    重新激活条件：
    - last_message_id 不同（有新回复）
    - message_count 增加（有新消息）
    仅对 dismissed 生效，completed 不自动恢复。
    """
    snapshot = dismissed.get("snapshot", {})
    return (
        current_thread.get("latest_message_ref")
        != snapshot.get("last_message_id")
    )
```

### 5.3 CLI 命令

| 命令 | 作用 |
|------|------|
| `twinbox queue dismiss THREAD_ID --reason "已处理"` | 标记为 dismissed |
| `twinbox queue complete THREAD_ID --action "已回复"` | 标记为 completed |
| `twinbox queue restore THREAD_ID` | 恢复到队列 |
| `twinbox queue status --json` | 查看当前用户状态 |

### 5.4 OpenClaw 工具

| 工具 | 作用 |
|------|------|
| `twinbox_queue_dismiss` | 对话中标记完成 |
| `twinbox_queue_restore` | 对话中恢复 |

---

## 6. 推送过滤

### 6.1 修改 `push_dispatcher.py`

在推送前增加过滤步骤：

```python
def dispatch_push(state_root, payload, ...):
    # 1. 加载用户状态
    user_state = load_user_state(state_root)

    # 2. 过滤 dismissed + 检测重新激活
    filtered, reactivated = filter_dismissed_threads(
        payload["snapshots"], user_state
    )

    # 3. 如果有重新激活，从 dismissed 移除
    if reactivated:
        remove_dismissed(state_root, reactivated)

    # 4. 推送过滤后的队列
    ...
```

### 6.2 推送内容变化

推送消息中增加：
- 新增线程数
- 重新激活线程数
- 已过滤（dismissed）线程数

---

## 7. Schedule 覆盖

### 7.1 新增 CLI 命令

| 命令 | 作用 |
|------|------|
| `twinbox schedule list --json` | 查看当前调度配置（默认 + 覆盖） |
| `twinbox schedule update JOB_NAME --cron "30 9 * * *"` | 修改调度时间 |
| `twinbox schedule reset JOB_NAME` | 恢复默认 |

### 7.2 实现方式

- 读取 `runtime/context/schedule-overrides.yaml`
- 合并 SKILL.md 默认值
- 通知 OpenClaw 重新注册 cron（`openclaw skills reload twinbox`）

---

## 8. 文件变更清单

### 新增文件

| 文件 | 职责 |
|------|------|
| `src/twinbox_core/imap_incremental.py` | IMAP 增量同步 |
| `src/twinbox_core/user_queue_state.py` | 用户队列状态管理 |
| `src/twinbox_core/merge_context.py` | Phase 1 context 合并 |
| `scripts/phase1_incremental.sh` | 增量同步入口脚本 |
| `runtime/context/uid-watermarks.json` | UID 水位（运行时生成） |
| `runtime/context/user-queue-state.yaml` | 用户状态（运行时生成） |
| `runtime/context/schedule-overrides.yaml` | 调度覆盖（运行时生成） |

### 修改文件

| 文件 | 改动 |
|------|------|
| `src/twinbox_core/orchestration.py` | daytime-sync 调用增量脚本 |
| `src/twinbox_core/push_dispatcher.py` | 推送前过滤 dismissed |
| `src/twinbox_core/task_cli.py` | 新增 queue/schedule 子命令 |
| `src/twinbox_core/daytime_slice.py` | 合并用户状态过滤 |
| `SKILL.md` | 新增 queue/schedule 命令到任务表 |

---

## 9. 测试策略

| 测试 | 覆盖 |
|------|------|
| `test_imap_incremental.py` | UID 水位读写、UIDVALIDITY 变化处理、增量拉取 |
| `test_user_queue_state.py` | dismiss/complete/restore、重新激活逻辑 |
| `test_merge_context.py` | envelope 合并、去重 |
| `test_push_filter.py` | 推送过滤、重新激活检测 |
| `test_schedule_override.py` | 覆盖读写、合并默认值 |

---

## 10. 风险与缓解

| 风险 | 缓解 |
|------|------|
| IMAP 连接不稳定 | 增量失败时回退全量，不阻塞流水线 |
| UIDVALIDITY 频繁变化 | 自动回退窗口重扫，记录日志 |
| 用户状态文件损坏 | 原子写入 + 备份，损坏时重置为空 |
| 增量遗漏邮件 | nightly-full 全量对账，每 24 小时修正 |
| imaplib 与 himalaya 数据格式不一致 | 统一到 canonical envelope schema |
